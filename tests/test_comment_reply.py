import os

os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("DISABLE_SCHEDULER", "1")

from app import comment_reply, comments, strategy  # noqa: E402
from app.config import settings  # noqa: E402

MSG = """C xin chào cô Kim.
C muốn xem luận quẻ kinh dịch cho năm mới 2027 từ cô kim gieo ạ .
Khách hàng này đã nhờ Cô Kim xem bát tự trước đây:
Chị Ngọc: sinh ngày 20/2/1973 dương lịch lúc 7 giờ tối"""


def test_anonymize_and_prefill():
    assert comment_reply.anonymize("Chị Ngọc nhờ Cô Kim, @ngoc.73") == "một chị nhờ Cô Kim, (nick)"
    row = [r for r in comments.analyze(MSG) if r.get("chart")][0]
    pre = comment_reply.package_prefill(MSG, row)
    assert pre["loai"] == 1 and pre["dd"] == 20 and pre["t"] == "19:00" and pre["gioi"] == "nu"
    assert "Quý Sửu" in pre["title"] and "Ngọc" not in pre["brief"] and "KHÔNG gieo quẻ" in pre["brief"]
    assert "Đinh Hỏa" in pre["brief"]


def test_quick_reply_route_and_package(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    calls = []

    def fake(prompt, system="", json_mode=False):
        calls.append(prompt)
        txt = ('{"tra_loi": "Chị ơi, Cô Kim đọc thấy lá số Đinh Hỏa của chị ấm áp lắm, link ở bio nha"}' if len(calls) == 1 else
               '{"tra_loi": "Chị ơi, Cô Kim xem theo Bát Tự ngày giờ sinh nha, lá số Đinh Hỏa của chị rất ấm, Cô Kim sẽ giải mã kỹ trong video tối nay 🍵", "goi_y_video": "Nữ Quý Sửu 1973 bước vào năm 2027"}')
        return txt, {"input_tokens": 1, "output_tokens": 1, "thinking_tokens": 0, "total_tokens": 2, "cost_usd": 0.001,
                     "endpoint": "aistudio"}
    monkeypatch.setattr(strategy, "call_gemini", fake)
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    c = TestClient(app)
    c.post("/login", data={"password": settings.app_password})
    html = c.post("/laso/comments", data={"text": MSG}).text
    assert "Trả lời nhanh (AI)" in html and "Tạo gói SX" in html
    d = c.post("/api/laso/reply", data={"text": MSG, "line": 4}).json()
    assert len(calls) == 2 and "bio" not in d["reply"] and d["level"] == "ok" and "Ngọc" not in calls[0]
    assert "20/02/1973 19:00 = Quý Sửu" in calls[0]
    assert c.post("/api/laso/reply", data={"text": MSG, "line": 1}).status_code == 400
    page = c.post("/laso/package", data={"text": MSG, "line": 4}).text
    assert 'value="1973"' in page and "Trả lời một chị Quý Sửu 1973" in page and "tin nhắn khách" in page
