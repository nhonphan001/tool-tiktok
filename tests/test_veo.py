import base64
import json
import os

os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("DISABLE_SCHEDULER", "1")

import pytest  # noqa: E402

from app import clips, db, media, packages, veo  # noqa: E402
from app.config import settings  # noqa: E402


@pytest.fixture
def env(monkeypatch, tmp_path):
    db.get_conn()
    packages.init()
    with db.tx() as c:
        c.execute("DELETE FROM packages")
        c.execute("DELETE FROM jobs")
        c.execute("DELETE FROM ai_usage")
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\xff\xd8\xffIMG")
    sa = tmp_path / "sa.json"
    sa.write_text("{}")
    monkeypatch.setattr(settings, "veo_enabled", True)
    monkeypatch.setattr(settings, "veo_model", "fast")
    monkeypatch.setattr(settings, "veo_resolution", "720p")
    monkeypatch.setattr(settings, "veo_budget_usd", 20.0)
    monkeypatch.setattr(settings, "gemini_vertex_project", "nangtam-gemini")
    monkeypatch.setattr(settings, "google_service_account_file", str(sa))
    monkeypatch.setattr(media, "cache_dir", lambda: str(tmp_path))
    monkeypatch.setattr(media, "fetch", lambda fid: (str(img), {"name": "a.jpg", "mimeType": "image/jpeg"}))
    monkeypatch.setattr(veo, "_token", lambda: "tok")
    monkeypatch.setattr(veo.time, "sleep", lambda s: None)
    pid = packages.save({"goi": "18", "loai": 1, "scene1": "x", **{f"image{i}": "I" * 30 + str(i) for i in range(1, 5)},
                         **{f"prompt{i}": f"Photorealistic video cảnh {i}" for i in range(1, 5)}})
    return pid


def test_estimate_and_budget(env, monkeypatch):
    e = veo.estimate(4)
    assert e["usd"] == 3.2 and e["per_clip"] == 0.8 and e["model"] == "Veo 3.1 Fast" and not e["over_budget"]
    monkeypatch.setattr(settings, "veo_resolution", "1080p")
    assert veo.estimate(4)["usd"] == 3.84
    monkeypatch.setattr(settings, "veo_model", "standard")
    assert veo.estimate(1)["usd"] == 3.2
    monkeypatch.setattr(settings, "veo_budget_usd", 5.0)
    assert veo.estimate(4)["over_budget"]


def test_request_body():
    body = veo.build_request("p", b"abc", "image/jpeg")
    par = body["parameters"]
    assert par["aspectRatio"] == "9:16" and par["durationSeconds"] == 8 and par["generateAudio"] is True
    assert par["sampleCount"] == 1 and "background music" in par["negativePrompt"]
    assert body["instances"][0]["image"]["bytesBase64Encoded"] == base64.b64encode(b"abc").decode()
    assert veo._url("predictLongRunning").startswith(
        "https://us-central1-aiplatform.googleapis.com/v1/projects/nangtam-gemini/locations/us-central1/publishers/"
        "google/models/veo-3.1-fast-generate-001:predictLongRunning") if settings.gemini_vertex_project else True


def test_run_scene_saves_clip_and_cost(env, monkeypatch):
    calls = []

    class R:
        def __init__(self, data):
            self.status_code, self._d, self.text = 200, data, json.dumps(data)

        def json(self):
            return self._d

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(url.rsplit(":", 1)[1])
        if url.endswith("predictLongRunning"):
            assert json["instances"][0]["prompt"] == "Photorealistic video cảnh 2"
            return R({"name": "projects/x/operations/op1"})
        n = calls.count("fetchPredictOperation")
        return R({"done": n >= 2, "response": {"videos": [{"bytesBase64Encoded": base64.b64encode(b"MP4DATA").decode(),
                                                             "mimeType": "video/mp4"}]}})

    monkeypatch.setattr(veo.httpx, "post", fake_post)
    cost = veo._run_scene(env, "2")
    assert cost == 0.8 and calls == ["predictLongRunning", "fetchPredictOperation", "fetchPredictOperation"]
    c = clips.load(packages.get(env))["2"]
    assert c["source"] == "veo" and c["status"] == "cho_duyet" and c["id"].startswith("veo:Goi_18_canh_2_veo_")
    assert open(veo.local_path(c["id"]), "rb").read() == b"MP4DATA"
    assert db.query_one("SELECT cost_usd FROM ai_usage WHERE kind='veo'")["cost_usd"] == 0.8
    assert veo.month_spent() == 0.8
    # anh Nhơn thả đúng file này vào thư mục 02 → tool dùng bản Drive, giữ trạng thái duyệt
    clips.set_status(env, "2", "dat")
    cl, _ = clips.sync(packages.get(env), [{"id": "D" * 33, "name": c["name"], "modifiedTime": "2099-01-01T00:00:00Z"}])
    assert cl["2"]["id"] == "D" * 33 and cl["2"]["status"] == "dat" and cl["2"]["veo_local"] == c["id"]


def test_filtered_and_errors(env, monkeypatch):
    with pytest.raises(veo.VeoError):
        veo._extract_video({"response": {"raiMediaFilteredCount": 1, "raiMediaFilteredReasons": ["person"]}})
    monkeypatch.setattr(settings, "veo_enabled", False)
    with pytest.raises(veo.VeoError):
        veo.start(env, ["1"])
    assert veo.local_path("veo:../../etc/passwd") == ""


def test_route_requires_matching_confirmation(env, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    started = []
    monkeypatch.setattr(veo, "start", lambda pid, sc: started.append(sc))
    c = TestClient(app)
    c.post("/login", data={"password": settings.app_password})
    c.post(f"/packages/{env}/veo", data={"scenes": "1,2,3,4", "confirm_usd": "1.00"})
    assert started == []  # giá xác nhận không khớp → không chạy
    c.post(f"/packages/{env}/veo", data={"scenes": "1,2,3,4", "confirm_usd": "3.20"})
    assert started == [["1", "2", "3", "4"]]
    html = c.get(f"/packages/{env}").text
    assert "Tạo cả 4 cảnh bằng Veo" in html and "3.20" in html
