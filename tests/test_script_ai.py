import json
import os

os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("DISABLE_SCHEDULER", "1")

from app import db, gemini_requests as gr, packages, script_ai, strategy  # noqa: E402
from app.config import settings  # noqa: E402

GOOD = ["Chị Canh Ngọ chín mươi, sang năm hai không hai bảy nên tiến mạnh hay giữ nhịp chậm lại? Comment năm sinh để Cô Kim xem giúp, rồi nghe Cô Kim nói nha.",
        "Canh là thanh kim loại thô ngồi trên chữ Ngọ là lửa mùa hè, nên chị giống thanh kiếm được lửa rèn, càng va chạm càng cứng cỏi, nói thẳng mà sống rất tình.",
        "Mệnh Lộ Bàng Thổ là đất bên đường, ai đi qua cũng dựa được, nên chị hay là chỗ dựa cho cả nhà, mà ít ai hỏi chị có mệt hay không đâu.",
        "Năm Bính Ngọ này, Ngọ gặp Ngọ là tự hình, Bính lại là Thất Sát với Canh, nên nhiều chị thấy áp lực dồn dập, hay tự trách mình chưa đủ tốt với ai.",
        "Nhiều người không biết, chị sinh trước sáng mùng bốn tháng hai năm chín mươi thì Bát Tự tính là Kỷ Tỵ, còn sinh tháng Một năm chín mốt vẫn là Canh Ngọ.",
        "Sang năm Đinh Mùi, Ngọ với Mùi là lục hợp, Đinh là Chính Quan với Canh, công việc dễ có người ghi nhận, nhưng trách nhiệm cũng nặng hơn trước nhiều lắm.",
        "Nên câu trả lời là tiến, nhưng tiến từng bước chắc, đừng gồng một mình, mệt thì nghỉ ngơi nha. Để lại ngày sinh dưới bình luận để Cô Kim giải mã nha."]


def _resp(canh, hook="Nữ Canh Ngọ 1990 · Năm Đinh Mùi 2027", cap="Chị nào tuổi Canh Ngọ 1990 comment năm sinh nha #cokim"):
    return json.dumps({"tieu_de": "x", "canh": canh, "chu_tren_hinh": hook, "chu_chuong": {"2": "1. Tính cách"},
                       "caption": cap, "binh_luan_ghim": "Chị em Canh Ngọ năm nay áp lực nhất chuyện gì?",
                       "goi_y_hinh": ["rót trà"] * len(canh)}, ensure_ascii=False)


def test_year_facts():
    f = " ".join(script_ai.year_facts(1990))
    for s in ("Canh Ngọ", "Lộ Bàng Thổ", "Kỷ Tỵ", "Ngọ – Ngọ tự hình", "Ngọ – Mùi lục hợp", "Thất Sát", "Chính Quan", "04/02/1990"):
        assert s in f, s


def test_draft_fixes_then_letter(monkeypatch):
    db.get_conn()
    gr.init()
    monkeypatch.setattr(settings, "goi_reserved_until", 34)
    rid = gr.create("Lá số nữ Canh Ngọ 1990 năm 2027", "Nữ Canh Ngọ 1990", {"loai": 1, "goal": "comment", "scenes": 7,
                                                                             "o_phep_thu": "12:30 × kiểu B"})
    req = gr.get(rid)
    assert int(req["goi"]) >= 35  # không trùng số Claude đã giữ
    calls = []
    bad = list(GOOD)
    bad[0] = "Chào cả nhà, hôm nay Cô Kim kể chuyện người tuổi Canh Ngọ, mình cùng nghe nha, chuyện dài lắm đó."  # thiếu CTA sớm, ngắn

    def fake(prompt, system, json_mode):
        calls.append(prompt)
        assert "BỘ QUY TẮC KỊCH BẢN" in system and "Lộ Bàng Thổ" in prompt and "12:30 × kiểu B" in prompt
        return (_resp(bad) if len(calls) == 1 else _resp(GOOD)), {"cost_usd": 0.002}
    monkeypatch.setattr(strategy, "record_usage", lambda *a, **k: None)
    monkeypatch.setattr(strategy, "call_gemini", fake)
    msg = script_ai.draft_and_store(rid)
    assert len(calls) == 2 and "BỘ KIỂM TRA BÁO" in calls[1] and "2 lượt" in msg
    req = gr.get(rid)
    kb = req["opts"]["kich_ban"]
    assert kb["issues"] == [] and kb["canh"][0].startswith("Chị Canh Ngọ")
    letter = req["letter_md"]
    assert "Lời thoại SOẠN SẴN — GIỮ NGUYÊN VĂN" in letter and "Bộ quy tắc kịch bản" in letter and GOOD[4] in letter


def test_rules_in_strategy_prompt_and_settings():
    assert "BỘ QUY TẮC KỊCH BẢN" in strategy.full_system_prompt()
    from fastapi.testclient import TestClient
    from app.main import app

    c = TestClient(app)
    c.post("/login", data={"password": settings.app_password})
    page = c.get("/settings").text
    assert "Bộ quy tắc kịch bản" in page and 'name="goi_reserved_until"' in page
    assert "Gemini API soạn sẵn lời thoại" in c.get("/requests").text
