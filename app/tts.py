"""Giọng đọc Cô Kim bằng TTS (phương án B: Veo không tiếng + 1 giọng TTS cố định).

- Google Cloud Text-to-Speech (texttospeech.googleapis.com), xác thực bằng service account (scope cloud-platform).
  Cần bật "Cloud Text-to-Speech API" trong project Vertex.
- 2 loại giọng: Gemini TTS (gemini-2.5-flash-tts, điều khiển giọng bằng lời dặn: miền Nam, ấm, chậm) và Chirp 3 HD.
- Trang /giong: tạo 4 mẫu cùng 1 câu → nghe, xem tốc độ (âm tiết/giây) → chọn 1 giọng thương hiệu (cài đặt tts_voice).
- Gói SX: tạo 4 file giọng Goi_<n>_canh_<k>_giong.wav theo lời thoại 4 cảnh để Gemini ghép ở P8b (chuẩn hoá −14 LUFS).
Giá (ước tính, rất nhỏ): Gemini 2.5 Flash TTS ~$0,50/1 triệu token chữ + ~$10/1 triệu token âm thanh (25 token/giây);
Chirp 3 HD ~$30/1 triệu ký tự. Một câu 8 giây < $0,005.
"""
import base64
import io
import json
import os
import re
import shutil
import subprocess
import wave
import zipfile

import httpx

from . import db
from .config import settings

URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
GEMINI_TTS_MODEL = "gemini-2.5-flash-tts"
STYLE_FALLBACK = ("Đọc bằng giọng nữ miền Nam (Sài Gòn), khoảng 25–30 tuổi, ấm áp, nhẹ nhàng, thân mật như đang rót trà tâm sự "
         "với người nghe. Tốc độ chậm rãi, khoảng 3,6 âm tiết mỗi giây, ngắt nghỉ tự nhiên ở dấu phẩy. Đọc đúng dấu "
         "tiếng Việt, không thêm từ, không nhạc nền.")
VOICES = {  # khoá: (loại, tên giọng, nhãn, mô tả) — 14 giọng nữ Gemini TTS + 1 giọng Chirp tiếng Việt
    "g_sulafat": ("gemini", "Sulafat", "Gemini · Sulafat", "ấm"),
    "g_aoede": ("gemini", "Aoede", "Gemini · Aoede", "nhẹ, thoáng"),
    "g_kore": ("gemini", "Kore", "Gemini · Kore", "chắc, rõ chữ"),
    "g_vindemiatrix": ("gemini", "Vindemiatrix", "Gemini · Vindemiatrix", "dịu dàng"),
    "g_achernar": ("gemini", "Achernar", "Gemini · Achernar", "mềm, nhỏ nhẹ"),
    "g_despina": ("gemini", "Despina", "Gemini · Despina", "mượt"),
    "g_callirrhoe": ("gemini", "Callirrhoe", "Gemini · Callirrhoe", "thoải mái, tự nhiên"),
    "g_erinome": ("gemini", "Erinome", "Gemini · Erinome", "trong, rõ"),
    "g_gacrux": ("gemini", "Gacrux", "Gemini · Gacrux", "chín chắn, trầm"),
    "g_leda": ("gemini", "Leda", "Gemini · Leda", "trẻ trung"),
    "g_autonoe": ("gemini", "Autonoe", "Gemini · Autonoe", "sáng"),
    "g_zephyr": ("gemini", "Zephyr", "Gemini · Zephyr", "tươi, sáng"),
    "g_laomedeia": ("gemini", "Laomedeia", "Gemini · Laomedeia", "vui, nhiều năng lượng"),
    "g_pulcherrima": ("gemini", "Pulcherrima", "Gemini · Pulcherrima", "dứt khoát"),
    "chirp_aoede": ("chirp", "vi-VN-Chirp3-HD-Aoede", "Chirp 3 HD · Aoede", "giọng có sẵn tiếng Việt, không chỉnh được vùng miền"),
}
SAMPLE_TEXT = ("Sáng 20/11, Cô Kim dọn trà ra vườn hoa đón nắng sớm. Mời cả nhà nhấp ngụm trà ấm, để lòng dịu lại "
               "giữa ngày bận rộn và chúc quý thầy cô mãi bình an nhé.")  # 40 âm tiết ≈ 10 giây (mẫu của Gemini 20/11)
RATE = 24000
RETRY_WAITS = (8.0, 20.0, 40.0)  # giây chờ trước mỗi lần thử lại khi Google báo hạn mức/quá tải
REF_DEFAULT = os.path.join(os.path.dirname(__file__), "defaults", "co_kim_mau_chuan.mp3")


def style() -> str:
    """Hồ sơ giọng Cô Kim (anh Nhơn soạn) — sửa được trên trang /giong."""
    return (settings.tts_style or "").strip() or STYLE_FALLBACK
SYL_MIN, SYL_MAX = 3.8, 4.0  # anh Nhơn chốt 20/11


class TTSError(RuntimeError):
    pass


def ready() -> tuple[bool, str]:
    if not settings.gemini_vertex_project:
        return False, "Chưa có ID project Vertex (Cài đặt → Gemini)"
    if not os.path.exists(settings.google_service_account_file or ""):
        return False, "Thiếu file service account"
    return True, ""


def voice_key() -> str:
    return settings.tts_voice if settings.tts_voice in VOICES else ""


_DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]


def _num_vi(n: int) -> str:
    """Đọc số nguyên 0–999999 thành chữ (giọng miền Nam: 'không' cho hàng chục 0 → 'lẻ')."""
    if n < 10:
        return _DIGITS[n]
    if n < 100:
        t, u = divmod(n, 10)
        head = "mười" if t == 1 else _DIGITS[t] + " mươi"
        if u == 0:
            return head
        tail = {1: "mốt" if t > 1 else "một", 4: "tư" if t > 1 else "bốn", 5: "lăm"}.get(u, _DIGITS[u])
        return f"{head} {tail}"
    if n < 1000:
        h, r = divmod(n, 100)
        if r == 0:
            return f"{_DIGITS[h]} trăm"
        return f"{_DIGITS[h]} trăm " + (f"lẻ {_DIGITS[r]}" if r < 10 else _num_vi(r))
    k, r = divmod(n, 1000)
    if r == 0:
        return f"{_num_vi(k)} nghìn"
    if r < 10:
        return f"{_num_vi(k)} nghìn không trăm lẻ {_DIGITS[r]}"
    return f"{_num_vi(k)} nghìn " + (f"không trăm {_num_vi(r)}" if r < 100 else _num_vi(r))


def speakable(text: str) -> str:
    """Đổi số, ngày tháng, % sang chữ trước khi gửi TTS (phụ đề vẫn giữ số).
    '20/11' → 'hai mươi tháng mười một'; '20/11/2026' → '… năm hai nghìn không trăm hai mươi sáu'."""
    t = text or ""

    def _date(m):
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        out = f"{_num_vi(d)} tháng {_num_vi(mo)}"
        return out + (f" năm {_num_vi(int(y))}" if y else "")

    t = re.sub(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?:/(\d{4}))?(?![\d/])",
               lambda m: _date(m) if 1 <= int(m.group(1)) <= 31 and 1 <= int(m.group(2)) <= 12 else m.group(0), t)
    t = re.sub(r"(\d+)\s*%", lambda m: f"{_num_vi(int(m.group(1)))} phần trăm", t)
    t = re.sub(r"(?<![\d.,])(\d{1,6})(?![\d])", lambda m: _num_vi(int(m.group(1))), t)
    return re.sub(r"[ \t]{2,}", " ", t)


def syllables(text: str) -> int:
    return len(re.findall(r"[^\s\d.,!?;:\"“”()…–\-]+", speakable(text or "")))


def estimate_usd(text: str, key: str, seconds: float = 8) -> float:
    if VOICES[key][0] == "chirp":
        return round(len(text) * 30e-6, 5)
    return round(len(text) / 3 * 0.5e-6 + seconds * 25 * 10e-6, 5)


def build_request(text: str, key: str, rate: float = 1.0) -> dict:
    kind, name = VOICES[key][0], VOICES[key][1]
    audio = {"audioEncoding": "LINEAR16", "sampleRateHertz": RATE}
    if kind == "gemini":
        return {"input": {"prompt": style(), "text": speakable(text)},
                "voice": {"languageCode": "vi-VN", "name": name, "modelName": GEMINI_TTS_MODEL}, "audioConfig": audio}
    return {"input": {"text": speakable(text)}, "voice": {"languageCode": "vi-VN", "name": name},
            "audioConfig": {**audio, "speakingRate": rate}}


def _token() -> str:
    from .notebooklm import _credentials

    return _credentials(["https://www.googleapis.com/auth/cloud-platform"]).token


def wav_seconds(data: bytes) -> float:
    try:
        with wave.open(io.BytesIO(data)) as w:
            return w.getnframes() / float(w.getframerate())
    except (wave.Error, EOFError):
        return len(data) / (RATE * 2.0)


def _as_wav(data: bytes) -> bytes:
    if data[:4] == b"RIFF":
        return data
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data)
    return buf.getvalue()


def synthesize(text: str, key: str, rate: float = 1.0) -> bytes:
    if key not in VOICES:
        raise TTSError(f"Giọng không có: {key}")
    if not text.strip():
        raise TTSError("Lời thoại trống")
    h = {"Authorization": f"Bearer {_token()}", "Content-Type": "application/json",
         "x-goog-user-project": settings.gemini_vertex_project}
    import time

    body = build_request(text, key, rate)
    for wait in RETRY_WAITS + (None,):
        r = httpx.post(URL, headers=h, json=body, timeout=90)
        # 429 = vượt hạn mức/phút của Gemini TTS; 499/500/503 = Google huỷ hoặc quá tải → chờ rồi thử lại
        if r.status_code not in (429, 499, 500, 503) or wait is None:
            break
        time.sleep(wait)
    if r.status_code != 200:
        msg = r.text[:300]
        if r.status_code == 403 and "texttospeech" in msg.lower():
            msg = "Chưa bật Cloud Text-to-Speech API cho project, hoặc service account chưa có quyền. " + msg
        raise TTSError(f"TTS lỗi {r.status_code}: {msg}")
    b64 = r.json().get("audioContent")
    if not b64:
        raise TTSError("TTS không trả âm thanh")
    data = _as_wav(base64.b64decode(b64))
    from . import strategy

    strategy.record_usage("tts", None, {"endpoint": "cloud_tts", "input_tokens": len(text), "output_tokens": 0,
                                        "thinking_tokens": 0, "total_tokens": len(text),
                                        "cost_usd": estimate_usd(text, key, wav_seconds(data))})
    return data


def tts_dir() -> str:
    from .media import cache_dir

    d = os.path.join(cache_dir(), "tts")
    os.makedirs(d, exist_ok=True)
    return d


def analyze(path: str) -> dict:
    """Đo bằng ffmpeg: độ to (LUFS), khoảng lặng đầu/cuối, thời lượng nói, cao độ trung vị (Hz).
    Không có ffmpeg/numpy thì trả về phần đo được."""
    out: dict = {}
    if not path or not os.path.exists(path) or not shutil.which("ffmpeg"):
        return out
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af",
                            "silencedetect=n=-35dB:d=0.2,loudnorm=print_format=summary", "-f", "null", "-"],
                           capture_output=True, text=True, timeout=60)
        log = r.stderr
        m = re.search(r"Input Integrated:\s*(-?[\d.]+)", log)
        if m:
            out["lufs"] = float(m.group(1))
        m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", log)
        dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0
        starts = [float(x) for x in re.findall(r"silence_start:\s*(-?[\d.]+)", log)]
        ends = [float(x) for x in re.findall(r"silence_end:\s*([\d.]+)", log)]
        lead = ends[0] if starts and starts[0] <= 0.01 and ends else 0.0
        tail = dur - starts[-1] if starts and (len(starts) > len(ends) or (ends and ends[-1] >= dur - 0.15)) else 0.0
        out.update(lead=round(lead, 2), tail=round(max(tail, 0), 2), speech=round(max(dur - lead - max(tail, 0), 0), 2))
    except (OSError, subprocess.SubprocessError, ValueError):
        return out
    try:
        import numpy as np

        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                             capture_output=True, timeout=60).stdout
        x = np.frombuffer(raw, dtype=np.int16).astype(float)
        sr, f0 = 16000, []
        for i in range(0, len(x) - 640, 320):
            fr = x[i:i + 640]
            if np.sqrt((fr ** 2).mean()) < 500:
                continue
            fr = fr - fr.mean()
            ac = np.correlate(fr, fr, "full")[639:]
            lo, hi = sr // 400, sr // 80
            k = lo + int(np.argmax(ac[lo:hi]))
            if ac[k] > 0.4 * ac[0]:
                f0.append(sr / k)
        if len(f0) > 20:
            out["f0"] = int(np.median(f0))
    except Exception:  # noqa: BLE001  (numpy không có / file lạ)
        pass
    return out


def reference_path() -> str:
    for ext in ("mp3", "wav", "m4a"):
        p = os.path.join(tts_dir(), f"mau_chuan.{ext}")
        if os.path.exists(p):
            return p
    return REF_DEFAULT if os.path.exists(REF_DEFAULT) else ""


def reference_info() -> dict:
    p = reference_path()
    if not p:
        return {}
    cache = os.path.join(tts_dir(), "mau_chuan.json")
    key = f"{p}:{os.path.getmtime(p)}"
    try:
        with open(cache, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("_key") == key:
            return d
    except (OSError, ValueError):
        pass
    d = {"_key": key, "name": os.path.basename(p), **analyze(p)}
    try:
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(d, f)
    except OSError:
        pass
    return d


def save_reference(data: bytes, filename: str) -> str:
    ext = (filename.rsplit(".", 1)[-1] or "").lower()
    if ext not in ("mp3", "wav", "m4a") or len(data) > 10 * 1024 * 1024 or len(data) < 1000:
        raise TTSError("Chỉ nhận file .mp3/.wav/.m4a, dưới 10 MB")
    for e in ("mp3", "wav", "m4a"):
        old = os.path.join(tts_dir(), f"mau_chuan.{e}")
        if os.path.exists(old):
            os.remove(old)
    p = os.path.join(tts_dir(), f"mau_chuan.{ext}")
    with open(p, "wb") as f:
        f.write(data)
    return p


def _meta(text: str, data: bytes, path: str = "") -> dict:
    sec = round(wav_seconds(data), 2)
    n = syllables(text)
    a = analyze(path) if path else {}
    speak = a.get("speech") or sec  # tốc độ tính trên phần có tiếng nói (bỏ lặng đầu/cuối)
    sps = round(n / speak, 2) if speak else 0
    return {"seconds": sec, "syllables": n, "sps": sps, "speed_ok": SYL_MIN <= sps <= SYL_MAX,
            "fits_8s": sec <= 8.0, **{k: a[k] for k in ("lufs", "lead", "f0") if k in a},
            "lead_ok": a.get("lead", 0) <= 0.3}


# ---------- Mẫu nghe thử ----------
def samples_path() -> str:
    return os.path.join(tts_dir(), "samples.json")


def load_samples() -> dict:
    try:
        with open(samples_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def make_samples(text: str, keys: list[str] | None = None, workers: int = 2) -> dict:
    """Tạo mẫu song song (4 luồng); giữ mẫu cũ của giọng không tạo lại nếu câu đọc không đổi."""
    from concurrent.futures import ThreadPoolExecutor

    keys = [k for k in (keys or list(VOICES)) if k in VOICES]
    old = load_samples()
    out = old if old.get("_text") == text else {}
    out["_text"] = text
    errors = []

    def one(k):
        data = synthesize(text, k)
        path = os.path.join(tts_dir(), f"mau_{k}.wav")
        with open(path, "wb") as f:
            f.write(data)
        return {**_meta(text, data, path), "created": db.now_iso()}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {k: ex.submit(one, k) for k in keys}
        for k, fu in futs.items():
            try:
                out[k] = fu.result()
            except Exception as e:  # noqa: BLE001
                errors.append(f"{VOICES[k][2]}: {str(e)[:200]}")
                out.pop(k, None)
            _job_update(done=len([x for x in futs if futs[x].done()]))
    with open(samples_path(), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    return {"samples": out, "errors": errors}


# ---------- chạy nền (15 giọng mất 1–2 phút, tránh quá thời gian chờ của trình duyệt) ----------
def _job_path() -> str:
    return os.path.join(tts_dir(), "samples_job.json")


def job() -> dict:
    try:
        with open(_job_path(), encoding="utf-8") as f:
            j = json.load(f)
    except (OSError, ValueError):
        return {}
    if j.get("running"):
        from datetime import datetime, timezone

        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(j["started"])).total_seconds()
        except (KeyError, ValueError):
            age = 0
        if age > 600:  # tiến trình chết giữa chừng
            j["running"] = False
    return j


def _write_job(j: dict) -> None:
    """Ghi nguyên tử (file tạm rồi đổi tên) để trang đang tải lại không đọc phải file ghi dở."""
    tmp = _job_path() + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(j, f, ensure_ascii=False)
        os.replace(tmp, _job_path())
    except OSError:
        pass


def _job_update(**kw) -> None:
    j = job()
    j.update(kw)
    _write_job(j)


def start_samples(text: str, keys: list[str] | None = None) -> bool:
    """Chạy nền; False nếu đang có lượt khác chạy."""
    import threading

    if job().get("running"):
        return False
    keys = [k for k in (keys or list(VOICES)) if k in VOICES]
    _write_job({"running": True, "total": len(keys), "done": 0, "started": db.now_iso(), "errors": []})

    def run():
        try:
            r = make_samples(text, keys)
            _job_update(running=False, done=len(keys), errors=r["errors"], finished=db.now_iso())
        except Exception as e:  # noqa: BLE001
            _job_update(running=False, errors=[str(e)[:300]], finished=db.now_iso())

    threading.Thread(target=run, daemon=True).start()
    return True


def missing(text: str) -> list[str]:
    """Giọng chưa có mẫu cho câu đọc hiện tại (lượt trước lỗi)."""
    smp = load_samples()
    if smp.get("_text") != text:
        return list(VOICES)
    return [k for k in VOICES if k not in smp]


def rank(samples: dict, ref: dict) -> list[str]:
    """Xếp giọng theo độ gần giọng mẫu chuẩn: lệch cao độ (Hz) + phạt tốc độ ngoài 3,8–4,0 + phạt lặng đầu."""
    keys = [k for k in VOICES if k in samples]
    rf = ref.get("f0")

    def score(k):
        s = samples[k]
        sc = abs(s["f0"] - rf) if rf and s.get("f0") else 60.0
        sps = s.get("sps") or 0
        sc += 0 if SYL_MIN <= sps <= SYL_MAX else 40 * min(abs(sps - SYL_MIN), abs(sps - SYL_MAX))
        sc += max(0.0, (s.get("lead") or 0) - 0.3) * 30
        return sc

    for k in keys:
        samples[k]["score"] = round(score(k), 1)
    return sorted(keys, key=lambda k: samples[k]["score"])


def sample_file(key: str) -> str:
    return os.path.join(tts_dir(), f"mau_{key}.wav") if key in VOICES else ""


# ---------- Giọng 4 cảnh của gói ----------
def scene_name(goi, k: int) -> str:
    return f"Goi_{re.sub(r'[^0-9A-Za-z]', '', str(goi))}_canh_{k}_giong.wav"


def scene_file(goi, k: int) -> str:
    return os.path.join(tts_dir(), scene_name(goi, k))


def scene_info(p: dict) -> dict:
    out = {}
    for k in range(1, 5):
        path = scene_file(p.get("goi"), k)
        if os.path.exists(path):
            with open(path, "rb") as f:
                data = f.read()
            out[str(k)] = {"name": scene_name(p.get("goi"), k), **_meta(p.get(f"scene{k}") or "", data, path)}
    return out


def make_scenes(p: dict, key: str | None = None) -> dict:
    key = key or voice_key()
    if not key:
        raise TTSError("Chưa chọn giọng thương hiệu — vào trang Giọng Cô Kim để chọn")
    errors, done = [], []
    for k in range(1, 5):
        text = (p.get(f"scene{k}") or "").strip()
        if not text:
            errors.append(f"cảnh {k}: chưa có lời thoại")
            continue
        try:
            data = synthesize(text, key)
        except Exception as e:  # noqa: BLE001
            errors.append(f"cảnh {k}: {str(e)[:160]}")
            continue
        with open(scene_file(p.get("goi"), k), "wb") as f:
            f.write(data)
        done.append(str(k))
    return {"done": done, "errors": errors, "voice": VOICES[key][2]}


def scenes_zip(p: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for k in range(1, 5):
            path = scene_file(p.get("goi"), k)
            if os.path.exists(path):
                z.write(path, scene_name(p.get("goi"), k))
    return buf.getvalue()


def estimate_scenes(p: dict, key: str | None = None) -> float:
    key = key or voice_key()
    if not key:
        return 0.0
    return round(sum(estimate_usd(p.get(f"scene{k}") or "", key) for k in range(1, 5)), 4)
