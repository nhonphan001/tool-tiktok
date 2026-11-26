"""Ghép số liệu TikTok API (tool) với báo cáo Claude in Chrome (TikTok Studio) → báo cáo đồng thuận cho Gemini.

1. ingest(): đọc khối JSON của báo cáo Chrome thành bảng chrome_video_metrics (mỗi video × mỗi báo cáo).
2. promo_suspects(): dò video nghi được quảng bá từ chuỗi ảnh chụp API (view tăng đều/tăng vọt) mà Chrome chưa xác nhận.
3. diffs(): chênh lệch API ↔ Studio theo video.
4. build_md() / push(): báo cáo đồng thuận → Doc BAO_CAO_DONG_THUAN__GUI_GEMINI (ghi đè), không tốn token.

Quy tắc ghép: tổng = API (chính xác); trả phí = trang Quảng bá; tự nhiên = tổng − trả phí; giữ chân/follower/nguồn = Studio.
"""
import json
import logging
import statistics
from datetime import datetime, timedelta, timezone

from . import chrome_reports, db
from .config import settings

log = logging.getLogger(__name__)
VN = timezone(timedelta(hours=7))

COLS = ["video_id", "goi", "loai", "scenes", "snapshot_at", "posted_at", "duration_s", "promoted", "promo_spent",
        "promo_views", "promo_followers", "views", "unique_viewers", "likes", "comments", "shares", "saves",
        "new_followers", "avg_watch_s", "completion", "ret_2s", "ret_10s", "for_you", "following", "search",
        "h_score", "comments_birth", "search_queries"]


def init() -> None:
    chrome_reports.init()
    with db.tx() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS chrome_video_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT, report_id INTEGER, video_id TEXT, goi TEXT, loai INTEGER, scenes INTEGER,
            snapshot_at TEXT, posted_at TEXT, duration_s REAL, promoted INTEGER, promo_spent REAL, promo_views INTEGER,
            promo_followers INTEGER, views INTEGER, unique_viewers INTEGER, likes INTEGER, comments INTEGER, shares INTEGER,
            saves INTEGER, new_followers INTEGER, avg_watch_s REAL, completion REAL, ret_2s REAL, ret_10s REAL,
            for_you REAL, following REAL, search REAL, h_score INTEGER, comments_birth INTEGER, search_queries TEXT,
            UNIQUE(report_id, video_id))""")


# --------------------------------------------------------------------------- 1. đọc JSON báo cáo Chrome
def _num(x):
    if x is None or x == "" or isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return x
    s = str(x).strip().replace("~", "").replace("%", "").replace(" ", "")
    mult = 1
    if s[-1:].lower() == "k":
        mult, s = 1000, s[:-1]
    s = s.replace(",", ".") if s.count(",") == 1 and "." not in s else s.replace(",", "")
    try:
        v = float(s) * mult
    except ValueError:
        return None
    return int(v) if v == int(v) else v


def _rate(x):
    """Tỷ lệ về đơn vị % (0,023 → 2,3)."""
    v = _num(x)
    return round(v * 100, 2) if isinstance(v, (int, float)) and 0 < v < 1 else v


def _video_rows(data: dict) -> list[dict]:
    """Hỗ trợ khuôn tiktok-studio-quet/v1 (videos[]) và khuôn 1 video cũ (metrics ở gốc)."""
    vids = data.get("videos")
    if isinstance(vids, list):
        return [v for v in vids if isinstance(v, dict)]
    if data.get("metrics") or data.get("video_id"):
        return [data]
    return []


def _row(v: dict, snap: str) -> dict | None:
    vid = str(v.get("video_id") or "").strip()
    if not vid.isdigit():
        return None
    m = v.get("metrics") or {}
    promo = v.get("promo") or {}
    ret = v.get("retention_pct") or {}
    src = v.get("traffic_source_pct") or {}
    hook = v.get("hook") or {}
    com = v.get("comments") or {}
    split = v.get("goi_17_split") or {}
    promoted = v.get("promoted")
    q = v.get("search_queries") or []
    return {
        "video_id": vid, "goi": str(v.get("goi") or ""), "loai": _num(v.get("loai")), "scenes": _num(v.get("scenes")),
        "snapshot_at": str(v.get("snapshot_at") or snap or ""), "posted_at": str(v.get("posted_at") or ""),
        "duration_s": _num(v.get("duration_s")),
        "promoted": None if promoted is None else int(bool(promoted)),
        "promo_spent": _num(promo.get("spent")), "promo_views": _num(promo.get("views") or split.get("promo_views")),
        "promo_followers": _num(promo.get("followers") or split.get("promo_followers")),
        "views": _num(m.get("views")), "unique_viewers": _num(m.get("unique_viewers")), "likes": _num(m.get("likes")),
        "comments": _num(m.get("comments")), "shares": _num(m.get("shares")), "saves": _num(m.get("saves")),
        "new_followers": _num(m.get("new_followers")), "avg_watch_s": _num(m.get("avg_watch_s")),
        "completion": _rate(m.get("completion_rate")), "ret_2s": _num(ret.get("2")), "ret_10s": _num(ret.get("10")),
        "for_you": _num(src.get("for_you")), "following": _num(src.get("following")), "search": _num(src.get("search")),
        "h_score": _num(hook.get("h_score")), "comments_birth": _num(com.get("with_birth")),
        "search_queries": json.dumps(q, ensure_ascii=False)[:1000] if q else "",
    }


def ingest(report_id: int) -> int:
    """Tách số liệu từng video của 1 báo cáo. Trả về số video đọc được."""
    init()
    r = chrome_reports.get(report_id)
    data = chrome_reports.extract_json((r or {}).get("body") or "") or {}
    snap = str(data.get("snapshot_at") or (r or {}).get("run_started") or (r or {}).get("created_at") or "")
    rows = [x for x in (_row(v, snap) for v in _video_rows(data)) if x]
    with db.tx() as c:
        c.execute("DELETE FROM chrome_video_metrics WHERE report_id=?", (report_id,))
        for x in rows:
            c.execute(f"INSERT INTO chrome_video_metrics (report_id, {', '.join(COLS)}) VALUES (?{', ?' * len(COLS)})",
                      (report_id, *[x[k] for k in COLS]))
    return len(rows)


def ingest_all() -> int:
    init()
    return sum(ingest(r["id"]) for r in db.query("SELECT id FROM chrome_reports ORDER BY id"))


def latest_chrome() -> dict[str, dict]:
    """Số Chrome mới nhất của mỗi video."""
    init()
    rows = db.query("SELECT * FROM chrome_video_metrics ORDER BY snapshot_at, report_id")
    return {r["video_id"]: r for r in rows}


# --------------------------------------------------------------------------- 2. nghi quảng bá
def _daily_gains(video_id: str) -> list[tuple[str, int]]:
    """View tăng theo ngày (giờ VN) từ ảnh chụp API: ngày → view cuối ngày − view cuối ngày trước."""
    snaps = db.query("SELECT taken_at, view_count FROM video_snapshots WHERE video_id=? ORDER BY taken_at", (video_id,))
    last_by_day: dict[str, int] = {}
    for s in snaps:
        try:
            d = datetime.fromisoformat(str(s["taken_at"]).replace("Z", "+00:00")).astimezone(VN).date().isoformat()
        except ValueError:
            continue
        last_by_day[d] = s["view_count"] or 0
    days = sorted(last_by_day)
    return [(d, last_by_day[d] - last_by_day[p]) for p, d in zip(days, days[1:])]


def promo_suspects(open_id: str | None = None) -> list[dict]:
    """Video nghi có Quảng bá mà Chrome chưa xác nhận: (a) ≥3 ngày liền tăng ≥1.000 view/ngày và đều nhau (max ≤ 1,8 × min);
    (b) tổng view ≥ 5 × trung vị view của video 30 ngày gần đây (và ≥ 2.000). Chỉ là gợi ý để chạy skill kiểm trang Quảng bá."""
    from . import analytics

    acc = db.get_active_account() or {}
    oid = open_id or acc.get("open_id")
    if not oid:
        return []
    vids = analytics.get_videos(oid)
    chrome = latest_chrome()
    # trung vị theo VIEW TỔNG của video 30 ngày gần đây (view/ngày của video cũ rất nhỏ → bội số bị phóng đại)
    recent = [v for v in vids if v.get("age_days") is not None and v["age_days"] <= 30]
    tot = [v.get("view_count") or 0 for v in recent]
    med = statistics.median(tot) if len(tot) >= 5 else 0
    out = []
    for v in vids[:60]:
        c = chrome.get(v["id"])
        if c and c.get("promoted") is not None:
            continue  # Chrome đã kiểm trang Quảng bá
        gains = _daily_gains(v["id"])
        reasons = []
        run = [g for _, g in gains[-5:] if g >= 1000]
        if len(run) >= 3 and max(run) <= 1.8 * min(run):
            reasons.append(f"{len(run)} ngày liền tăng đều {min(run):,}–{max(run):,} view/ngày".replace(",", "."))
        if med and (v.get("view_count") or 0) >= max(5 * med, 2000):
            reasons.append(f"{v['view_count']:,} view ≈ {v['view_count'] / med:.0f}× trung vị 30 ngày ({med:,.0f})".replace(",", "."))
        if reasons:
            out.append({"video_id": v["id"], "posted": v.get("posted_str"), "views": v.get("view_count"),
                        "label": v.get("label"), "reasons": reasons})
    return out


# --------------------------------------------------------------------------- 3. chênh lệch API ↔ Studio
def _api_at(video_id: str, when: str) -> dict | None:
    """Ảnh chụp API gần thời điểm Chrome đọc nhất (trong ±12 giờ); không có thì số API mới nhất."""
    snaps = db.query("SELECT taken_at, view_count, like_count, comment_count, share_count FROM video_snapshots"
                     " WHERE video_id=? ORDER BY taken_at", (video_id,))
    if not snaps:
        return None
    try:
        t = datetime.fromisoformat(when.replace("Z", "+00:00"))
        t = t if t.tzinfo else t.replace(tzinfo=VN)
    except ValueError:
        return dict(snaps[-1], gap_h=None)

    def gap(s):
        try:
            return abs((datetime.fromisoformat(str(s["taken_at"]).replace("Z", "+00:00")) - t).total_seconds()) / 3600
        except ValueError:
            return 1e9
    best = min(snaps, key=gap)
    g = gap(best)
    return dict(best if g <= 12 else snaps[-1], gap_h=round(g, 1) if g <= 12 else None)


def _pct(a, b):
    return round((b - a) / a * 100, 1) if a and b is not None else None


def diffs() -> list[dict]:
    out = []
    for vid, c in latest_chrome().items():
        a = _api_at(vid, c.get("snapshot_at") or "")
        if not a:
            out.append({"video_id": vid, "goi": c.get("goi"), "note": "API chưa có video này"})
            continue
        out.append({"video_id": vid, "goi": c.get("goi"), "api_views": a["view_count"], "studio_views": c.get("views"),
                    "views_pct": _pct(a["view_count"], c.get("views")), "api_likes": a["like_count"],
                    "studio_likes": c.get("likes"), "likes_pct": _pct(a["like_count"], c.get("likes")),
                    "gap_h": a.get("gap_h")})
    return out


# --------------------------------------------------------------------------- 4. bảng ghép + báo cáo
def merged(open_id: str | None = None, days: int = 21) -> list[dict]:
    """Mỗi video gần đây: số API + số Chrome + phần tự nhiên + gói."""
    from . import analytics, packages

    acc = db.get_active_account() or {}
    oid = open_id or acc.get("open_id")
    vids = analytics.get_videos(oid) if oid else []
    since = datetime.now(VN) - timedelta(days=days)
    chrome = latest_chrome()
    pk = {p.get("video_id"): p for p in packages.all_packages() if p.get("video_id")}
    out = []
    for v in vids:
        if not v.get("posted_local") or v["posted_local"] < since:
            continue
        c = chrome.get(v["id"]) or {}
        p = pk.get(v["id"]) or {}
        total = v.get("view_count") or 0  # API = tổng chính xác
        pv = c.get("promo_views") if c.get("promoted") else (0 if c.get("promoted") == 0 else None)
        pf = c.get("promo_followers") if c.get("promoted") else (0 if c.get("promoted") == 0 else None)
        org_v = total - pv if pv is not None else None
        org_f = (c["new_followers"] - pf) if (pf is not None and c.get("new_followers") is not None) else None
        out.append({
            "video_id": v["id"], "posted": v.get("posted_str"), "hour": v["posted_local"].strftime("%H:%M"),
            "goi": p.get("goi") or c.get("goi") or "", "loai": p.get("loai") or c.get("loai"),
            "scenes": packages.n_scenes(p) if p else c.get("scenes"), "label": v.get("label"),
            "api_views": total, "api_likes": v.get("like_count") or 0, "api_comments": v.get("comment_count") or 0,
            "api_shares": v.get("share_count") or 0, "views_per_day": v.get("views_per_day"),
            "chrome": bool(c), "promoted": c.get("promoted"), "promo_views": pv, "promo_followers": pf,
            "organic_views": org_v, "new_followers": c.get("new_followers"), "organic_followers": org_f,
            "ret_2s": c.get("ret_2s"), "ret_10s": c.get("ret_10s"), "avg_watch_s": c.get("avg_watch_s"),
            "completion": c.get("completion"), "saves": c.get("saves"), "for_you": c.get("for_you"),
            "following": c.get("following"), "search": c.get("search"), "h_score": c.get("h_score"),
            "comments_birth": c.get("comments_birth"), "snapshot_at": c.get("snapshot_at"),
            "like_rate": round((v.get("like_count") or 0) / total * 100, 1) if total else None,
            "comments_per_1k": round((v.get("comment_count") or 0) / total * 1000, 1) if total else None,
            "follow_rate_org": round(org_f / org_v * 100, 2) if (org_f is not None and org_v) else None,
        })
    return out


def _f(x, unit=""):
    if x is None or x == "":
        return "—"
    if isinstance(x, float):
        return f"{x:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + unit
    if isinstance(x, int):
        return f"{x:,}".replace(",", ".") + unit
    return f"{x}{unit}"


def _group(rows: list[dict], key, label: str) -> list[str]:
    """So sánh nhóm CHỈ trên video tự nhiên đã có số Chrome (promoted = 0)."""
    org = [r for r in rows if r["promoted"] == 0]
    groups: dict[str, list[dict]] = {}
    for r in org:
        k = key(r)
        if k:
            groups.setdefault(k, []).append(r)
    if not groups:
        return [f"| {label} | chưa có video tự nhiên đã quét | | | | |"]
    lines = []
    for k, g in sorted(groups.items()):
        def avg(f):
            xs = [r[f] for r in g if isinstance(r.get(f), (int, float))]
            return round(sum(xs) / len(xs), 1) if xs else None
        tag = " (ít dữ liệu)" if len(g) < 2 else ""
        lines.append(f"| {label}: {k}{tag} | {len(g)} | {_f(avg('organic_views'))} | {_f(avg('ret_2s'), '%')} | "
                     f"{_f(avg('follow_rate_org'), '%')} | {_f(avg('comments_per_1k'))} |")
    return lines


def build_md(open_id: str | None = None, days: int = 21) -> str:
    from . import analytics

    init()
    now = datetime.now(VN)
    acc = db.get_active_account() or {}
    oid = open_id or acc.get("open_id") or ""
    rows = merged(oid, days)
    snaps = db.query("SELECT taken_at, follower_count FROM account_snapshots WHERE open_id=? AND follower_count IS NOT NULL"
                     " ORDER BY taken_at", (oid,)) if oid else []
    by_day: dict[str, int] = {}
    for s in snaps:
        try:
            d = datetime.fromisoformat(str(s["taken_at"]).replace("Z", "+00:00")).astimezone(VN).strftime("%d/%m")
        except ValueError:
            continue
        by_day[d] = s["follower_count"]
    fdays = list(by_day.items())[-10:]
    sus = promo_suspects(oid)
    dif = diffs()
    reps = chrome_reports.list_reports(limit=8)
    n_chrome = sum(1 for r in rows if r["chrome"])
    L = [f"# BÁO CÁO ĐỒNG THUẬN TikTok Manager (Display API) + An (TikTok Studio) · {now:%d/%m/%Y %H:%M}", "",
         "> **Dành cho Gemini phân tích và đánh giá.** Tool tự soạn, ghi đè Doc này sau mỗi báo cáo TikTok Studio mới từ An (Antigravity). Không tốn token.",
         "> **Quy tắc ghép số:**",
         "> - **Tổng** (view, thích, bình luận, chia sẻ) = TikTok Display API (VPS tự quét 4 lần/ngày, chính xác).",
         "> - **Trả phí** = trang Quảng bá (An · Antigravity đọc chỉ-đọc).",
         "> - **Tự nhiên** = tổng − trả phí.",
         "> - **Giữ chân / follower theo video / nguồn view** = TikTok Studio (An · Antigravity đọc chỉ-đọc, số biểu đồ có sai số ±2 điểm).",
         f"> **Trạng thái:** {'TUẦN THỬ NGHIỆM KHÔNG QUẢNG BÁ (từ 25/11)' if settings.ads_paused else 'có thể có Quảng bá'} · "
         f"{len(rows)} video trong {days} ngày · {n_chrome} video đã có số TikTok Studio.", "",
         "## 1. Kênh (API)", ""]
    if fdays:
        L += ["| Ngày | " + " | ".join(d for d, _ in fdays) + " |", "|---|" + "---|" * len(fdays),
              "| Follower | " + " | ".join(_f(v) for _, v in fdays) + " |", ""]
    else:
        L += ["(chưa có ảnh chụp follower)", ""]
    L += ["Lưu ý: follower 15–26/11 có ~2.020 follower mua qua Quảng bá (xem bối cảnh cuối báo cáo).", "",
          "## 2. Bảng video ghép (API + Claude in Chrome)", "",
          "| Đăng | Gói | Loại | Cảnh | View API | QB? | View tự nhiên | Follower mới | Follower tự nhiên | Follow/view TN | "
          "Giữ chân 2s | 10s | Xem TB | Thích/view | BL/1.000 | Đề xuất / Follow / Tìm % | H | Chrome đọc lúc |",
          "|" + "---|" * 18]
    for r in rows:
        qb = {1: "**CÓ**", 0: "không", None: "chưa kiểm"}[r["promoted"]]
        src = "/".join(_f(r[k]) for k in ("for_you", "following", "search")) if r["chrome"] else "—"
        L.append(f"| {r['posted']} | {r['goi'] or '—'} | {r['loai'] or '—'} | {r['scenes'] or '—'} | {_f(r['api_views'])} | {qb} | "
                 f"{_f(r['organic_views'])} | {_f(r['new_followers'])} | {_f(r['organic_followers'])} | {_f(r['follow_rate_org'], '%')} | "
                 f"{_f(r['ret_2s'], '%')} | {_f(r['ret_10s'], '%')} | {_f(r['avg_watch_s'], 's')} | {_f(r['like_rate'], '%')} | "
                 f"{_f(r['comments_per_1k'])} | {src} | {_f(r['h_score'])} | {(r['snapshot_at'] or '—')[:16]} |")
    L += ["", "## 3. So sánh nhóm (chỉ video TỰ NHIÊN đã có số Claude in Chrome)", "",
          "| Nhóm | Số video | View TN TB | Giữ chân 2s TB | Follow/view TN | BL/1.000 |", "|---|---|---|---|---|---|"]
    L += _group(rows, lambda r: f"Loại {r['loai']}" if r["loai"] else "", "Loại")
    L += _group(rows, lambda r: r["hour"][:2] + "h", "Giờ đăng")
    L += _group(rows, lambda r: f"{r['scenes']} cảnh" if r["scenes"] else "", "Số cảnh")
    L += _group(rows, lambda r: ("đạt ≥5/6" if r["h_score"] >= 5 else "dưới 5/6") if isinstance(r["h_score"], (int, float)) else "", "Quy tắc H")
    L += ["", "## 4. Video nghi được Quảng bá (từ chuỗi API, Claude in Chrome chưa kiểm)", ""]
    L += [f"- {s['posted']} · {s['video_id']} · {(s['label'] or '')[:50]}: {'; '.join(s['reasons'])} → chạy skill chế độ video để kiểm trang Quảng bá."
          for s in sus] or ["- Không có."]
    L += ["", "## 5. Chênh lệch API ↔ Studio", "", "| Gói | Video | View API | View Studio | Lệch | Thích API | Thích Studio | Lệch | Cách nhau (giờ) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for d in dif:
        if d.get("note"):
            L.append(f"| {d['goi'] or '—'} | {d['video_id']} | {d['note']} | | | | | | |")
        else:
            L.append(f"| {d['goi'] or '—'} | {d['video_id']} | {_f(d['api_views'])} | {_f(d['studio_views'])} | {_f(d['views_pct'], '%')} | "
                     f"{_f(d['api_likes'])} | {_f(d['studio_likes'])} | {_f(d['likes_pct'], '%')} | {_f(d['gap_h'])} |")
    if not dif:
        L.append("| — | chưa có báo cáo Claude in Chrome có khối JSON | | | | | | | |")
    L += ["", "Lệch view > 10% thường do Studio làm tròn (\"10K\") hoặc API trễ; khi đó tin số API cho tổng.", "",
          "## 6. Báo cáo Claude in Chrome gần nhất", ""]
    for r in reps:
        tok = (f"{r['tokens_exact']:,} token" if r.get("tokens_exact") else
               (f"~{r['tokens_est']:,} token" if r.get("tokens_est") else "")).replace(",", ".")
        L.append(f"- {(r.get('run_started') or r['created_at'])[:16].replace('T', ' ')} · {r['title']} · {tok}")
        body = (chrome_reports.get(r["id"]) or {}).get("body") or ""
        summ = chrome_reports._summary_part(body, 700).strip()
        if summ:
            L += ["  > " + ln for ln in summ.splitlines() if ln.strip()][:8]
    if not reps:
        L.append("- (chưa có)")
    L += ["", "## 7. Bối cảnh Quảng bá", "", settings.ads_context.strip(), "",
          "## 8. Gemini cần làm", "",
          "1. Đánh giá **chỉ trên số tự nhiên**: video nào giữ chân giây 2 tốt nhất, follow/view tự nhiên cao nhất, vì sao (dẫn số mục 2–3).",
          "2. Kiểm tra mục 4 (nghi quảng bá) và mục 5 (chênh lệch): có số nào không đáng tin không.",
          "3. Đề xuất 3 thay đổi cụ thể cho các gói kế tiếp (khung 0, câu đầu, vị trí câu kêu gọi, giờ đăng, dạng video).",
          "4. Trả lời bằng file `DANHGIA-<ddmm>-DONG-THUAN__GUI_CLAUDE.md` trong GUI_CLAUDE.",
          "", "```json", json.dumps({"schema": "dong-thuan/v1", "generated_at": now.isoformat(timespec="seconds"),
                                     "videos": rows, "promo_suspects": sus, "api_vs_studio": dif},
                                    ensure_ascii=False, default=str), "```"]
    return "\n".join(L)


PUSH_DAYS = 400  # Doc cho Gemini: mọi video (cả tháng 3) để có số nền đầy đủ sau lượt quét toàn bộ


def push() -> str:
    """Ghi đè Doc đồng thuận trong GUI_GEMINI. Trả 'ok' hoặc lỗi."""
    if not settings.consensus_doc_gemini:
        return "chưa cấu hình Doc"
    try:
        from .notebooklm import push_drive

        push_drive(settings.consensus_doc_gemini, build_md(days=PUSH_DAYS))
        db.log_sync("consensus", "ok", "BAO_CAO_DONG_THUAN__GUI_GEMINI")
        return "ok"
    except Exception as e:  # noqa: BLE001
        log.exception("consensus push")
        db.log_sync("consensus", "error", str(e)[:200])
        return str(e)[:200]


def after_report(report_id: int) -> str:
    """Gọi sau khi lưu báo cáo Chrome: tách số liệu rồi gửi báo cáo đồng thuận. Lỗi không làm hỏng luồng chính."""
    try:
        ingest(report_id)
        return push()
    except Exception as e:  # noqa: BLE001
        log.exception("consensus after_report")
        return str(e)[:200]
