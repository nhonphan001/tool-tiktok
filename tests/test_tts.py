import base64
import io
import os
import wave

os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("DISABLE_SCHEDULER", "1")

import pytest  # noqa: E402

from app import clips, db, media, packages, tts  # noqa: E402
from app.config import settings  # noqa: E402


def _wav(sec: float) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\0\0" * int(24000 * sec))
    return buf.getvalue()


@pytest.fixture
def env(monkeypatch, tmp_path):
    db.get_conn()
    packages.init()
    with db.tx() as c:
        c.execute("DELETE FROM packages")
        c.execute("DELETE FROM ai_usage")
    sa = tmp_path / "sa.json"
    sa.write_text("{}")
    monkeypatch.setattr(settings, "gemini_vertex_project", "nangtam-gemini")
    monkeypatch.setattr(settings, "google_service_account_file", str(sa))
    monkeypatch.setattr(settings, "tts_voice", "")
    monkeypatch.setattr(media, "cache_dir", lambda: str(tmp_path))
    monkeypatch.setattr(tts, "_token", lambda: "tok")
    sent = []

    class R:
        status_code = 200
        text = ""

        def __init__(self, sec):
            self.sec = sec

        def json(self):
            return {"audioContent": base64.b64encode(_wav(self.sec)).decode()}

    def fake_post(url, headers=None, json=None, timeout=None):
        sent.append((url, headers, json))
        return R(7.5)

    monkeypatch.setattr(tts.httpx, "post", fake_post)
    return sent


def test_request_bodies():
    g = tts.build_request("Chào con", "g_sulafat")
    assert g["voice"] == {"languageCode": "vi-VN", "name": "Sulafat", "modelName": "gemini-2.5-flash-tts"}
    assert "miền Nam" in g["input"]["prompt"] and g["input"]["text"] == "Chào con"
    c = tts.build_request("Chào con", "chirp_aoede")
    assert c["voice"]["name"] == "vi-VN-Chirp3-HD-Aoede" and "prompt" not in c["input"]
    assert tts.syllables("Chào con, Cô Kim pha trà.") == 6


def test_samples_choose_and_scenes(env, monkeypatch):
    r = tts.make_samples(tts.SAMPLE_TEXT)
    assert not r["errors"] and set(r["samples"]) == {"_text", *tts.VOICES}
    s = r["samples"]["g_kore"]
    assert s["seconds"] == 7.5 and s["sps"] == round(tts.syllables(tts.SAMPLE_TEXT) / 7.5, 2)
    assert env[0][1]["x-goog-user-project"] == "nangtam-gemini"
    assert db.query_one("SELECT COUNT(*) n FROM ai_usage WHERE kind='tts'")["n"] == 4

    pid = packages.save({"goi": "19", "loai": 3, **{f"scene{i}": f"Lời cảnh {i} nhé con" for i in range(1, 5)}})
    with pytest.raises(tts.TTSError):
        tts.make_scenes(packages.get(pid))  # chưa chọn giọng
    monkeypatch.setattr(settings, "tts_voice", "g_sulafat")
    out = tts.make_scenes(packages.get(pid))
    assert out["done"] == ["1", "2", "3", "4"] and env[-1][2]["input"]["text"] == "Lời cảnh 4 nhé con"
    info = tts.scene_info(packages.get(pid))
    assert info["1"]["name"] == "Goi_19_canh_1_giong.wav" and info["1"]["fits_8s"]
    # thư GHEP kèm phần lồng giọng khi clip không tiếng
    cl = {str(k): {"id": f"X{k}", "name": f"Goi_19_canh_{k}_veo_khongtieng_1.mp4", "status": "dat", "audio": False}
          for k in range(1, 5)}
    _, md = clips.ghep_letter(packages.get(pid), cl)
    assert "Phương án B" in md and "Goi_19_canh_3_giong.wav" in md and "−14 LUFS" in md and "Gemini · Sulafat" in md


def test_routes(env, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    c = TestClient(app)
    c.post("/login", data={"password": settings.app_password})
    assert "Giọng Cô Kim" in c.get("/giong").text
    c.post("/giong/mau", data={"text": "Chào con, uống trà với Cô nhé."})
    html = c.get("/giong").text
    assert "/giong/mau/g_aoede.wav" in html and "Chọn giọng này" in html
    assert c.get("/giong/mau/g_aoede.wav").headers["content-type"] == "audio/wav"
    assert c.get("/giong/mau.zip").status_code == 200
    c.post("/giong/chon", data={"key": "chirp_aoede"})
    assert settings.tts_voice == "chirp_aoede"
    pid = packages.save({"goi": "19", "loai": 3, **{f"scene{i}": f"Lời cảnh {i}" for i in range(1, 5)}})
    c.post(f"/packages/{pid}/giong")
    assert c.get(f"/media/{pid}/giong2").headers["content-type"] == "audio/wav"
    db.save_setting("tts_voice", "")
