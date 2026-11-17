"""Gắn nhãn video (Gói, mã sản phẩm, hành, nhóm nội dung, giỏ hàng) và kiểm tra tuân thủ từng video."""
import json
import logging
from statistics import mean

from . import analytics, compliance, db, products, strategy

log = logging.getLogger(__name__)

CONTENT_GROUPS = {
    1: "Giải mã lá số cá nhân",
    2: "Theo tuổi, con giáp, giờ sinh",
    3: "Nhân duyên, gia đạo",
    4: "Trả lời bình luận xin xem lá số",
    5: "Trà sáng chữa lành, đếm ngược",
    6: "Kiến thức Bát Tự, Dụng Thần",
}
ELEMENTS = products.ELEMENTS
FIELDS = ("goi", "product_code", "element", "content_group", "has_cart", "note")


def get_all() -> dict[str, dict]:
    return {r["video_id"]: r for r in db.query("SELECT * FROM video_tags")}


def save(video_id: str, data: dict, source: str = "manual") -> None:
    row = {k: data.get(k) for k in FIELDS}
    if row["content_group"] in ("", None):
        row["content_group"] = None
    else:
        row["content_group"] = int(row["content_group"])
    if row["has_cart"] in ("", None):
        row["has_cart"] = None
    else:
        row["has_cart"] = 1 if str(row["has_cart"]).lower() in ("1", "true", "yes", "co") else 0
    if row["product_code"]:
        row["product_code"] = str(row["product_code"]).strip().upper()
        p = products.by_code().get(row["product_code"])
        if p and not row["element"]:
            row["element"] = p["element"]
    with db.tx() as c:
        c.execute(
            "INSERT INTO video_tags(video_id, goi, product_code, element, content_group, has_cart, note, source,"
            " updated_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(video_id) DO UPDATE SET goi=excluded.goi,"
            " product_code=excluded.product_code, element=excluded.element, content_group=excluded.content_group,"
            " has_cart=excluded.has_cart, note=excluded.note, source=excluded.source, updated_at=excluded.updated_at",
            (video_id, row["goi"], row["product_code"], row["element"], row["content_group"], row["has_cart"],
             row["note"], source, db.now_iso()),
        )


def videos_with_tags(open_id: str) -> list[dict]:
    """Danh sách video kèm nhãn và kết quả kiểm tra tuân thủ caption."""
    tags = get_all()
    prods = products.by_code()
    out = []
    for v in analytics.get_videos(open_id):
        t = tags.get(v["id"], {})
        v["tag"] = t
        has_cart = None if t.get("has_cart") is None else bool(t["has_cart"])
        text = f"{v.get('title') or ''}\n{v.get('description') or ''}"
        v["compliance"] = compliance.check(text, has_cart)
        v["like_view"] = round((v["like_count"] or 0) / v["view_count"] * 100, 2) if v["view_count"] else 0
        v["product"] = prods.get(t.get("product_code") or "")
        out.append(v)
    return out


def compliance_issues(open_id: str) -> list[dict]:
    return [v for v in videos_with_tags(open_id) if v["compliance"]["level"] != "ok"]


def _group(vs: list[dict], key) -> list[dict]:
    groups: dict = {}
    for v in vs:
        k = key(v)
        if k in (None, ""):
            continue
        groups.setdefault(k, []).append(v)
    rows = []
    for k, items in groups.items():
        rows.append({
            "key": k,
            "count": len(items),
            "avg_views": round(mean(x["view_count"] or 0 for x in items)),
            "avg_engagement": round(mean(x["engagement"] for x in items), 2),
            "like_view": round(mean(x["like_view"] for x in items), 2),
        })
    return sorted(rows, key=lambda r: r["avg_views"], reverse=True)


def tag_analysis(open_id: str) -> dict:
    vs = videos_with_tags(open_id)
    tagged = [v for v in vs if v["tag"]]
    prods = products.by_code()
    by_group = _group(tagged, lambda v: v["tag"].get("content_group"))
    for r in by_group:
        r["label"] = f"{r['key']}. {CONTENT_GROUPS.get(r['key'], '')}"
    by_element = _group(tagged, lambda v: v["tag"].get("element"))
    for r in by_element:
        r["label"] = r["key"]
    by_product = _group(tagged, lambda v: v["tag"].get("product_code"))
    for r in by_product:
        p = prods.get(r["key"])
        r["label"] = f"{r['key']} – {p['name']}" if p else r["key"]
    by_cart = _group(tagged, lambda v: None if v["tag"].get("has_cart") is None else
                     ("Có giỏ hàng" if v["tag"]["has_cart"] else "Không giỏ hàng"))
    for r in by_cart:
        r["label"] = r["key"]
    return {"total": len(vs), "tagged": len(tagged), "by_group": by_group, "by_element": by_element,
            "by_product": by_product, "by_cart": by_cart}


CLASSIFY_SYSTEM = """Bạn phân loại video TikTok của kênh Bát Tự "Tiệm Trà Giải Mã – Cô Kim" dựa trên tiêu đề/caption.
Trả về DUY NHẤT một mảng JSON, mỗi phần tử:
{"id": "<id video>", "content_group": 1-6, "element": "Kim|Mộc|Thủy|Hỏa|Thổ|", "product_code": "<mã trong danh sách hoặc rỗng>",
 "has_cart": true|false|null, "goi": "<số gói nếu caption có ghi, ngược lại rỗng>"}
Nhóm nội dung: 1 Giải mã lá số cá nhân; 2 Theo tuổi, con giáp, giờ sinh; 3 Nhân duyên, gia đạo (vợ chồng, mẹ con);
4 Trả lời bình luận xin xem lá số; 5 Trà sáng chữa lành, đếm ngược cuối năm; 6 Kiến thức Bát Tự, Dụng Thần.
element = hành Dụng Thần / hành chủ đạo được nhắc trong video; để rỗng nếu không rõ.
product_code chỉ điền khi caption nhắc rõ sản phẩm trùng tên trong danh sách; KHÔNG đoán.
has_cart = true nếu caption nhắc giỏ hàng/sản phẩm, null nếu không rõ."""


def classify(open_id: str, limit: int = 60) -> tuple[str, dict]:
    """Phân loại các video chưa có nhãn tay bằng Gemini. Chạy trong jobs (nền)."""
    tags = get_all()
    vids = [v for v in analytics.get_videos(open_id) if tags.get(v["id"], {}).get("source") != "manual"
            and not tags.get(v["id"])][:limit]
    if not vids:
        return "Không còn video nào cần phân loại", None
    prods = products.all_products()
    plist = "\n".join(f"{p['code']} | {p['element']} | {p['name']}" for p in prods) or "(chưa đồng bộ bảng sản phẩm)"
    vlist = "\n".join(f"{v['id']} | {(v.get('title') or '')[:150]} | {(v.get('description') or '')[:300]}" for v in vids)
    prompt = f"DANH SÁCH SẢN PHẨM (mã | hành | tên):\n{plist}\n\nVIDEO (id | tiêu đề | caption):\n{vlist}"
    text, usage = strategy.call_gemini(prompt, system=CLASSIFY_SYSTEM, json_mode=True)
    strategy.record_usage("classify", None, usage)
    try:
        start, end = text.find("["), text.rfind("]")
        items = json.loads(text[start:end + 1])
    except (ValueError, TypeError):
        raise RuntimeError(f"Gemini trả về không phải JSON: {text[:200]}")
    ids = {v["id"] for v in vids}
    codes = {p["code"] for p in prods}
    n = 0
    for it in items:
        vid = str(it.get("id", ""))
        if vid not in ids:
            continue
        code = str(it.get("product_code") or "").upper()
        elem = products.normalize_element(str(it.get("element") or ""))
        save(vid, {
            "goi": str(it.get("goi") or ""),
            "product_code": code if code in codes else "",
            "element": elem if elem in ELEMENTS else "",
            "content_group": it.get("content_group") if it.get("content_group") in range(1, 7) else None,
            "has_cart": None if it.get("has_cart") is None else bool(it.get("has_cart")),
            "note": "",
        }, source="ai")
        n += 1
    return f"Gemini đã phân loại {n}/{len(vids)} video", usage
