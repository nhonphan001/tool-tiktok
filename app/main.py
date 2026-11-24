"""Web app quản lý: dashboard, video, phân tích, chiến lược, cài đặt."""
import hmac
import re
import logging
import os
import threading
from contextlib import asynccontextmanager

import markdown as md
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
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


log = logging.getLogger(__name__)
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
    from . import unread

    try:
        badges, seen_before = unread.visit(request.url.path)
    except Exception:  # noqa: BLE001
        log.exception("unread")
        badges, seen_before = {}, ""

    def is_new(ts) -> bool:  # mục mới hơn lần xem trước của khu đang mở → chấm đỏ
        return bool(seen_before and ts and str(ts)[:19].replace(" ", "T") > seen_before[:19])

    ctx.setdefault("badges", badges)
    ctx.setdefault("seen_before", seen_before)
    ctx.setdefault("is_new", is_new)
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


def _laso_row(text: str, line: int) -> dict | None:
    return next((r for r in comments.analyze(text) if r.get("line") == line and r.get("chart")), None)


@app.post("/api/laso/reply")
def laso_reply(text: str = Form(""), line: int = Form(...)):
    """Trả lời nhanh bằng Gemini cho 1 dòng đã lập được lá số (gọi bằng fetch, trang không tải lại)."""
    from . import comment_reply

    row = _laso_row(text, line)
    if not row:
        return JSONResponse({"error": "Dòng này chưa lập được lá số"}, status_code=400)
    if not settings.gemini_api_key and settings.gemini_backend != "vertex":
        return JSONResponse({"error": "Chưa cấu hình Gemini API (Cài đặt → Gemini)"}, status_code=400)
    try:
        return comment_reply.draft_reply(text, row["chart"])
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": str(e)[:300]}, status_code=502)


@app.post("/laso/package")
def laso_package(request: Request, text: str = Form(""), line: int = Form(...)):
    """Điền sẵn form Yêu cầu Gemini (Loại 1, nhóm 4, kèm ngày giờ sinh) từ tin nhắn khách."""
    from . import comment_reply

    row = _laso_row(text, line)
    if not row:
        flash(request, "Dòng này chưa lập được lá số", "error")
        return RedirectResponse("/laso", status_code=303)
    request.session["pre_request"] = comment_reply.package_prefill(text, row)
    return RedirectResponse("/requests#moi", status_code=303)


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
    events: dict[str, str] = {}  # gói → lần cuối Gemini gửi phiếu / sửa / video
    for r in gemini_requests.all_requests():
        t = max(str(r.get(k) or "")[:19] for k in ("answered_at", "answer_modified", "video_seen"))
        if t > events.get(str(r["goi"]), ""):
            events[str(r["goi"])] = t
    for p in items:
        p["chk"] = packages.check(p)
        p["event_at"] = events.get(str(p.get("goi")), "")
    known = {str(p.get("goi")) for p in items}
    waiting = sorted((g for g in events if g not in known), key=lambda x: int(x) if x.isdigit() else 0)
    return render(request, "packages.html", items=items, status=packages.STATUS, loai_short=packages.LOAI_SHORT,
                  events=events, waiting=waiting)


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
    sua = [r for r in gemini_requests.all_requests()
           if p.get("goi") and str(r["goi"]) == str(p.get("goi")) and r["opts"].get("kind") == "sua"]
    syl_lo, syl_hi = packages.syllable_range()
    return {"clips": None, "nsc": packages.n_scenes(p), "max_sc": packages.MAX_SCENES, "sua_reqs": sua, "req_status": gemini_requests.STATUS, "clip_s": packages.clip_seconds(),
            "syl_lo": syl_lo, "syl_hi": syl_hi, "plan": plan, "plan_fields": post_plan.FIELDS, "p": p, "b": p.get("birth") or {}, "chk": chk, "block": packages.nhan_video_block(p, chk) if p.get("id") else "",
            "loai": packages.LOAI, "status": packages.STATUS, "groups": tags.CONTENT_GROUPS,
            "products": products.all_products(), "videos": analytics.get_videos(acc["open_id"])[:60] if acc else [],
            **_chrome_ctx(p)}


def _chrome_ctx(p: dict) -> dict:
    from . import chrome_reports

    if not p.get("id"):
        return {"chrome_req": "", "chrome_rows": []}
    return {"chrome_req": chrome_reports.video_request(p), "chrome_rows": chrome_reports.list_reports(p["id"])}


@app.get("/requests", response_class=HTMLResponse)
def requests_page(request: Request, sid: int | None = None, row: int | None = None):
    from . import strategy_plan

    reqs = gemini_requests.all_requests()
    pre = request.session.pop("pre_request", None) or {}  # "Tạo gói SX" từ trang Lá số
    if sid is not None and row is not None:  # "Tạo gói" từ lịch 7 ngày của chiến lược
        st = db.query_one("SELECT content_md FROM strategies WHERE id=?", (sid,))
        rows = strategy_plan.parse_schedule((st or {}).get("content_md") or "")
        if 0 <= row < len(rows):
            pre = {**strategy_plan.prefill(rows[row]), "plan_key": f"{sid}:{row}", "warnings": rows[row]["warnings"]}
    return render(request, "requests.html", reqs=reqs, status=gemini_requests.STATUS, goals=gemini_requests.GOALS,
                  loai=packages.LOAI, next_goi=gemini_requests.next_goi(), s=settings,
                  sa=notebooklm.service_account_email(), pre=pre)


@app.post("/requests/new")
async def requests_new(request: Request):
    f = await request.form()
    brief = (f.get("brief") or "").strip()
    if not brief:
        flash(request, "Hãy nhập nội dung yêu cầu", "error")
        return RedirectResponse("/requests", status_code=303)
    opts = {"loai": int(f.get("loai") or 3), "goal": f.get("goal") or "follow", "ads": bool(f.get("ads")),
            "ads_days": int(f.get("ads_days") or 7), "publish": (f.get("publish") or "").strip(),
            "scenes": min(max(int(f.get("scenes") or 4), 4), packages.MAX_SCENES)}
    if f.get("plan_key"):
        opts["plan_key"] = str(f.get("plan_key"))[:40]  # dòng lịch 7 ngày đã tạo gói
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
    _send_bg(rid, f"/requests#r{rid}")
    flash(request, f"Đã giữ số Gói {r['goi']} và soạn thư — đang gửi cho Gemini chạy ngầm, xong tool sẽ báo.", "success")
    return RedirectResponse(f"/requests#r{rid}", status_code=303)


def _send_bg(rid: int, link: str) -> int:
    """Gửi thư yêu cầu vào hộp thư Gemini ở luồng nền."""
    r = gemini_requests.get(rid) or {}
    return jobs.start("send", lambda: f"{r.get('code', '')}: {gemini_requests.send(rid)}", link=link)


@app.post("/requests/{rid}/send")
def requests_send(request: Request, rid: int):
    _send_bg(rid, f"/requests#r{rid}")
    flash(request, "Đang gửi lại thư chạy ngầm — xong tool sẽ báo.", "info")
    return RedirectResponse(f"/requests#r{rid}", status_code=303)


@app.post("/requests/check")
def requests_check(request: Request):
    def _check():
        done = gemini_requests.check_replies()
        return ("Thư mới / cập nhật từ Gemini: " + ", ".join(
            f"Gói {d['goi']}" + (" (video thành phẩm)" if d.get("video") else " (đã sửa)" if d.get("updated") else "")
            for d in done)) if done else "Chưa có thư trả lời mới."
    jobs.start("mail_check", _check, link="/requests")
    flash(request, "Đang kiểm tra hộp thư chạy ngầm — xong tool sẽ báo.", "info")
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


@app.get("/media/{pid}/clips.zip")
def media_clips_zip(pid: int):
    import io as _io
    import zipfile as _zip

    from fastapi.responses import PlainTextResponse
    from . import clips as _clips, media, veo as _veo

    p = packages.get(pid)
    if not p:
        return PlainTextResponse("Không có gói", status_code=404)
    buf = _io.BytesIO()
    with _zip.ZipFile(buf, "w", _zip.ZIP_STORED) as z:
        for k, c in sorted(_clips.load(p).items()):
            cid = str(c.get("id") or "")
            try:
                path = _veo.local_path(cid) if cid.startswith("veo:") else (media.fetch(cid)[0] if cid else "")
            except Exception:  # noqa: BLE001
                path = ""
            if path and os.path.exists(path):
                z.write(path, c.get("name") or f"Goi_{p.get('goi')}_canh_{k}.mp4")
        from . import tts as _tts

        for k in range(1, packages.n_scenes(p) + 1):  # giọng TTS từng cảnh (phương án B) đi kèm để Gemini ghép
            vp = _tts.scene_file(p.get("goi"), k)
            if os.path.exists(vp):
                z.write(vp, _tts.scene_name(p.get("goi"), k))
    if buf.tell() < 100:
        return PlainTextResponse("Chưa có clip nào", status_code=404)
    return HTMLResponse(buf.getvalue(), media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="Goi_{p.get("goi")}_4_clip_tho.zip"'})


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
    if kind in ("giong1", "giong2", "giong3", "giong4") and p:
        from . import tts as _tts

        path = _tts.scene_file(p.get("goi"), int(kind[-1]))
        if not os.path.exists(path):
            return PlainTextResponse("Chưa có file giọng", status_code=404)
        return FileResponse(path, media_type="audio/wav", headers={
            "Content-Disposition": f'{"attachment" if download else "inline"}; filename="{os.path.basename(path)}"',
            "Cache-Control": "no-store"})
    if kind.startswith("clip") and p:
        from . import clips as _clips, veo as _veo

        cid = (_clips.load(p).get(kind[4:]) or {}).get("id") or ""
        if cid.startswith("veo:"):
            path = _veo.local_path(cid)
            if not path or not os.path.exists(path):
                return PlainTextResponse("Không còn file Veo trên máy chủ", status_code=404)
            return FileResponse(path, media_type="video/mp4", headers={
                "Content-Disposition": f'{"attachment" if download else "inline"}; filename="{os.path.basename(path)}"'})
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
    from . import veo

    from . import tts

    ok, why = veo.ready()
    tts_ok, tts_why = tts.ready()
    vk = tts.voice_key()
    ctx.update(clips=cl, clip_status=clips.STATUS, clips_ok=clips.all_ok(cl), raw_err=raw_err, ghep=ghep,
               req_status=gemini_requests.STATUS, veo_ok=ok, veo_why=why, veo_one=veo.estimate(1),
               veo_all=veo.estimate(packages.n_scenes(p)), veo_one_b=veo.estimate(1, False), veo_all_b=veo.estimate(packages.n_scenes(p), False),
               veo_running=veo.running(pid), tts_ok=tts_ok, tts_why=tts_why,
               tts_voice=tts.VOICES[vk][2] if vk else "", tts_scenes=tts.scene_info(p),
               tts_usd=tts.estimate_scenes(p))
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


@app.post("/packages/{pid}/veo")
def package_veo(request: Request, pid: int, scenes: str = Form(...), confirm_usd: str = Form(""),
                audio: str = Form("1")):
    from . import veo

    sc = [s for s in scenes.split(",") if s in [str(i) for i in range(1, packages.MAX_SCENES + 1)]]
    au = audio != "0"
    est = veo.estimate(len(sc), au)
    if not sc:
        flash(request, "Chưa chọn cảnh", "error")
    elif confirm_usd != f"{est['usd']:.2f}":
        flash(request, "Giá đã thay đổi, hãy xác nhận lại", "error")
    elif veo.running(pid):
        flash(request, "Veo đang chạy cho gói này, đợi xong rồi tạo tiếp", "info")
    else:
        try:
            veo.start(pid, sc, au)
            vnd = f"{est['vnd']:,}".replace(",", ".")
            flash(request, f"Đã gửi Veo tạo cảnh {', '.join(sc)} ({est['model']} {est['resolution']}"
                           f"{'' if au else ', không tiếng'}, ≈ ${est['usd']:.2f} ≈ "
                           f"{vnd}đ). Mỗi clip mất khoảng 1–3 phút; tool sẽ báo khi xong.", "success")
        except Exception as e:  # noqa: BLE001
            flash(request, f"Không chạy được Veo: {e}", "error")
    return RedirectResponse(f"/packages/{pid}#clips", status_code=303)


@app.post("/packages/{pid}/giong")
def package_voice(request: Request, pid: int):
    from . import tts

    p = packages.get(pid)
    if not p:
        return RedirectResponse("/packages", status_code=303)
    def _tts():
        r = tts.make_scenes(p)
        if not r["done"]:
            raise RuntimeError("Chưa tạo được giọng. " + " · ".join(r["errors"]))
        return (f"Đã tạo giọng {r['voice']} cho cảnh {', '.join(r['done'])} Gói {p.get('goi')}."
                + (" Lỗi: " + " · ".join(r["errors"]) if r["errors"] else ""))
    jobs.start("tts", _tts, link=f"/packages/{pid}#clips")
    flash(request, "Đang tạo giọng các cảnh chạy ngầm — xong tool sẽ báo.", "info")
    return RedirectResponse(f"/packages/{pid}#clips", status_code=303)


@app.get("/hop-thu")
def mail_notes_page(request: Request, k: str = ""):
    from . import mail_notes

    notes = mail_notes.all_notes()
    if k:
        notes = [n for n in notes if n["kind"] == k or n["sender"].lower() == k]
    return render(request, "mail_notes.html", active="mail", notes=notes, changes=mail_notes.changes(),
                  kinds=mail_notes.KIND_LABELS, status=mail_notes.STATUS, whitelist=mail_notes.WHITELIST,
                  auto=settings.auto_apply_updates, k=k)


@app.post("/hop-thu/quet")
def mail_notes_scan(request: Request):
    from . import mail_notes

    def _scan():
        got = mail_notes.scan()
        return f"Đã đọc {len(got)} thư mới/vừa sửa." if got else "Không có thư mới."
    jobs.start("mail_notes", _scan, link="/hop-thu")
    flash(request, "Đang đọc hộp thư chạy ngầm — xong tool sẽ báo, tải lại trang để xem.", "info")
    return RedirectResponse("/hop-thu", status_code=303)


@app.post("/hop-thu/{file_id}/{key}")
def mail_notes_decide(request: Request, file_id: str, key: str, action: str = Form(...)):
    from . import mail_notes

    try:
        flash(request, mail_notes.decide(file_id, key, action), "success")
    except ValueError as e:
        flash(request, str(e), "error")
    return RedirectResponse("/hop-thu#n-" + file_id, status_code=303)


@app.post("/hop-thu/hoan-tac/{cid}")
def mail_notes_revert(request: Request, cid: int):
    from . import mail_notes

    try:
        flash(request, mail_notes.revert(cid), "success")
    except ValueError as e:
        flash(request, str(e), "error")
    return RedirectResponse("/hop-thu#nhat-ky", status_code=303)


@app.post("/hop-thu/tu-dong")
def mail_notes_toggle(request: Request, on: str = Form("")):
    db.save_setting("auto_apply_updates", "true" if on else "false")
    apply_overrides(db.load_settings())
    flash(request, "Đã BẬT tự áp dụng cập nhật an toàn (giờ đăng, KPI)." if on else "Đã TẮT tự áp dụng — mọi cập nhật chờ anh duyệt.",
          "success")
    return RedirectResponse("/hop-thu", status_code=303)


@app.get("/tom-tat")
def summaries_page(request: Request):
    from . import cycle_summary

    return render(request, "summaries.html", active="strategy", rows=cycle_summary.all_rows(),
                  doc_g=settings.summary_doc_gemini, doc_c=settings.summary_doc_claude)


@app.get("/danh-gia", response_class=HTMLResponse)
def chrome_page(request: Request, days: int = 7):
    from . import chrome_reports

    days = max(1, min(days, 30))
    return render(request, "chrome_reports.html", active="chrome", rows=chrome_reports.list_reports(),
                  week=chrome_reports.week_request(days), days=days, ads_paused=settings.ads_paused,
                  pk={p["id"]: p for p in packages.all_packages()})


@app.get("/danh-gia/gio")
def chrome_clock():
    """Mốc giờ cho skill tiktok-studio-quet ghi lúc bắt đầu và kết thúc."""
    from . import chrome_reports

    return HTMLResponse(chrome_reports.clock_text(), media_type="text/plain; charset=utf-8")


@app.get("/danh-gia/ngu-canh")
def chrome_context(days: int = 14):
    """Trang văn bản cho skill Claude in Chrome đọc (cần đăng nhập TikTok Manager)."""
    from . import chrome_reports

    return HTMLResponse(chrome_reports.context_md(max(1, min(days, 60))), media_type="text/plain; charset=utf-8")


@app.get("/danh-gia/skill.zip")
def chrome_skill_zip():
    """Gói skill tiktok-studio-quet (SKILL.md + references) để tải lên Claude."""
    import io
    import zipfile as _zf
    from pathlib import Path

    root = Path(__file__).parent / "chrome_skill"
    buf = io.BytesIO()
    with _zf.ZipFile(buf, "w", _zf.ZIP_DEFLATED) as z:
        for f in sorted((root / "tiktok-studio-quet").rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(root).as_posix())
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": "attachment; filename=tiktok-studio-quet.zip"})


@app.get("/danh-gia/{rid}.md")
def chrome_report_md(rid: int):
    from . import chrome_reports

    r = chrome_reports.get(rid)
    if not r:
        return RedirectResponse("/danh-gia", status_code=303)
    return HTMLResponse(r["body"], media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f"inline; filename=danh-gia-{rid}.md"})


@app.post("/danh-gia")
async def chrome_report_upload(request: Request):
    from . import chrome_reports

    form = await request.form()
    pid = int(form.get("pid") or 0) or None
    back = f"/packages/{pid}#posted" if pid else "/danh-gia"
    body = str(form.get("text") or "").strip()
    f = form.get("file")
    if not body and f is not None and hasattr(f, "read"):
        raw = await f.read()
        body = raw.decode("utf-8", errors="replace").strip()
    if len(body) < 50:
        flash(request, "Báo cáo trống hoặc quá ngắn — dán nội dung hoặc chọn file .md của Claude in Chrome.", "error")
        return RedirectResponse(back, status_code=303)
    rid = chrome_reports.add(body, pid=pid)
    if pid and not chrome_reports.get(rid)["video_id"]:
        vid = (packages.get(pid) or {}).get("video_id") or ""
        if vid:
            with db.tx() as c:
                c.execute("UPDATE chrome_reports SET video_id=? WHERE id=?", (vid, rid))
    flash(request, "Đã lưu báo cáo. Lần lập chiến lược tới sẽ dùng báo cáo này.", "success")
    return RedirectResponse(back, status_code=303)


@app.post("/danh-gia/{rid}/xoa")
def chrome_report_delete(request: Request, rid: int):
    from . import chrome_reports

    chrome_reports.delete(rid)
    flash(request, "Đã xoá báo cáo", "success")
    return RedirectResponse("/danh-gia", status_code=303)


@app.get("/tom-tat/{sid}.md")
def summaries_md(sid: int, download: int = 0):
    from . import cycle_summary

    r = cycle_summary.get(sid)
    if not r:
        return RedirectResponse("/tom-tat", status_code=303)
    disp = "attachment" if download else "inline"
    return HTMLResponse(r["md"], media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f"{disp}; filename={r['code']}.md"})


@app.post("/tom-tat/gui-lai")
def summaries_resend(request: Request):
    from . import cycle_summary

    st = db.query_one("SELECT id FROM strategies WHERE status='done' ORDER BY id DESC LIMIT 1")
    if not st:
        flash(request, "Chưa có chiến lược nào để tóm tắt", "error")
        return RedirectResponse("/tom-tat", status_code=303)

    def _sum():
        sid = cycle_summary.after_strategy(st["id"])
        r = cycle_summary.get(sid) if sid else None
        if not r:
            raise RuntimeError("Không tạo được bản tóm tắt")
        if r["error"] and not r["pushed"]:
            raise RuntimeError(f"{r['code']}: {r['error']}")
        return f"Đã tạo {r['code']}" + (f" · gửi: {r['pushed']}" if r["pushed"] else "") + (f" · lỗi: {r['error']}" if r["error"] else "")
    jobs.start("summary", _sum, link="/tom-tat")
    flash(request, "Đang tạo và gửi bản tóm tắt chạy ngầm — xong tool sẽ báo.", "info")
    return RedirectResponse("/tom-tat", status_code=303)


@app.get("/giong")
def voices_page(request: Request):
    from . import tts

    ok, why = tts.ready()
    samples = tts.load_samples()
    ref = tts.reference_info()
    order = tts.rank(samples, ref)
    order += [k for k in tts.VOICES if k not in order]  # giọng chưa có mẫu xếp cuối
    return render(request, "voices.html", active="voices", voices=tts.VOICES, samples=samples, ok=ok, why=why,
                  chosen=tts.voice_key(), text=samples.get("_text") or tts.SAMPLE_TEXT, style=tts.style(),
                  ref=ref, order=order, ranked=bool(ref.get("f0")) and any(samples.get(k, {}).get("f0") for k in tts.VOICES),
                  job=tts.job(), missing=tts.missing(samples.get("_text") or tts.SAMPLE_TEXT),
                  syl_min=tts.SYL_MIN, syl_max=tts.SYL_MAX, est=sum(tts.estimate_usd(tts.SAMPLE_TEXT, k) for k in tts.VOICES),
                  v=int(os.path.getmtime(tts.samples_path())) if os.path.exists(tts.samples_path()) else 0)


@app.post("/giong/mau")
def voices_make(request: Request, text: str = Form(...), only_missing: str = Form("")):
    from . import tts

    text = text.strip()[:400]
    keys = tts.missing(text) if only_missing else list(tts.VOICES)
    if not keys:
        flash(request, "Đủ giọng mẫu rồi.", "info")
    elif tts.start_samples(text, keys):
        flash(request, f"Đang tạo {len(keys)} giọng mẫu (khoảng 1–3 phút). Trang tự tải lại khi xong.", "info")
    else:
        flash(request, "Đang có lượt tạo giọng chạy, đợi xong rồi tạo tiếp.", "info")
    return RedirectResponse("/giong", status_code=303)


@app.post("/giong/ho-so")
def voices_style(request: Request, style: str = Form("")):
    val = style.strip()
    if val == _default_text(*DEFAULT_TEXT_KEYS["tts_style"]).strip():
        val = ""
    db.save_setting("tts_style", val[:6000])
    apply_overrides(db.load_settings())
    flash(request, "Đã lưu hồ sơ giọng Cô Kim. Bấm “Tạo giọng mẫu” để nghe lại theo hồ sơ mới.", "success")
    return RedirectResponse("/giong", status_code=303)


@app.post("/giong/mau-chuan")
async def voices_reference(request: Request):
    from . import tts

    form = await request.form()
    f = form.get("file")
    try:
        if not f or not getattr(f, "filename", ""):
            raise tts.TTSError("Chưa chọn file")
        tts.save_reference(await f.read(), f.filename)
        flash(request, "Đã thay giọng mẫu chuẩn.", "success")
    except tts.TTSError as e:
        flash(request, str(e), "error")
    return RedirectResponse("/giong", status_code=303)


@app.get("/giong/mau-chuan")
def voices_reference_file():
    from fastapi.responses import FileResponse, PlainTextResponse
    from . import tts

    p = tts.reference_path()
    if not p:
        return PlainTextResponse("Chưa có giọng mẫu chuẩn", status_code=404)
    mt = {"mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4"}[p.rsplit(".", 1)[-1]]
    return FileResponse(p, media_type=mt, headers={"Cache-Control": "no-store"})


@app.post("/giong/chon")
def voices_choose(request: Request, key: str = Form(...)):
    from . import tts

    if key not in tts.VOICES:
        flash(request, "Giọng không hợp lệ", "error")
    else:
        db.save_setting("tts_voice", key)
        apply_overrides(db.load_settings())
        flash(request, f"Đã chọn giọng thương hiệu: {tts.VOICES[key][2]}. Mọi gói sẽ dùng giọng này.", "success")
    return RedirectResponse("/giong", status_code=303)


@app.get("/giong/mau/{key}.wav")
def voices_file(key: str, download: int = 0):
    from fastapi.responses import FileResponse, PlainTextResponse
    from . import tts

    path = tts.sample_file(key)
    if not path or not os.path.exists(path):
        return PlainTextResponse("Chưa có mẫu", status_code=404)
    return FileResponse(path, media_type="audio/wav", headers={
        "Content-Disposition": f'{"attachment" if download else "inline"}; filename="Co_Kim_mau_{key}.wav"',
        "Cache-Control": "no-store"})


@app.get("/giong/mau.zip")
def voices_zip():
    import io as _io
    import zipfile as _zip

    from fastapi.responses import PlainTextResponse
    from . import tts

    buf = _io.BytesIO()
    with _zip.ZipFile(buf, "w", _zip.ZIP_STORED) as z:
        for i, k in enumerate(tts.VOICES, 1):
            path = tts.sample_file(k)
            if os.path.exists(path):
                z.write(path, f"GIONG_MAU_{i}_{k}.wav")
        ref = tts.reference_path()
        if ref and buf.tell() > 100:
            z.write(ref, "GIONG_MAU_CHUAN_CO_KIM." + ref.rsplit(".", 1)[-1])
    if buf.tell() < 100:
        return PlainTextResponse("Chưa có mẫu", status_code=404)
    return HTMLResponse(buf.getvalue(), media_type="application/zip",
                        headers={"Content-Disposition": 'attachment; filename="Co_Kim_giong_mau.zip"'})


@app.post("/packages/{pid}/sua")
async def package_sua(request: Request, pid: int):
    """Gửi Gemini thư sửa phiếu gói: chỉ các mục kiểm tra anh Nhơn đánh dấu ✓ + ghi chú."""
    f = await request.form()
    note = str(f.get("note") or "")
    picked = {int(x) for x in f.getlist("items") if str(x).isdigit()}
    p = packages.get(pid)
    if not p:
        return RedirectResponse("/packages", status_code=303)
    chk = packages.check(p)
    chk = {**chk, "items": [i for k, i in enumerate(chk["items"]) if k in picked and i["level"] in ("error", "warn")]}
    chk["errors"] = sum(1 for i in chk["items"] if i["level"] == "error")
    chk["warns"] = sum(1 for i in chk["items"] if i["level"] == "warn")
    if not (chk["items"] or note.strip()):
        flash(request, "Chưa chọn mục nào và chưa có ghi chú — không gửi", "info")
        return RedirectResponse(f"/packages/{pid}#check", status_code=303)
    rid = gemini_requests.create_sua(p, chk, note[:2000])
    r = gemini_requests.get(rid)
    _send_bg(rid, f"/packages/{pid}#check")
    flash(request, f"Đã soạn thư {r['code']} — đang gửi cho Gemini chạy ngầm, xong tool sẽ báo.", "success")
    return RedirectResponse(f"/packages/{pid}#check", status_code=303)


@app.post("/packages/{pid}/ghep")
def package_ghep(request: Request, pid: int):
    from . import clips

    p = packages.get(pid)
    cl = clips.load(p or {})
    if not p or not clips.all_ok(cl):
        flash(request, "Cần duyệt ĐẠT đủ mọi cảnh trước khi gửi Gemini ghép", "error")
        return RedirectResponse(f"/packages/{pid}#clips", status_code=303)
    if clips.local_only(cl):
        flash(request, f"Cảnh {', '.join(clips.local_only(cl))} là clip Veo chưa có trên Drive: bấm “Tải 4 clip (.zip)”, "
                       "giải nén vào thư mục 02 rồi Quét lại thư mục 02.", "error")
        return RedirectResponse(f"/packages/{pid}#clips", status_code=303)
    code, letter = clips.ghep_letter(p, cl)
    rid = gemini_requests.create_ghep(p["goi"], code, f"Ghép video Gói {p['goi']}", letter)
    _send_bg(rid, f"/packages/{pid}#clips")
    flash(request, f"Đã soạn thư {code} — đang gửi cho Gemini ghép chạy ngầm, xong tool sẽ báo.", "success")
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
    from . import fixer

    acc = db.get_active_account()
    issues = tags.compliance_issues(acc["open_id"]) if acc else []
    gem = request.session.pop("fix_gemini", None) or {}
    for v in issues:
        cart = None if (v.get("tag") or {}).get("has_cart") is None else bool(v["tag"]["has_cart"])
        v["orig"] = f"{v.get('title') or ''}\n{v.get('description') or ''}".strip()
        if (v.get("title") or "").strip() and (v.get("description") or "").strip().startswith((v.get("title") or "").strip()):
            v["orig"] = (v.get("description") or "").strip()  # TikTok trả title = đầu caption → khỏi lặp
        v["fix"] = fixer.sua_nhanh(v["orig"], cart)
        v["gem"] = gem if gem.get("video_id") == v["id"] else None
    result = request.session.pop("check_result", None)
    if result:
        result["fix"] = fixer.sua_nhanh(result["text"], {"1": True, "0": False}.get(result.get("has_cart")))
    return render(
        request, "compliance.html", issues=issues, result=result, level_labels=compliance.LEVEL_LABELS,
        allowed=compliance.ALLOWED_CTA, rules=settings.content_rules, gemini_ready=bool(settings.gemini_api_key),
    )


@app.post("/compliance/fix/{video_id}")
def compliance_fix_gemini(request: Request, video_id: str):
    from . import fixer

    acc = db.get_active_account()
    v = next((x for x in (tags.compliance_issues(acc["open_id"]) if acc else []) if x["id"] == video_id), None)
    if not v:
        flash(request, "Không tìm thấy video", "error")
        return RedirectResponse("/compliance", status_code=303)
    cart = None if (v.get("tag") or {}).get("has_cart") is None else bool(v["tag"]["has_cart"])
    text = (v.get("description") or v.get("title") or "").strip()
    try:
        r = fixer.viet_lai_gemini(text, cart)
        u = r.get("usage") or {}
        request.session["fix_gemini"] = {"video_id": video_id, "text": r["text"][:3000], "why": r["why"][:300],
                                         "level": r["after"]["level"], "tokens": u.get("total_tokens", 0),
                                         "cost_vnd": round((u.get("cost_usd") or 0) * settings.usd_vnd_rate)}
    except Exception as e:  # noqa: BLE001
        flash(request, f"Gemini chưa viết lại được: {e}", "error")
    return RedirectResponse(f"/compliance#v{video_id}", status_code=303)


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
    from . import strategy_plan

    plan = strategy_plan.parse_schedule(current["content_md"]) if current and current.get("content_md") else []
    made = {r["opts"].get("plan_key"): r for r in gemini_requests.all_requests() if r["opts"].get("plan_key")}
    for r in plan:
        r["req"] = made.get(f"{current['id']}:{r['idx']}")
    return render(
        request, "strategy.html", items=items, current=current, gemini_ready=bool(settings.gemini_api_key), plan=plan,
        loai_short=packages.LOAI_SHORT, groups=tags.CONTENT_GROUPS,
        answer=request.session.pop("answer", None) or _ask_answer(request.query_params.get("ans")),
        usage=strategy.usage_summary(), rate=settings.usd_vnd_rate,
        endpoint_labels=strategy.ENDPOINT_LABELS, endpoint_now=strategy.ENDPOINT_LABELS[strategy.planned_endpoint()],
    )


def _ask_answer(jid) -> dict | None:
    import json as _json

    if not (jid and str(jid).isdigit()):
        return None
    j = db.query_one("SELECT * FROM jobs WHERE id=? AND kind='ask'", (int(jid),))
    if not j or j["status"] == "pending":
        return None
    if j["status"] == "error":
        return {"q": "", "a": f"Lỗi: {j['message']}", "usage": None}
    try:
        d = _json.loads(j["message"])
    except ValueError:
        return None
    return {"q": d.get("q", ""), "a": d.get("a", ""), "usage": None}


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
    """Hỏi Gemini chạy ngầm; câu trả lời lưu ở bảng jobs (kind=ask), xem tại /strategy?ans=<id>."""
    import json as _json

    acc = db.get_active_account()
    if not acc:
        flash(request, "Chưa kết nối kênh", "error")
        return RedirectResponse("/strategy#ask", status_code=303)
    q = question.strip()
    holder = {}

    def _ask():
        answer, usage = strategy.ask(acc["open_id"], q)
        with db.tx() as c:
            c.execute("UPDATE jobs SET link=? WHERE id=?", (f"/strategy?ans={holder['id']}#ask", holder["id"]))
        return _json.dumps({"q": q, "a": answer}, ensure_ascii=False), usage
    holder["id"] = jobs.start("ask", _ask, link="/strategy#ask")
    flash(request, "Đã gửi câu hỏi cho Gemini chạy ngầm — xong tool sẽ báo, bấm “Xem” để đọc câu trả lời.", "info")
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
        if key in ("auto_strategy", "veo_enabled", "auto_apply_updates", "ads_paused"):
            val = "true" if form.get(key) else "false"
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
    def _test():
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
        if not ok:
            raise RuntimeError(msg)
        return msg
    jobs.start("drive_test", _test, link="/settings")
    flash(request, "Đang kiểm tra Drive chạy ngầm — xong tool sẽ báo.", "info")
    return RedirectResponse("/settings", status_code=303)


@app.post("/settings/recompute-costs")
def settings_recompute_costs(request: Request):
    n = strategy.recompute_costs()
    flash(request, f"Đã tính lại chi phí cho {n} bản ghi theo giá hiện tại", "success")
    return RedirectResponse("/settings", status_code=303)


@app.post("/scan")
def scan_now(request: Request):
    if jobs.running("scan"):
        flash(request, "Đang quét rồi — tool sẽ báo khi xong.", "info")
    else:
        def _scan():
            res = scanner.run_scan("manual")
            if res["status"] != "ok":
                raise RuntimeError(res["message"])
            return res["message"] + (" · đã lập chiến lược mới" if settings.auto_strategy else "")
        jobs.start("scan", _scan, link="/")
        flash(request, "Đang quét TikTok chạy ngầm (kèm lập chiến lược nếu bật) — anh cứ làm việc khác, xong tool sẽ báo.", "info")
    return RedirectResponse(request.headers.get("referer") or "/", status_code=303)


@app.post("/sync")
def sync_now(request: Request):
    acc = db.get_active_account()
    if not acc:
        flash(request, "Chưa kết nối kênh", "error")
    else:
        def _sync():
            res = notebooklm.sync_all(acc["open_id"])
            if not res:
                return "NOTEBOOKLM_MODE đang tắt"
            ok = sum(r["status"] == "ok" for r in res)
            if ok < len(res):
                raise RuntimeError(f"Đồng bộ: {ok}/{len(res)} thành công")
            return f"Đồng bộ: {ok}/{len(res)} thành công"
        jobs.start("sync", _sync, link="/settings")
        flash(request, "Đang đồng bộ chạy ngầm — xong tool sẽ báo.", "info")
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
        if j["kind"] == "ask" and j["status"] == "done":
            import json as _json

            try:
                j["message"] = "Hỏi: " + _json.loads(j["message"]).get("q", "")[:120] + " — bấm Xem để đọc câu trả lời"
            except ValueError:
                pass
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
