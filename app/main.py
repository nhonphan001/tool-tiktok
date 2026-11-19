"""Web app quản lý: dashboard, video, phân tích, chiến lược, cài đặt."""
import hmac
import re
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

from . import gemini_requests, mailbox, sku_lookup
from . import analytics, battu, comments, compliance, db, jobs, kpi, notebooklm, packages, pricing, products, report, scanner, scheduler, strategy, tags, tiktok
from .config import DEFAULT_TEXT_KEYS, EDITABLE_KEYS, _default_text, apply_overrides, settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
BASE_DIR = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
def _static_version() -> str:
    """Mã phiên bản file tĩnh: đổi mỗi lần cập nhật để Cloudflare/trình duyệt không dùng CSS cũ."""
    import hashlib
    h = hashlib.md5()
    for name in ("style.css",):
        try:
            with open(os.path.join(BASE_DIR, "static", name), "rb") as f:
                h.update(f.read())
        except OSError:
            pass
    return h.hexdigest()[:8]


templates.env.globals["static_v"] = _static_version()
templates.env.filters["num"] = lambda x: f"{x:,}".replace(",", ".") if isinstance(x, (int, float)) else "—"
templates.env.filters["delta"] = (
    lambda x: "—" if x is None else (("+" if x >= 0 else "") + f"{x:,}".replace(",", "."))
)
templates.env.filters["localtime"] = analytics.localtime
_LATEX = {r"\ge": "≥", r"\geq": "≥", r"\le": "≤", r"\leq": "≤", r"\times": "×", r"\approx": "≈",
          r"\rightarrow": "→", r"\to": "→", r"\Rightarrow": "⇒", r"\pm": "±", r"\neq": "≠",
          r"\%": "%", r"\cdot": "·", r"\sim": "~", r"\,": " ", r"\;": " "}


def _strip_latex(text: str) -> str:
    """Gemini hay viết công thức kiểu $\\ge 4.0\\%$: đổi sang ký tự thường để hiển thị đúng."""
    import re

    def repl(m):
        inner = m.group(1)
        for k in sorted(_LATEX, key=len, reverse=True):
            inner = inner.replace(k, _LATEX[k])
        inner = re.sub(r"\\text\{([^}]*)\}", r"\1", inner)
        return inner.replace("{", "").replace("}", "").strip()

    return re.sub(r"\$([^$\n]*\\[^$\n]*)\$", repl, text or "")


templates.env.filters["markdown"] = lambda t: md.markdown(_strip_latex(t), extensions=["tables", "fenced_code"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.get_conn()
    packages.init()
    apply_overrides(db.load_settings())
    if db.load_settings().get("cost_recomputed") != "v1":  # tính lại chi phí theo bảng giá mới (một lần)
        strategy.recompute_costs()
        db.save_setting("cost_recomputed", "v1")
    if os.getenv("DISABLE_SCHEDULER") != "1":
        scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="TikTok Channel Manager", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

PUBLIC_PATHS = ("/login", "/static", "/healthz", "/auth/tiktok/callback", "/privacy", "/terms", "/tiktok", "/api/public/")


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
            "pending_jobs": (db.query_one(
                "SELECT (SELECT COUNT(*) FROM strategies WHERE status='pending' OR notified=0)"
                " + (SELECT COUNT(*) FROM jobs WHERE status='pending' OR notified=0) AS n"
            ) or {}).get("n", 0),
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
        k=kpi.summary(oid),
        issues=tags.compliance_issues(oid),
        level_labels=compliance.LEVEL_LABELS,
    )


@app.get("/videos", response_class=HTMLResponse)
def videos_page(request: Request, sort: str = "create_time", q: str = "", group: str = "", element: str = "",
                issues: str = "", untagged: str = ""):
    acc = db.get_active_account()
    vids = tags.videos_with_tags(acc["open_id"]) if acc else []
    if q:
        ql = q.lower()
        vids = [v for v in vids if ql in (v["label"] or "").lower() or ql in (v.get("description") or "").lower()]
    if group:
        vids = [v for v in vids if str(v["tag"].get("content_group") or "") == group]
    if element:
        vids = [v for v in vids if v["tag"].get("element") == element]
    if issues:
        vids = [v for v in vids if v["compliance"]["level"] != "ok"]
    if untagged:
        vids = [v for v in vids if not v["tag"]]
    keys = {
        "create_time": lambda v: v.get("create_time") or 0,
        "view_count": lambda v: v["view_count"] or 0,
        "like_count": lambda v: v["like_count"] or 0,
        "comment_count": lambda v: v["comment_count"] or 0,
        "share_count": lambda v: v["share_count"] or 0,
        "engagement": lambda v: v["engagement"],
        "like_view": lambda v: v["like_view"],
        "views_per_day": lambda v: v["views_per_day"],
    }
    vids.sort(key=keys.get(sort, keys["create_time"]), reverse=True)
    return render(
        request, "videos.html", videos=vids, sort=sort, q=q, group=group, element=element, issues=issues,
        untagged=untagged, groups=tags.CONTENT_GROUPS, elements=tags.ELEMENTS, level_labels=compliance.LEVEL_LABELS,
        classify_running=jobs.running("classify"), gemini_ready=bool(settings.gemini_api_key),
    )


@app.post("/videos/classify")
def videos_classify(request: Request):
    acc = db.get_active_account()
    if not acc:
        flash(request, "Chưa kết nối kênh", "error")
    elif jobs.running("classify"):
        flash(request, "Đang phân loại, vui lòng đợi", "info")
    else:
        jobs.start("classify", tags.classify, acc["open_id"])
        flash(request, "Gemini đang phân loại video ở chế độ nền, sẽ có thông báo khi xong.", "info")
    return RedirectResponse("/videos", status_code=303)


@app.get("/videos/{video_id}", response_class=HTMLResponse)
def video_detail(request: Request, video_id: str):
    acc = db.get_active_account()
    v = next((x for x in tags.videos_with_tags(acc["open_id"]) if x["id"] == video_id), None) if acc else None
    if not v:
        return RedirectResponse("/videos", status_code=303)
    return render(
        request, "video_detail.html", v=v, hist=analytics.video_history(video_id), groups=tags.CONTENT_GROUPS,
        elements=tags.ELEMENTS, products=products.all_products(), level_labels=compliance.LEVEL_LABELS,
    )


@app.post("/videos/{video_id}/tags")
async def video_tags_save(request: Request, video_id: str):
    form = await request.form()
    tags.save(video_id, {k: form.get(k, "") for k in tags.FIELDS})
    flash(request, "Đã lưu nhãn video", "success")
    return RedirectResponse(f"/videos/{video_id}", status_code=303)


@app.get("/analytics", response_class=HTMLResponse)
def analytics_page(request: Request):
    acc = db.get_active_account()
    an = analytics.deep_analysis(acc["open_id"]) if acc else None
    ta = tags.tag_analysis(acc["open_id"]) if acc else None
    slots = kpi.slot_performance(acc["open_id"]) if acc else []
    return render(request, "analytics.html", an=an, ta=ta, slots=slots, kpi_min=settings.kpi_like_view_min)


def _parse_time(t: str) -> tuple[int | None, int]:
    t = (t or "").strip()
    if not t:
        return None, 0
    hh, _, mm = t.partition(":")
    return int(hh), int(mm or 0)


def _chart_from_params(q) -> dict:
    h, mi = _parse_time(q.get("t", ""))
    return battu.lap_la_so(int(q.get("dd")), int(q.get("mm")), int(q.get("yy")), h, mi, q.get("gioi") or None,
                           q.get("lich") or "duong", bool(q.get("nhuan")))


@app.get("/laso", response_class=HTMLResponse)
def laso_page(request: Request):
    q = request.query_params
    result = error = None
    if q.get("dd") and q.get("mm") and q.get("yy"):
        try:
            result = _chart_from_params(q)
        except (ValueError, TypeError) as e:
            error = str(e)
    from urllib.parse import urlencode

    return render(request, "laso.html", f=dict(q), result=result, error=error, rows=None, text="",
                  summary=battu.mo_ta_ngan(result) if result else "", qs=urlencode(dict(q)))


@app.post("/laso/comments", response_class=HTMLResponse)
def laso_comments(request: Request, text: str = Form("")):
    # Không lưu bình luận: chỉ phân tích và hiển thị trong phản hồi này
    rows = comments.analyze(text)
    return render(request, "laso.html", f={}, result=None, error=None, rows=rows, text=text, summary="", qs="")


@app.get("/packages", response_class=HTMLResponse)
def packages_page(request: Request):
    items = packages.all_packages()
    for p in items:
        p["chk"] = packages.check(p)
    return render(request, "packages.html", items=items, status=packages.STATUS, loai_short=packages.LOAI_SHORT)


def _package_ctx(p: dict) -> dict:
    acc = db.get_active_account()
    chk = packages.check(p) if p.get("id") else {"items": [], "errors": 0, "warns": 0, "ads_ok": False,
                                                 "chart": packages.chart_of(p)[0], "hanh": "", "product": None}
    from . import post_plan

    req = next((r for r in gemini_requests.all_requests() if p.get("goi") and str(r["goi"]) == str(p.get("goi"))), None)
    slots = sorted((kpi.summary(acc["open_id"]).get("slots") or []) if acc else [], key=lambda s: s.get("avg_views") or 0,
                   reverse=True)
    best = next((s["label"].replace("Khung ", "") for s in slots if s.get("label", "").startswith("Khung")), "")
    plan = post_plan.suggest(p, chk, req, best)
    return {"clips": None, "plan": plan, "plan_fields": post_plan.FIELDS, "p": p, "b": p.get("birth") or {}, "chk": chk, "block": packages.nhan_video_block(p, chk) if p.get("id") else "",
            "loai": packages.LOAI, "status": packages.STATUS, "groups": tags.CONTENT_GROUPS,
            "products": products.all_products(), "videos": analytics.get_videos(acc["open_id"])[:60] if acc else []}


@app.get("/requests", response_class=HTMLResponse)
def requests_page(request: Request):
    reqs = gemini_requests.all_requests()
    return render(request, "requests.html", reqs=reqs, status=gemini_requests.STATUS, goals=gemini_requests.GOALS,
                  loai=packages.LOAI, next_goi=gemini_requests.next_goi(), s=settings,
                  sa=notebooklm.service_account_email())


@app.post("/requests/new")
async def requests_new(request: Request):
    f = await request.form()
    brief = (f.get("brief") or "").strip()
    if not brief:
        flash(request, "Hãy nhập nội dung yêu cầu", "error")
        return RedirectResponse("/requests", status_code=303)
    opts = {"loai": int(f.get("loai") or 3), "goal": f.get("goal") or "follow", "ads": bool(f.get("ads")),
            "ads_days": int(f.get("ads_days") or 7), "publish": (f.get("publish") or "").strip()}
    birth = {k: (f.get(k) or "").strip() for k in ("dd", "mm", "yy", "t", "lich", "gioi")}
    if opts["loai"] == 1:
        opts["ads"] = False  # video lá số không bao giờ chạy quảng cáo
        if birth["dd"] and birth["mm"] and birth["yy"]:
            c, err = packages.chart_of({"birth": birth})
            if err:
                flash(request, f"Ngày giờ sinh không hợp lệ: {err}", "error")
                return RedirectResponse("/requests", status_code=303)
            opts["birth"] = birth
    rid = gemini_requests.create(brief, f.get("title") or "", opts)
    r = gemini_requests.get(rid)
    try:
        msg = gemini_requests.send(rid)
        flash(request, f"Gói {r['goi']}: {msg}", "success")
    except Exception as e:  # noqa: BLE001
        flash(request, f"Đã soạn thư Gói {r['goi']} nhưng chưa gửi được: {e}", "error")
    return RedirectResponse(f"/requests#r{rid}", status_code=303)


@app.post("/requests/{rid}/send")
def requests_send(request: Request, rid: int):
    try:
        flash(request, gemini_requests.send(rid), "success")
    except Exception as e:  # noqa: BLE001
        flash(request, f"Chưa gửi được: {e}", "error")
    return RedirectResponse(f"/requests#r{rid}", status_code=303)


@app.post("/requests/check")
def requests_check(request: Request):
    try:
        done = gemini_requests.check_replies()
        flash(request, ("Thư mới / cập nhật từ Gemini: " + ", ".join(
            f"Gói {d['goi']}" + (" (video thành phẩm)" if d.get("video") else " (đã sửa)" if d.get("updated") else "")
            for d in done)) if done
              else "Chưa có thư trả lời mới.", "success" if done else "info")
    except Exception as e:  # noqa: BLE001
        flash(request, f"Không kiểm tra được hộp thư: {e}", "error")
    return RedirectResponse("/requests", status_code=303)


@app.get("/requests/{rid}.md")
def requests_md(rid: int):
    r = gemini_requests.get(rid)
    if not r:
        return RedirectResponse("/requests", status_code=303)
    return HTMLResponse(r["letter_md"], media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f"attachment; filename={r['code']}__YEUCAU.md"})


@app.get("/packages/import", response_class=HTMLResponse)
def packages_import(request: Request):
    """Liệt kê phiếu gói tìm thấy trong hộp thư Drive (chỉ đọc)."""
    try:
        found, error = mailbox.scan(), None
    except Exception as e:  # noqa: BLE001
        found, error = [], str(e)
    existing = {p["goi"]: p["id"] for p in packages.all_packages() if p.get("goi")}
    for g in found:
        g["existing_id"] = existing.get(g.get("goi"))
    return render(request, "packages_import.html", found=found, error=error, sa=notebooklm.service_account_email())


@app.get("/packages/import/{goi}", response_class=HTMLResponse)
def packages_import_one(request: Request, goi: str):
    """Mở form Gói SX điền sẵn từ hộp thư — CHƯA lưu; người dùng xem lại rồi bấm Lưu & kiểm tra."""
    try:
        g = mailbox.get(goi)
    except Exception as e:  # noqa: BLE001
        flash(request, f"Không đọc được hộp thư: {e}", "error")
        return RedirectResponse("/packages/import", status_code=303)
    if not g:
        flash(request, f"Không tìm thấy Gói {goi} trong hộp thư", "error")
        return RedirectResponse("/packages/import", status_code=303)
    existing = next((p for p in packages.all_packages() if p.get("goi") == str(goi)), None)
    p = {k: g.get(k, "") for k in (*packages.FIELDS, *packages.PROMPTS, *packages.IMAGES, *packages.VIDEOS)}
    p["content_group"] = g.get("content_group") or ""
    p["loai"] = g.get("loai") or 2
    req = next((r for r in gemini_requests.all_requests() if str(r["goi"]) == str(goi)), None)
    p["birth"] = (req or {}).get("opts", {}).get("birth") or {}  # lá số đã gửi trong thư → để B.2 đối chiếu
    if existing:
        p["id"] = existing["id"]
        p["status"] = existing.get("status")
        full = packages.get(existing["id"]) or {}
        for k in (*packages.FIELDS, *packages.PROMPTS, *packages.IMAGES, *packages.VIDEOS, "content_group", "post_plan_json"):
            if not p.get(k) and full.get(k):
                p[k] = full[k]  # thư không có trường này → giữ giá trị đang lưu trong tool
    ctx = _package_ctx({**p, "id": None})
    ctx["p"] = p
    ctx["imported"] = g
    return render(request, "package.html", **ctx)


@app.get("/packages/new", response_class=HTMLResponse)
def package_new(request: Request):
    q = request.query_params
    birth = {k: q.get(k, "") for k in ("dd", "mm", "yy", "t", "lich", "nhuan", "gioi")} if q.get("dd") else {}
    return render(request, "package.html", **_package_ctx({"loai": 1 if birth else 2, "birth": birth}))


@app.get("/media/{pid}/images.zip")
def media_zip(pid: int):
    from fastapi.responses import PlainTextResponse
    from . import media

    p = packages.get(pid)
    if not p:
        return PlainTextResponse("Không có gói", status_code=404)
    try:
        data, errors = media.images_zip(p)
    except Exception as e:  # noqa: BLE001
        return PlainTextResponse(f"Không tải được ảnh: {e}", status_code=502)
    if not data or len(data) < 100:
        return PlainTextResponse("Không tải được ảnh nào. " + " · ".join(errors), status_code=502)
    return HTMLResponse(data, media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="GOI_{p.get("goi") or pid}_anh_4_canh.zip"'})


@app.get("/media/{pid}/{kind}")
def media_file(pid: int, kind: str, download: int = 0):
    from fastapi.responses import FileResponse, PlainTextResponse
    from . import media

    p = packages.get(pid)
    fid = media.file_id_for(p or {}, kind)
    if not fid:
        return PlainTextResponse("Không có file", status_code=404)
    try:
        path, meta = media.fetch(fid)
    except Exception as e:  # noqa: BLE001
        return PlainTextResponse(str(e), status_code=502)
    name = re.sub(r'[^\w.\- ]', "_", meta["name"])
    return FileResponse(path, media_type=meta["mimeType"], headers={
        "Content-Disposition": f'{"attachment" if download else "inline"}; filename="{name}"',
        "Cache-Control": "private, max-age=86400"})


@app.get("/packages/{pid}/phieu.md")
def package_markdown(pid: int):
    p = packages.get(pid)
    if not p:
        return RedirectResponse("/packages", status_code=303)
    text = packages.to_markdown(p, packages.check(p))
    fname = f"PHIEU_GOI_{(p.get('goi') or pid)}.md".replace(" ", "_")
    return HTMLResponse(text, media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f"attachment; filename={fname}"})


_RAW_CACHE: dict = {"t": 0.0, "files": None, "err": ""}


def _raw_files(force: bool = False) -> tuple[list, str]:
    """Danh sách clip thô trong thư mục 02 (đệm 60 giây)."""
    import time

    from . import clips

    if force or _RAW_CACHE["files"] is None or time.time() - _RAW_CACHE["t"] > 60:
        try:
            _RAW_CACHE.update(files=clips.list_raw(), err="", t=time.time())
        except Exception as e:  # noqa: BLE001
            _RAW_CACHE.update(files=[], err=str(e)[:200], t=time.time())
    return _RAW_CACHE["files"] or [], _RAW_CACHE["err"]


@app.get("/packages/{pid}", response_class=HTMLResponse)
def package_detail(request: Request, pid: int):
    from . import clips

    p = packages.get(pid)
    if not p:
        return RedirectResponse("/packages", status_code=303)
    files, raw_err = _raw_files()
    cl, new = clips.sync(p, files)
    if new:
        clips.save(pid, cl)
        p = packages.get(pid)
    ctx = _package_ctx(p)
    ghep = next((r for r in gemini_requests.all_requests()
                 if str(r["goi"]) == str(p.get("goi")) and r["opts"].get("kind") == "ghep"), None)
    ctx.update(clips=cl, clip_status=clips.STATUS, clips_ok=clips.all_ok(cl), raw_err=raw_err, ghep=ghep,
               req_status=gemini_requests.STATUS)
    return render(request, "package.html", **ctx)


@app.post("/packages/{pid}/clips/sync")
def package_clips_sync(request: Request, pid: int):
    files, err = _raw_files(force=True)
    flash(request, f"Không đọc được thư mục 02: {err}" if err else f"Đã quét thư mục 02 ({len(files)} clip).",
          "error" if err else "info")
    return RedirectResponse(f"/packages/{pid}#clips", status_code=303)


@app.post("/packages/{pid}/clips/{scene}")
def package_clip_status(request: Request, pid: int, scene: str, status: str = Form(...), note: str = Form("")):
    from . import clips

    try:
        clips.set_status(pid, scene, status, note)
        flash(request, f"Cảnh {scene}: {clips.STATUS.get(status, status)}", "success" if status == "dat" else "info")
    except ValueError as e:
        flash(request, str(e), "error")
    return RedirectResponse(f"/packages/{pid}#clips", status_code=303)


@app.post("/packages/{pid}/ghep")
def package_ghep(request: Request, pid: int):
    from . import clips

    p = packages.get(pid)
    cl = clips.load(p or {})
    if not p or not clips.all_ok(cl):
        flash(request, "Cần duyệt ĐẠT đủ 4 cảnh trước khi gửi Gemini ghép", "error")
        return RedirectResponse(f"/packages/{pid}#clips", status_code=303)
    code, letter = clips.ghep_letter(p, cl)
    rid = gemini_requests.create_ghep(p["goi"], code, f"Ghép video Gói {p['goi']}", letter)
    try:
        flash(request, "Đã gửi yêu cầu ghép cho Gemini: " + gemini_requests.send(rid), "success")
    except Exception as e:  # noqa: BLE001
        flash(request, f"Đã soạn thư ghép nhưng chưa gửi được: {e}", "error")
    return RedirectResponse(f"/packages/{pid}#clips", status_code=303)


@app.post("/packages/save")
async def package_save(request: Request):
    form = await request.form()
    from . import post_plan

    data = {k: form.get(k, "") for k in (*packages.FIELDS, *packages.PROMPTS, *packages.IMAGES, *packages.VIDEOS,
                                         "dd", "mm", "yy", "t", "lich", "nhuan", "gioi", "status")}
    if any(k.startswith("plan_") for k in form.keys()):
        data["post_plan_json"] = post_plan.from_form(form)
    pid = packages.save(data, int(form["id"]) if form.get("id") else None)
    if data.get("goi"):
        gemini_requests.mark_imported(data["goi"])
    chk = packages.check(packages.get(pid))
    flash(request, f"Đã lưu gói. Kiểm tra: {chk['errors']} lỗi, {chk['warns']} cảnh báo.",
          "success" if not chk["errors"] else "error")
    return RedirectResponse(f"/packages/{pid}", status_code=303)


@app.post("/packages/{pid}/delete")
def package_delete(request: Request, pid: int):
    packages.delete(pid)
    flash(request, "Đã xoá gói", "info")
    return RedirectResponse("/packages", status_code=303)


@app.post("/packages/{pid}/link")
def package_link(request: Request, pid: int, video_id: str = Form(...)):
    packages.link_video(pid, video_id)
    flash(request, "Đã gắn video và ghi nhãn theo gói", "success")
    return RedirectResponse(f"/packages/{pid}", status_code=303)


@app.get("/compliance", response_class=HTMLResponse)
def compliance_page(request: Request):
    acc = db.get_active_account()
    return render(
        request, "compliance.html", issues=tags.compliance_issues(acc["open_id"]) if acc else [],
        result=request.session.pop("check_result", None), level_labels=compliance.LEVEL_LABELS,
        allowed=compliance.ALLOWED_CTA, rules=settings.content_rules,
    )


@app.post("/compliance/check")
def compliance_check(request: Request, text: str = Form(""), has_cart: str = Form("1")):
    cart = {"1": True, "0": False}.get(has_cart)
    res = compliance.check(text, cart)
    request.session["check_result"] = {"text": text[:5000], "has_cart": has_cart, **res}
    return RedirectResponse("/compliance#ket-qua", status_code=303)


@app.get("/products", response_class=HTMLResponse)
def products_page(request: Request):
    items = products.all_products()
    acc = db.get_active_account()
    usage = {}
    if acc:
        for v in tags.videos_with_tags(acc["open_id"]):
            code = v["tag"].get("product_code")
            if code:
                u = usage.setdefault(code, {"count": 0, "views": 0})
                u["count"] += 1
                u["views"] += v["view_count"] or 0
    for it in items:
        it["audit"] = products.audit(it)
        it["real_link"] = products.real_link(it.get("link") or "")
    return render(
        request, "products.html", items=items, usage=usage, s=settings, running=jobs.running("products"),
        new=request.session.get("new_sku") or {}, elements=tags.ELEMENTS,
        synced=items[0]["synced_at"] if items else None,
    )


@app.post("/products/autofill")
def products_autofill(request: Request, link: str = Form(""), name: str = Form("")):
    """Dán link sản phẩm -> tự điền form Thêm SKU (CHƯA ghi vào bảng; người dùng duyệt rồi bấm Thêm)."""
    try:
        data = sku_lookup.suggest(link=link, title=name.strip())
        request.session["new_sku"] = data
        _, errors, warns = products.validate_new(data)
        msg = f"Đã tự điền {data['code']} ({data['_auto']}). Kiểm tra lại các ô, điền GIÁ, rồi bấm “Thêm vào bảng”."
        if errors:
            msg += " Cần sửa: " + " · ".join(errors)
        elif warns:
            msg += " Lưu ý: " + " · ".join(warns)
        flash(request, msg, "error" if errors else "success")
    except Exception as e:  # noqa: BLE001
        request.session["new_sku"] = {"link": link, "name": name}
        flash(request, f"Không tự điền được: {e}", "error")
    return RedirectResponse("/products#add", status_code=303)


@app.post("/products/add")
async def products_add(request: Request):
    form = dict(await request.form())
    if form.get("preview"):
        d, errors, warns = products.validate_new(form)
        request.session["new_sku"] = form
        flash(request, ("Chưa ghi. " + " · ".join(errors)) if errors else
              ("Kiểm tra đạt" + (" (cảnh báo: " + " · ".join(warns) + ")" if warns else "") + ". Bấm “Thêm vào bảng” để ghi."),
              "error" if errors else "success")
        return RedirectResponse("/products#add", status_code=303)
    try:
        msg = products.append_row(form)
        request.session.pop("new_sku", None)
        flash(request, msg, "success")
    except Exception as e:  # noqa: BLE001
        request.session["new_sku"] = form
        flash(request, f"Chưa ghi vào bảng: {e}", "error")
    return RedirectResponse("/products#add", status_code=303)


@app.post("/products/sync")
def products_sync(request: Request):
    if jobs.running("products"):
        flash(request, "Đang đồng bộ, vui lòng đợi", "info")
    else:
        jobs.start("products", products.sync)
        flash(request, "Đang đọc bảng sản phẩm ở chế độ nền (chỉ đọc, không sửa bảng).", "info")
    return RedirectResponse("/products", status_code=303)


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
        endpoint_labels=strategy.ENDPOINT_LABELS, endpoint_now=strategy.ENDPOINT_LABELS[strategy.planned_endpoint()],
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


FILES_DIR = os.path.join(BASE_DIR, "files")
DOC_TITLES = {
    "QUY_TRINH_CHOT_V2.pdf": ("Quy trình luồng tự động – bản chốt V2 (PDF, 10 trang)",
                              "Kiến trúc, lịch tự động, luồng sản xuất, cổng tuân thủ, hộp thư, Gói 16, quy trình chốt P1–P13"),
    "QUY_TRINH_CHOT_V2.md": ("Quy trình chốt V2 (văn bản)", "Bảng P1–P13, P8a/P8b, quy tắc C.10a, thư mục Drive"),
    "SAO_LUU_VA_KHOI_PHUC.md": ("Sao lưu & khôi phục hệ thống", "Cách sao lưu VPS, khôi phục khi hỏng / mất GitHub"),
}


@app.get("/tai-lieu", response_class=HTMLResponse)
def docs_page(request: Request):
    files = [n for n in DOC_TITLES if os.path.exists(os.path.join(FILES_DIR, n))]
    return render(request, "docs.html", files=files, titles=DOC_TITLES)


@app.get("/tai-lieu/{name}")
def docs_file(name: str, download: int = 0):
    from fastapi.responses import FileResponse, PlainTextResponse

    if name not in DOC_TITLES or not os.path.exists(os.path.join(FILES_DIR, name)):
        return PlainTextResponse("Không có tài liệu này", status_code=404)
    path = os.path.join(FILES_DIR, name)
    if name.endswith(".md") and not download:
        return RedirectResponse(f"/tai-lieu/xem/{name}", status_code=303)
    media = "application/pdf" if name.endswith(".pdf") else "text/markdown; charset=utf-8"
    disp = "attachment" if download else "inline"
    return FileResponse(path, media_type=media, headers={"Content-Disposition": f'{disp}; filename="{name}"'})


@app.get("/tai-lieu/xem/{name}", response_class=HTMLResponse)
def docs_view(request: Request, name: str):
    if name not in DOC_TITLES or not name.endswith(".md"):
        return RedirectResponse("/tai-lieu", status_code=303)
    with open(os.path.join(FILES_DIR, name), encoding="utf-8") as f:
        text = f.read()
    text = text.split("---", 2)[2] if text.startswith("---") else text
    return render(request, "report.html", text=text, title=DOC_TITLES[name][0], md_url=f"/tai-lieu/{name}?download=1")


@app.get("/system", response_class=HTMLResponse)
def system_page(request: Request):
    from . import system_report

    return render(request, "report.html", text=system_report.to_markdown(), title="Báo cáo hệ thống",
                  md_name="BAOCAO_HE_THONG_TIKTOK_MANAGER.md", md_url="/api/system.md")


@app.get("/api/system.md")
def system_md(request: Request):
    from . import system_report

    return HTMLResponse(system_report.to_markdown(), media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": "attachment; filename=BAOCAO_HE_THONG_TIKTOK_MANAGER.md"})


@app.get("/api/public/system.md")
def api_public_system(request: Request):
    """Báo cáo tự động tình trạng hệ thống (cần API_TOKEN)."""
    if not _check_token(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401, headers=CORS)
    from . import system_report

    return HTMLResponse(system_report.to_markdown(), media_type="text/markdown; charset=utf-8", headers=CORS)


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
        scan_mode=scheduler.describe(),
        scans=db.query("SELECT * FROM scans ORDER BY id DESC LIMIT 20"),
        syncs=db.query("SELECT * FROM sync_log ORDER BY id DESC LIMIT 20"),
        sa_email=notebooklm.service_account_email(),
        price_now=pricing.price_for(settings.gemini_model, strategy.planned_endpoint()),
        endpoint_now=strategy.ENDPOINT_LABELS[strategy.planned_endpoint()],
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
            if key in DEFAULT_TEXT_KEYS and val == _default_text(*DEFAULT_TEXT_KEYS[key]).strip():
                val = ""  # giống mặc định -> lưu trống để luôn theo bản mặc định mới nhất
        else:
            continue
        db.save_setting(key, val)
    apply_overrides(db.load_settings())
    scheduler.reschedule()
    flash(request, "Đã lưu cài đặt", "success")
    return RedirectResponse("/settings", status_code=303)


@app.post("/settings/test-drive")
def settings_test_drive(request: Request):
    res = notebooklm.check_drive()
    ok = all(r["ok"] for r in res)
    msg = " · ".join(("✓ " if r["ok"] else "✗ ") + r["msg"] for r in res)
    acc = db.get_active_account()
    if ok and acc:
        synced = notebooklm.sync_all(acc["open_id"])
        drive = [x for x in synced if x["target"].startswith("drive:")]
        if not drive:
            msg += " · Chế độ đồng bộ chưa có “drive” nên chưa ghi thử."
        else:
            msg += " · Ghi thử: " + ", ".join(f"{x['target']} {x['status']}" for x in drive)
            ok = all(x["status"] == "ok" for x in drive)
    flash(request, msg, "success" if ok else "error")
    return RedirectResponse("/settings", status_code=303)


@app.post("/settings/recompute-costs")
def settings_recompute_costs(request: Request):
    n = strategy.recompute_costs()
    flash(request, f"Đã tính lại chi phí cho {n} bản ghi theo giá hiện tại", "success")
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
    """Trạng thái tác vụ chạy ngầm; trả về tác vụ vừa xong (mỗi tác vụ chỉ thông báo 1 lần)."""
    pending = [p["id"] for p in db.query("SELECT id FROM strategies WHERE status='pending'")]
    pending += [f"job{p['id']}" for p in db.query("SELECT id FROM jobs WHERE status='pending'")]
    finished = db.query(
        "SELECT id, source, status, total_tokens, cost_usd, duration_sec, endpoint, endpoint_note FROM strategies"
        " WHERE status!='pending' AND notified=0"
    )
    done_jobs = db.query("SELECT * FROM jobs WHERE status!='pending' AND notified=0")
    with db.tx() as c:
        c.executemany("UPDATE strategies SET notified=1 WHERE id=?", [(f["id"],) for f in finished])
        c.executemany("UPDATE jobs SET notified=1 WHERE id=?", [(j["id"],) for j in done_jobs])
    for f in finished:
        f["type"] = "strategy"
        f["endpoint_label"] = strategy.ENDPOINT_LABELS.get(f["endpoint"] or "", f["endpoint"] or "")
        f["cost_vnd"] = round((f["cost_usd"] or 0) * settings.usd_vnd_rate)
    links = {"classify": "/videos", "products": "/products"}
    for j in done_jobs:
        finished.append({
            "type": "job", "id": j["id"], "status": j["status"], "title": jobs.KIND_LABELS.get(j["kind"], j["kind"]),
            "message": j["message"], "link": j.get("link") or links.get(j["kind"], "/"), "total_tokens": j["total_tokens"],
            "cost_vnd": round((j["cost_usd"] or 0) * settings.usd_vnd_rate),
        })
    return {"pending": pending, "finished": finished}


def _check_token(request: Request) -> bool:
    supplied = request.headers.get("x-api-token") or request.query_params.get("token") or ""
    return bool(settings.api_token) and hmac.compare_digest(supplied.encode(), settings.api_token.encode())


CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "x-api-token", "Cache-Control": "no-store"}


@app.options("/api/public/{rest:path}", include_in_schema=False)
def api_public_options(rest: str):
    return JSONResponse({}, headers={**CORS, "Access-Control-Allow-Methods": "GET, OPTIONS"})


def _public_summary() -> dict | None:
    acc = db.get_active_account()
    if not acc:
        return None
    oid = acc["open_id"]
    ov = analytics.overview(oid)
    vids = tags.videos_with_tags(oid)
    last_scan = db.query_one("SELECT started_at, status, message FROM scans ORDER BY id DESC LIMIT 1")
    return {
        "channel": {"username": acc.get("username"), "display_name": acc.get("display_name")},
        "source": "TikTok API (số chính xác, không làm tròn)",
        "updated_at": ov.get("latest", {}).get("taken_at") if ov.get("latest") else None,
        "latest": ov.get("latest"),
        "deltas": ov.get("deltas"),
        "avg_views": ov.get("avg_views"),
        "avg_engagement": ov.get("avg_engagement"),
        "kpi": kpi.summary(oid),
        "compliance_issues": [
            {"id": v["id"], "posted": v["posted_str"], "title": v["label"], "level": v["compliance"]["level"],
             "found": [x["label"] for x in v["compliance"]["offsite"] + v["compliance"]["promise"]]}
            for v in vids if v["compliance"]["level"] != "ok"
        ],
        "videos": [
            {"id": v["id"], "posted": v["posted_str"], "title": v["label"], "share_url": v["share_url"],
             "views": v["view_count"], "likes": v["like_count"], "comments": v["comment_count"],
             "shares": v["share_count"], "like_view": v["like_view"], "tag": {k: v["tag"].get(k) for k in tags.FIELDS}}
            for v in vids[:100]
        ],
        "last_scan": last_scan,
    }


@app.get("/api/public/summary")
def api_public_summary(request: Request):
    """Số liệu chỉ-đọc cho bảng điều hành khác (cần API_TOKEN)."""
    if not _check_token(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401, headers=CORS)
    data = _public_summary()
    if data is None:
        return JSONResponse({"error": "no_account"}, status_code=404, headers=CORS)
    return JSONResponse(data, headers=CORS)


@app.get("/api/public/dashboard/{name}.json")
def api_public_dashboard_file(request: Request, name: str):
    """Tệp số liệu {rows, meta} dựng sẵn cho Bảng điều hành kênh (cần API_TOKEN)."""
    from . import dashboard_export

    if not _check_token(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401, headers=CORS)
    if name not in dashboard_export.NAMES:
        return JSONResponse({"error": "unknown", "names": list(dashboard_export.NAMES)}, status_code=404, headers=CORS)
    data = _public_summary()
    if data is None:
        return JSONResponse({"error": "no_account"}, status_code=404, headers=CORS)
    return JSONResponse(dashboard_export.build(data)[name], headers=CORS)


@app.get("/api/public/laso")
def api_public_laso(request: Request):
    """Lập lá số cho Gemini/công cụ khác: ?dd=5&mm=6&yy=1995&t=18:00&lich=duong|am&nhuan=1&gioi=nu (cần API_TOKEN)."""
    if not _check_token(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401, headers=CORS)
    try:
        r = _chart_from_params(request.query_params)
    except (ValueError, TypeError) as e:
        return JSONResponse({"error": str(e)}, status_code=400, headers=CORS)
    return JSONResponse({**r, "tom_tat": battu.mo_ta_ngan(r)}, headers=CORS)


@app.get("/api/public/report.md")
def api_public_report(request: Request):
    """Báo cáo Markdown đầy đủ cho Gemini đọc (cần API_TOKEN)."""
    if not _check_token(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401, headers=CORS)
    acc = db.get_active_account()
    text = report.build_report(acc["open_id"]) if acc else "Chưa kết nối kênh"
    return HTMLResponse(text, media_type="text/markdown; charset=utf-8", headers=CORS)


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
