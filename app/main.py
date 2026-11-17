"""Web app quản lý: dashboard, video, phân tích, chiến lược, cài đặt."""
import hmac
import logging
import os
import threading
from contextlib import asynccontextmanager

import markdown as md
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import analytics, db, notebooklm, report, scanner, scheduler, strategy, tiktok
from .config import EDITABLE_KEYS, apply_overrides, settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
BASE_DIR = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
templates.env.filters["num"] = lambda x: f"{x:,}".replace(",", ".") if isinstance(x, (int, float)) else "—"
templates.env.filters["delta"] = (
    lambda x: "—" if x is None else (("+" if x >= 0 else "") + f"{x:,}".replace(",", "."))
)
templates.env.filters["localtime"] = analytics.localtime
templates.env.filters["markdown"] = lambda t: md.markdown(t or "", extensions=["tables", "fenced_code"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.get_conn()
    apply_overrides(db.load_settings())
    if os.getenv("DISABLE_SCHEDULER") != "1":
        scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="TikTok Channel Manager", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

PUBLIC_PATHS = ("/login", "/static", "/healthz", "/auth/tiktok/callback", "/privacy", "/terms", "/tiktok")


@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path
    if not path.startswith(PUBLIC_PATHS) and not request.session.get("auth"):
        if path.startswith("/api/"):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return RedirectResponse("/login", status_code=303)
    return await call_next(request)


# Thêm sau cùng để SessionMiddleware bọc ngoài middleware kiểm tra đăng nhập
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, max_age=60 * 60 * 24 * 14, same_site="lax")


def render(request: Request, name: str, **ctx):
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(
        request,
        name,
        {
            "account": db.get_active_account(),
            "flash": flash,
            "active": name.split(".")[0],
            "pending_jobs": (db.query_one("SELECT COUNT(*) AS n FROM strategies WHERE status='pending' OR notified=0") or {}).get("n", 0),
            **ctx,
        },
    )


def flash(request: Request, msg: str, kind: str = "info"):
    request.session["flash"] = {"msg": msg, "kind": kind}


# ---------------- auth ----------------
@app.api_route("/healthz", methods=["GET", "HEAD"])
def healthz():
    return {"ok": True}


@app.get("/privacy", response_class=HTMLResponse)
def privacy_page(request: Request):
    return templates.TemplateResponse(
        request, "legal.html", {"kind": "privacy", "title": "Chính sách quyền riêng tư", "base_url": settings.base_url}
    )


@app.get("/terms", response_class=HTMLResponse)
def terms_page(request: Request):
    return templates.TemplateResponse(
        request, "legal.html", {"kind": "terms", "title": "Điều khoản sử dụng", "base_url": settings.base_url}
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login")
def login(request: Request, password: str = Form(...)):
    if hmac.compare_digest(password.encode(), settings.app_password.encode()):
        request.session["auth"] = True
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": "Sai mật khẩu"}, status_code=401)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# ---------------- TikTok OAuth ----------------
@app.get("/auth/tiktok")
def tiktok_connect(request: Request):
    if not settings.tiktok_client_key or not settings.tiktok_client_secret:
        flash(request, "Chưa cấu hình TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET trong .env", "error")
        return RedirectResponse("/settings", status_code=303)
    url, state = tiktok.build_auth_url()
    request.session["oauth_state"] = state
    return RedirectResponse(url, status_code=303)


@app.get("/auth/tiktok/callback")
def tiktok_callback(request: Request, code: str = "", state: str = "", error: str = "", error_description: str = ""):
    if not request.session.get("auth"):
        return RedirectResponse("/login", status_code=303)
    if error:
        flash(request, f"TikTok từ chối: {error_description or error}", "error")
        return RedirectResponse("/settings", status_code=303)
    expected = request.session.pop("oauth_state", None)
    if not expected or not hmac.compare_digest(expected, state):
        flash(request, "State OAuth không hợp lệ, vui lòng thử lại", "error")
        return RedirectResponse("/settings", status_code=303)
    try:
        tok = tiktok.exchange_code(code)
        db.upsert_account({**tok, "is_demo": 0, "connected_at": db.now_iso()})
    except tiktok.TikTokError as e:
        flash(request, str(e), "error")
        return RedirectResponse("/settings", status_code=303)
    threading.Thread(target=scanner.run_scan, args=("connect",), daemon=True).start()
    flash(request, "Đã kết nối TikTok! Đang quét dữ liệu lần đầu…", "success")
    return RedirectResponse("/", status_code=303)


@app.post("/auth/tiktok/disconnect")
def tiktok_disconnect(request: Request, delete_data: str = Form("")):
    acc = db.get_active_account()
    if acc:
        if acc.get("access_token") and not acc.get("is_demo"):
            tiktok.revoke(acc["access_token"])
        if delete_data:
            db.delete_account(acc["open_id"])
        else:
            db.upsert_account({"open_id": acc["open_id"], "access_token": "", "refresh_token": "", "token_expires_at": 0})
    flash(request, "Đã ngắt kết nối", "info")
    return RedirectResponse("/settings", status_code=303)


# ---------------- pages ----------------
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    acc = db.get_active_account()
    if not acc:
        return render(request, "dashboard.html", ov=None)
    oid = acc["open_id"]
    an = analytics.deep_analysis(oid)
    scans = db.query("SELECT * FROM scans ORDER BY id DESC LIMIT 5")
    return render(
        request,
        "dashboard.html",
        ov=analytics.overview(oid),
        series=analytics.account_series(oid),
        views=analytics.views_series(oid),
        an=an,
        scans=scans,
        next_run=scheduler.next_run(),
    )


@app.get("/videos", response_class=HTMLResponse)
def videos_page(request: Request, sort: str = "create_time", q: str = ""):
    acc = db.get_active_account()
    vids = analytics.get_videos(acc["open_id"]) if acc else []
    if q:
        ql = q.lower()
        vids = [v for v in vids if ql in (v["label"] or "").lower() or ql in (v.get("description") or "").lower()]
    keys = {
        "create_time": lambda v: v.get("create_time") or 0,
        "view_count": lambda v: v["view_count"] or 0,
        "like_count": lambda v: v["like_count"] or 0,
        "comment_count": lambda v: v["comment_count"] or 0,
        "share_count": lambda v: v["share_count"] or 0,
        "engagement": lambda v: v["engagement"],
        "views_per_day": lambda v: v["views_per_day"],
    }
    vids.sort(key=keys.get(sort, keys["create_time"]), reverse=True)
    return render(request, "videos.html", videos=vids, sort=sort, q=q)


@app.get("/videos/{video_id}", response_class=HTMLResponse)
def video_detail(request: Request, video_id: str):
    acc = db.get_active_account()
    v = next((x for x in analytics.get_videos(acc["open_id"]) if x["id"] == video_id), None) if acc else None
    if not v:
        return RedirectResponse("/videos", status_code=303)
    return render(request, "video_detail.html", v=v, hist=analytics.video_history(video_id))


@app.get("/analytics", response_class=HTMLResponse)
def analytics_page(request: Request):
    acc = db.get_active_account()
    an = analytics.deep_analysis(acc["open_id"]) if acc else None
    return render(request, "analytics.html", an=an)


@app.get("/strategy", response_class=HTMLResponse)
def strategy_page(request: Request, id: int | None = None):
    acc = db.get_active_account()
    items = (
        db.query(
            "SELECT id, created_at, source, goal, status, cost_usd FROM strategies WHERE open_id=? ORDER BY id DESC",
            (acc["open_id"],),
        )
        if acc
        else []
    )
    current = None
    if items:
        sid = id or items[0]["id"]
        current = db.query_one("SELECT * FROM strategies WHERE id=? AND open_id=?", (sid, acc["open_id"]))
    return render(
        request, "strategy.html", items=items, current=current, gemini_ready=bool(settings.gemini_api_key),
        answer=request.session.pop("answer", None), usage=strategy.usage_summary(), rate=settings.usd_vnd_rate,
    )


@app.post("/strategy/generate")
def strategy_generate(request: Request, goal: str = Form("")):
    acc = db.get_active_account()
    if not acc:
        flash(request, "Chưa kết nối kênh", "error")
        return RedirectResponse("/strategy", status_code=303)
    sid = strategy.start_background(acc["open_id"], goal.strip(), on_done=notebooklm.sync_all)
    flash(request, "Đang tạo chiến lược ở chế độ nền. Bạn có thể chuyển sang trang khác, sẽ có thông báo khi xong.", "info")
    return RedirectResponse(f"/strategy?id={sid}", status_code=303)


@app.post("/strategy/ask")
def strategy_ask(request: Request, question: str = Form(...)):
    acc = db.get_active_account()
    try:
        if acc:
            answer, usage = strategy.ask(acc["open_id"], question.strip())
        else:
            answer, usage = "Chưa kết nối kênh", None
    except strategy.StrategyError as e:
        answer, usage = f"Lỗi: {e}", None
    request.session["answer"] = {"q": question, "a": answer, "usage": usage}
    return RedirectResponse("/strategy#ask", status_code=303)


@app.post("/strategy/{sid}/delete")
def strategy_delete(request: Request, sid: int):
    with db.tx() as c:
        c.execute("DELETE FROM strategies WHERE id=?", (sid,))
    return RedirectResponse("/strategy", status_code=303)


@app.get("/report", response_class=HTMLResponse)
def report_page(request: Request):
    acc = db.get_active_account()
    text = report.build_report(acc["open_id"]) if acc else "Chưa có dữ liệu"
    return render(request, "report.html", text=text)


@app.get("/report.md")
def report_download():
    acc = db.get_active_account()
    text = report.build_report(acc["open_id"]) if acc else ""
    return HTMLResponse(
        text, media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=tiktok_report.md"},
    )


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return render(
        request,
        "settings.html",
        s=settings,
        next_run=scheduler.next_run(),
        scans=db.query("SELECT * FROM scans ORDER BY id DESC LIMIT 20"),
        syncs=db.query("SELECT * FROM sync_log ORDER BY id DESC LIMIT 20"),
        sa_email=notebooklm.service_account_email(),
        tiktok_ready=bool(settings.tiktok_client_key and settings.tiktok_client_secret),
    )


@app.post("/settings")
async def settings_save(request: Request):
    form = await request.form()
    for key in EDITABLE_KEYS:
        if key == "auto_strategy":
            val = "true" if form.get("auto_strategy") else "false"
        elif key in form:
            val = str(form.get(key)).strip()
        else:
            continue
        db.save_setting(key, val)
    apply_overrides(db.load_settings())
    scheduler.reschedule()
    flash(request, "Đã lưu cài đặt", "success")
    return RedirectResponse("/settings", status_code=303)


@app.post("/scan")
def scan_now(request: Request):
    res = scanner.run_scan("manual")
    flash(request, res["message"], "success" if res["status"] == "ok" else "error")
    return RedirectResponse(request.headers.get("referer") or "/", status_code=303)


@app.post("/sync")
def sync_now(request: Request):
    acc = db.get_active_account()
    if not acc:
        flash(request, "Chưa kết nối kênh", "error")
    else:
        res = notebooklm.sync_all(acc["open_id"])
        if not res:
            flash(request, "NOTEBOOKLM_MODE đang tắt", "info")
        else:
            ok = sum(r["status"] == "ok" for r in res)
            flash(request, f"Đồng bộ NotebookLM: {ok}/{len(res)} thành công", "success" if ok == len(res) else "error")
    return RedirectResponse(request.headers.get("referer") or "/settings", status_code=303)


@app.post("/demo/seed")
def demo_seed(request: Request):
    from . import demo

    if db.get_active_account() and not db.get_active_account().get("is_demo"):
        flash(request, "Đã có kênh thật được kết nối — không tạo dữ liệu demo", "error")
    else:
        db.delete_account(demo.DEMO_ID)
        demo.seed()
        flash(request, "Đã tạo dữ liệu DEMO (giả lập)", "success")
    return RedirectResponse("/", status_code=303)


# ---------------- JSON API ----------------
@app.get("/api/jobs")
def api_jobs():
    """Trạng thái các lần tạo chiến lược chạy ngầm; trả về job vừa xong (mỗi job thông báo 1 lần)."""
    pending = db.query("SELECT id FROM strategies WHERE status='pending'")
    finished = db.query(
        "SELECT id, source, status, total_tokens, cost_usd, duration_sec FROM strategies"
        " WHERE status!='pending' AND notified=0"
    )
    if finished:
        with db.tx() as c:
            c.executemany("UPDATE strategies SET notified=1 WHERE id=?", [(f["id"],) for f in finished])
    for f in finished:
        f["cost_vnd"] = round((f["cost_usd"] or 0) * settings.usd_vnd_rate)
    return {"pending": [p["id"] for p in pending], "finished": finished}


@app.get("/api/overview")
def api_overview():
    acc = db.get_active_account()
    return analytics.overview(acc["open_id"]) if acc else {}


@app.get("/api/videos")
def api_videos():
    acc = db.get_active_account()
    if not acc:
        return []
    return [{k: v for k, v in x.items() if k != "posted_local"} for x in analytics.get_videos(acc["open_id"])]


# Đặt cuối cùng để không che các route khác
VERIFY_DIR = os.path.join(os.path.dirname(os.path.abspath(settings.database_path)), "verify")


@app.get("/{filename}", include_in_schema=False)
def tiktok_verify_file(filename: str):
    """Phục vụ file xác minh URL prefix của TikTok (đặt file vào data/verify/)."""
    import re

    from fastapi.responses import PlainTextResponse

    if not re.fullmatch(r"tiktok[A-Za-z0-9_-]+\.txt", filename):
        return PlainTextResponse("Not found", status_code=404)
    path = os.path.join(VERIFY_DIR, filename)
    if not os.path.isfile(path):
        return PlainTextResponse("Not found", status_code=404)
    with open(path, encoding="utf-8") as f:
        return PlainTextResponse(f.read())
