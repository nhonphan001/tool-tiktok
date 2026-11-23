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
    assert "Southern Vietnamese accent" in g["input"]["prompt"] and g["input"]["text"] == "Chào con"
    c = tts.build_request("Chào con", "chirp_aoede")
    assert c["voice"]["name"] == "vi-VN-Chirp3-HD-Aoede" and "prompt" not in c["input"]
    assert tts.syllables("Chào con, Cô Kim pha trà.") == 6


def test_samples_choose_and_scenes(env, monkeypatch):
    r = tts.make_samples(tts.SAMPLE_TEXT)
    assert not r["errors"] and set(r["samples"]) == {"_text", *tts.VOICES}
    s = r["samples"]["g_kore"]
    assert s["seconds"] == 7.5 and s["sps"] == round(tts.syllables(tts.SAMPLE_TEXT) / 7.5, 2)
    assert env[0][1]["x-goog-user-project"] == "nangtam-gemini"
    assert db.query_one("SELECT COUNT(*) n FROM ai_usage WHERE kind='tts'")["n"] == len(tts.VOICES) == 15
    # xếp hạng theo độ gần cao độ mẫu chuẩn
    smp = {"g_kore": {"f0": 300, "sps": 3.9, "lead": 0.1}, "g_leda": {"f0": 225, "sps": 3.9, "lead": 0.1},
           "g_aoede": {"f0": 219, "sps": 4.6, "lead": 0.1}}
    assert tts.rank(smp, {"f0": 219}) == ["g_leda", "g_aoede", "g_kore"]

    pid = packages.save({"goi": "19", "loai": 3, **{f"scene{i}": f"Lời cảnh {i} nhé con" for i in range(1, 5)}})
    with pytest.raises(tts.TTSError):
        tts.make_scenes(packages.get(pid))  # chưa chọn giọng
    monkeypatch.setattr(settings, "tts_voice", "g_sulafat")
    out = tts.make_scenes(packages.get(pid))
    assert out["done"] == ["1", "2", "3", "4"] and env[-1][2]["input"]["text"] == "Lời cảnh bốn nhé con"
    info = tts.scene_info(packages.get(pid))
    assert info["1"]["name"] == "Goi_19_canh_1_giong.wav" and info["1"]["fits_8s"]
    # thư GHEP kèm phần lồng giọng khi clip không tiếng
    cl = {str(k): {"id": f"X{k}", "name": f"Goi_19_canh_{k}_veo_khongtieng_1.mp4", "status": "dat", "audio": False}
          for k in range(1, 5)}
    _, md = clips.ghep_letter(packages.get(pid), cl)
    assert "Phương án B" in md and "Goi_19_canh_3_giong.wav" in md and "−14 LUFS" in md and "Gemini · Sulafat" in md


def test_speakable_numbers():
    sp = tts.speakable
    assert sp("Sáng 20/11, chúc") == "Sáng hai mươi tháng mười một, chúc"
    assert sp("ngày 1/1/2026") == "ngày một tháng một năm hai nghìn không trăm hai mươi sáu"
    assert sp("giảm 15%") == "giảm mười lăm phần trăm"
    assert sp("21, 24, 25, 105, 2005") == "hai mươi mốt, hai mươi tư, hai mươi lăm, một trăm lẻ năm, hai nghìn không trăm lẻ năm"
    from app import packages
    assert packages.syllables("Cả nhà gửi lời chúc 20/11 nhé") == 11


def test_retry_and_missing(env, monkeypatch):
    calls = []

    class R:
        def __init__(self, code):
            self.status_code, self.text = code, '{"error": {"code": %d}}' % code

        def json(self):
            return {"audioContent": base64.b64encode(_wav(7.0)).decode()}

    seq = [429, 499, 200]
    monkeypatch.setattr(tts.httpx, "post", lambda *a, **k: (calls.append(1), R(seq[len(calls) - 1] if len(calls) <= 3 else 200))[1])
    monkeypatch.setattr("time.sleep", lambda s: None)
    assert tts.synthesize("Chào con", "g_kore")[:4] == b"RIFF" and len(calls) == 3
    tts.make_samples("Câu thử", ["g_kore", "g_leda"])
    assert set(tts.missing("Câu thử")) == set(tts.VOICES) - {"g_kore", "g_leda"}
    assert tts.missing("Câu khác") == list(tts.VOICES)


def test_reference_analyze():
    info = tts.analyze(tts.REF_DEFAULT)
    if info:  # có ffmpeg
        assert -16 < info["lufs"] < -13 and 0.5 < info["lead"] < 0.9 and 8 < info["speech"] < 9.5
        assert 180 < info.get("f0", 219) < 260


def test_routes(env, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    c = TestClient(app)
    c.post("/login", data={"password": settings.app_password})
    page = c.get("/giong").text
    assert "Giọng Cô Kim" in page and "Hồ sơ giọng" in page and "/giong/mau-chuan" in page
    assert c.get("/giong/mau-chuan").headers["content-type"] == "audio/mpeg"
    c.post("/giong/ho-so", data={"style": "Giọng nữ miền Nam, ấm."})
    assert settings.tts_style == "Giọng nữ miền Nam, ấm." and tts.build_request("x", "g_kore")["input"]["prompt"] == settings.tts_style
    c.post("/giong/ho-so", data={"style": ""})
    assert "AUDIO PROFILE" in tts.style()
    c.post("/giong/mau", data={"text": "Chào con, uống trà với Cô nhé."})
    import time
    for _ in range(600):
        if not tts.job().get("running"):
            break
        time.sleep(0.05)
    assert tts.job()["done"] == len(tts.VOICES)
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


def test_time_year_and_loose_prompt_match():
    from app import packages
    assert tts.speakable("Tối nay 19h00, Cô Kim") == "Tối nay mười chín giờ, Cô Kim"
    assert tts.speakable("lúc 19:30") == "lúc mười chín giờ ba mươi"
    assert tts.speakable("Đinh Mão 1987", year_digits=True) == "Đinh Mão một chín tám bảy"
    assert packages.syllables("tuổi Đinh Mão 1987") == 7
    p = {"goi": "1", "loai": 3, "scene1": "Tối nay 19h00 Cô Kim gửi chị em tuổi Đinh Mão 1987 lời chúc",
         "prompt1": 'she says: "Tối nay mười chín giờ Cô Kim gửi chị em tuổi Đinh Mão mười chín tám mươi bảy lời chúc"'}
    assert not [i for i in packages.check(p)["items"] if i["rule"] == "Prompt"]
    p["prompt1"] = 'she says: "Tối nay Cô Kim gửi bạn bè lời chúc"'
    assert [i for i in packages.check(p)["items"] if i["rule"] == "Prompt"]


def test_syllable_range_follows_clip_seconds(monkeypatch):
    from app import packages
    monkeypatch.setattr(settings, "clip_seconds", 10)
    assert packages.syllable_range() == (24, 34)
    p = {"goi": "1", "loai": 3, "scene1": " ".join(["trà"] * 32)}
    assert not [i for i in packages.check(p)["items"] if i["rule"] == "Nhịp cảnh"]
    monkeypatch.setattr(settings, "clip_seconds", 8)
    assert packages.syllable_range() == (24, 28)
    assert [i for i in packages.check(p)["items"] if i["rule"] == "Nhịp cảnh"]
