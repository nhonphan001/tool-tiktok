"""Bản tóm tắt tự động sau mỗi lần quét + lập chiến lược thành công → hộp thư Gemini và Claude (đánh giá chéo).

- Gồm: số liệu kênh lúc quét, tiến độ KPI, khung giờ, top video 7 ngày, các bước quy trình đang ⚠/❌,
  lịch 7 ngày của chiến lược (Loại + cảnh báo), mục KPI của chiến lược, danh sách điểm cần đánh giá chéo.
- Ghi vào 2 Google Doc (service account không tạo được file mới trong Drive cá nhân):
  TOM_TAT_TU_DONG__GUI_GEMINI.md (GUI_GEMINI) và TOM_TAT_TU_DONG__GUI_CLAUDE.md (GUI_CLAUDE).
  Doc giữ 7 bản mới nhất, bản mới ở trên cùng. Mọi bản lưu trong DB, tải .md ở /tom-tat.
- Không gọi AI, không tốn token.
"""
import logging
import re
from datetime import datetime, timedelta, timezone

from . import analytics, db, kpi, strategy_plan
from .config import settings

log = logging.getLogger(__name__)
KEEP_IN_DOC = 7
VN = timezone(timedelta(hours=7))


def init() -> None:
    with db.tx() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS cycle_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, code TEXT, scan_id INTEGER, strategy_id INTEGER,
            md TEXT, pushed TEXT DEFAULT '', error TEXT DEFAULT '')""")


def _section(md: str, title_rx: str, limit: int = 1800) -> str:
    m = re.search(rf"^#{{1,4}}[^\n]*{title_rx}[^\n]*$", md or "", re.M | re.I)
    if not m:
        return ""
    body = md[m.end():]
    nxt = re.search(r"^#{1,3}\s", body, re.M)
    body = (body[:nxt.start()] if nxt else body).strip()
    return body[:limit] + (" …" if len(body) > limit else "")


def _process_issues() -> list[str]:
    try:
        from . import system_report

        lines = system_report.to_markdown().splitlines()
    except Exception as e:  # noqa: BLE001
        return [f"Không đọc được báo cáo hệ thống: {e}"]
    out = []
    for ln in lines:
        if ln.startswith("| P") and ("⚠" in ln or "❌" in ln):
            cells = [x.strip() for x in ln.strip("|").split("|")]
            out.append(f"{cells[0]} {cells[1]} — {cells[2]}")
    return out


def build(open_id: str, strategy_row: dict | None) -> tuple[str, str]:
    now = datetime.now(VN)
    code = f"TOMTAT-{now:%d%m-%H%M}"
    scan = db.query_one("SELECT * FROM scans WHERE status='ok' ORDER BY id DESC LIMIT 1") or {}
    snaps = db.query("SELECT taken_at, follower_count, likes_count, video_count FROM account_snapshots WHERE open_id=?"
                     " AND follower_count IS NOT NULL ORDER BY taken_at", (open_id,))
    cur = snaps[-1] if snaps else {}
    d24 = None
    if snaps:
        t = datetime.fromisoformat(cur["taken_at"])
        base = analytics.snapshot_at_or_before(snaps, t - timedelta(days=1))
        d24 = (cur["follower_count"] - base["follower_count"]) if base else None
    ks = kpi.summary(open_id)
    lv = ks["like_view"]
    vids = analytics.get_videos(open_id)
    week = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp())
    top = sorted([v for v in vids if (v.get("create_time") or 0) >= week], key=lambda v: v.get("view_count") or 0,
                 reverse=True)[:5]
    md = strategy_row.get("content_md") if strategy_row else ""
    plan = strategy_plan.parse_schedule(md or "")
    issues = _process_issues()

    L = [
        "---", f"ma: {code}", "loai: tom_tat_tu_dong (quét + chiến lược)", "tu: TikTok Manager",
        "gui: Gemini + Claude (để anh Nhơn đánh giá chéo khi cần)",
        f"lan_quet: {scan.get('finished_at') or scan.get('started_at') or '—'} (UTC) · {scan.get('message') or ''}",
        (f"chien_luoc: #{strategy_row['id']} · {strategy_row.get('source')} {strategy_row.get('model') or ''} · "
         f"${float(strategy_row.get('cost_usd') or 0):.4f}") if strategy_row else "chien_luoc: (không có)",
        "---", "", f"# Tóm tắt tự động {now:%d/%m/%Y %H:%M} (giờ VN)", "",
        "## 1. Số liệu kênh",
        f"- Follower: **{cur.get('follower_count', '—')}**" + (f" (24 giờ: {d24:+d})" if d24 is not None else "")
        + f" · tổng tim {cur.get('likes_count', '—')} · {cur.get('video_count', '—')} video",
        f"- Tim/view {lv['days']} ngày: **{lv['rate']}%** (mốc ≥ {lv['min']}%) · {lv['below']}/{lv['videos']} video dưới mốc",
    ]
    for t in ks["targets"]:
        L.append(f"- KPI {t['target']:,} follower trước".replace(",", ".") + f" {t['deadline']}: {t['pct']}% · tốc độ {t['pace']}/ngày, "
                 f"cần {t['need_per_day'] or '—'}/ngày · dự kiến đạt {t['eta']} · "
                 f"{'đúng tiến độ' if t['on_track'] else 'CHẬM tiến độ'}")
    L += ["", "| Khung giờ | Số video | View TB | Tim/view |", "|---|---|---|---|"]
    L += [f"| {s['label']} | {s['count']} | {s['avg_views']} | {s['like_view']}% |" for s in ks["slots"]]
    if top:
        L += ["", "**Top video 7 ngày:**", "", "| Đăng | Video | View | Tim | Bình luận | Tim/view |", "|---|---|---|---|---|---|"]
        for v in top:
            title = re.sub(r"[|\n]+", " ", (v.get("title") or v.get("description") or "")[:60])
            pl = v.get("posted_local")
            vw, lk = v.get("view_count") or 0, v.get("like_count") or 0
            L.append(f"| {pl:%d/%m %H:%M} | {title} | {vw} | {lk} | {v.get('comment_count') or 0} | "
                     f"{round(lk / vw * 100, 1) if vw else 0}% |" if pl else
                     f"| — | {title} | {vw} | {lk} | {v.get('comment_count') or 0} | — |")
    L += ["", "## 2. Quy trình (bước đang ⚠/❌)"]
    L += [f"- {x}" for x in issues] or ["- Tất cả các bước ✅"]
    L += ["", "## 3. Chiến lược vừa lập"]
    if plan:
        L += ["", "| Ngày | Giờ | Loại | Chủ đề | Cảnh báo tool |", "|---|---|---|---|---|"]
        for r in plan:
            topic = re.sub(r"[|\n]+", " ", r["chu_de"])[:80]
            L.append(f"| {r['ngay']} | {r['gio']} | L{r['loai']} | {topic} | {'; '.join(r['warnings']) or '—'} |")
    elif strategy_row:
        L.append("- (không tách được bảng lịch 7 ngày)")
    kpi_md = _section(md or "", r"KPI")
    if kpi_md:
        L += ["", "**Mục KPI của chiến lược (trích):**", "", kpi_md]
    warn_rows = [r for r in plan if r["warnings"]]
    L += ["", "## 4. Điểm cần đánh giá chéo"]
    pts = []
    if warn_rows:
        pts.append(f"{len(warn_rows)}/{len(plan)} dòng lịch có cảnh báo (xem bảng mục 3) — chiến lược có lệch kế hoạch đã chốt không?")
    for t in ks["targets"]:
        if not t["on_track"]:
            pts.append(f"KPI {t['target']} follower đang chậm ({t['pace']}/ngày so với cần {t['need_per_day']}/ngày): giữ mốc, "
                       "tăng quảng cáo Loại 3, hay dời hạn?")
    if not lv["ok"]:
        pts.append(f"Tim/view {lv['rate']}% dưới mốc {lv['min']}%.")
    if issues:
        pts.append(f"{len(issues)} bước quy trình chưa ✅ (mục 2).")
    L += [f"{i}. {x}" for i, x in enumerate(pts or ["Không có điểm bất thường."], 1)]
    L += ["", "_Gemini/Claude: khi anh Nhơn yêu cầu đánh giá chéo, đối chiếu bản này với QUY_TRINH_CHOT_V2 và kế hoạch 7 ngày "
          "đã chốt (11:00 Loại 3 · 12:00 Loại 2 tối đa 2/tuần · 19:00 Loại 1). Muốn tool tự sửa cấu hình (giờ đăng, KPI…), "
          "thêm khối `cap_nhat_tool:` vào thư đánh giá — xem trang /hop-thu. Tool tự sinh, không tốn token._"]
    return code, "\n".join(L)


def _doc_text(latest_first: list[dict]) -> str:
    head = ("# TÓM TẮT TỰ ĐỘNG – TIKTOK MANAGER\n\nTool ghi sau mỗi lần quét + chiến lược thành công. "
            f"Bản mới nhất ở trên cùng, giữ {KEEP_IN_DOC} bản. Bản đầy đủ tải ở trang /tom-tat của tool.\n")
    return head + "".join(f"\n\n---\n\n{r['md']}" for r in latest_first)


def push(sid: int) -> dict:
    """Ghi 7 bản mới nhất vào 2 Doc hộp thư. Trả về {target: 'ok' | lỗi}."""
    from .notebooklm import push_drive

    rows = db.query("SELECT * FROM cycle_summaries ORDER BY id DESC LIMIT ?", (KEEP_IN_DOC,))
    text = _doc_text(rows)
    res = {}
    for name, doc in (("gemini", settings.summary_doc_gemini), ("claude", settings.summary_doc_claude)):
        if not doc:
            res[name] = "chưa cấu hình Doc"
            continue
        try:
            push_drive(doc, text)
            res[name] = "ok"
        except Exception as e:  # noqa: BLE001
            res[name] = str(e)[:200]
    ok = [k for k, v in res.items() if v == "ok"]
    err = "; ".join(f"{k}: {v}" for k, v in res.items() if v != "ok")
    with db.tx() as c:
        c.execute("UPDATE cycle_summaries SET pushed=?, error=? WHERE id=?", (",".join(ok), err, sid))
    db.log_sync("cycle_summary", "ok" if ok and not err else ("partial" if ok else "error"), err or "Gemini + Claude")
    return res


def after_strategy(strategy_id: int) -> int | None:
    """Gọi sau khi chiến lược lập xong (tự động sau quét hoặc bấm tay). Lỗi không làm hỏng luồng chính."""
    try:
        init()
        st = db.query_one("SELECT * FROM strategies WHERE id=?", (strategy_id,))
        if not st or st.get("status") != "done":
            return None
        code, md = build(st["open_id"], st)
        scan = db.query_one("SELECT id FROM scans WHERE status='ok' ORDER BY id DESC LIMIT 1") or {}
        with db.tx() as c:
            sid = c.execute("INSERT INTO cycle_summaries(created_at, code, scan_id, strategy_id, md) VALUES(?,?,?,?,?)",
                            (db.now_iso(), code, scan.get("id"), strategy_id, md)).lastrowid
        push(sid)
        return sid
    except Exception:  # noqa: BLE001
        log.exception("cycle summary failed")
        return None


def all_rows(limit: int = 50) -> list[dict]:
    init()
    return db.query("SELECT id, created_at, code, strategy_id, pushed, error FROM cycle_summaries ORDER BY id DESC LIMIT ?",
                    (limit,))


def get(sid: int) -> dict | None:
    init()
    return db.query_one("SELECT * FROM cycle_summaries WHERE id=?", (sid,))
