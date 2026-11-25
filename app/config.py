"""Cấu hình ứng dụng: đọc từ biến môi trường (.env), một số giá trị có thể ghi đè từ web app."""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _bool(v: str | None, default: bool = False) -> bool:
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


_DEFAULTS_DIR = os.path.join(os.path.dirname(__file__), "defaults")


def _default_text(name: str, env: str) -> str:
    """Giá trị từ biến môi trường, nếu trống thì đọc file mặc định trong app/defaults/."""
    v = os.getenv(env)
    if v:
        return v
    try:
        with open(os.path.join(_DEFAULTS_DIR, name), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


@dataclass
class Settings:
    app_password: str = field(default_factory=lambda: os.getenv("APP_PASSWORD", "admin"))
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", "dev-secret-change-me"))
    base_url: str = field(default_factory=lambda: os.getenv("BASE_URL", "http://localhost:8000").rstrip("/"))
    database_path: str = field(default_factory=lambda: os.getenv("DATABASE_PATH", "data/tiktok.db"))
    timezone: str = field(default_factory=lambda: os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh"))

    tiktok_client_key: str = field(default_factory=lambda: os.getenv("TIKTOK_CLIENT_KEY", ""))
    tiktok_client_secret: str = field(default_factory=lambda: os.getenv("TIKTOK_CLIENT_SECRET", ""))

    scan_interval_hours: float = field(default_factory=lambda: float(os.getenv("SCAN_INTERVAL_HOURS", "6")))
    # Giờ quét cố định theo TIMEZONE (để trống = quét theo chu kỳ scan_interval_hours)
    scan_times: str = field(default_factory=lambda: os.getenv("SCAN_TIMES", "05:00,11:00,17:00,23:00"))
    max_videos_per_scan: int = field(default_factory=lambda: int(os.getenv("MAX_VIDEOS_PER_SCAN", "200")))

    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.8-flash"))
    gemini_backend: str = field(default_factory=lambda: os.getenv("GEMINI_BACKEND", "aistudio"))
    # Vertex: "" = endpoint theo vùng (mặc định), "global" = endpoint global (cần mã project)
    gemini_vertex_location: str = field(default_factory=lambda: os.getenv("GEMINI_VERTEX_LOCATION", ""))
    gemini_vertex_project: str = field(default_factory=lambda: os.getenv("GEMINI_VERTEX_PROJECT", ""))
    # 0 = tự động theo bảng giá trong app/pricing.py; > 0 = giá nhập tay (USD / 1 triệu token)
    gemini_price_input: float = field(default_factory=lambda: float(os.getenv("GEMINI_PRICE_INPUT") or 0))
    gemini_price_output: float = field(default_factory=lambda: float(os.getenv("GEMINI_PRICE_OUTPUT") or 0))
    usd_vnd_rate: float = field(default_factory=lambda: float(os.getenv("USD_VND_RATE", "26000")))
    channel_context: str = field(default_factory=lambda: _default_text("channel_context.md", "CHANNEL_CONTEXT"))
    content_rules: str = field(default_factory=lambda: _default_text("content_rules.md", "CONTENT_RULES"))

    # KPI
    kpi_target_1: int = field(default_factory=lambda: int(os.getenv("KPI_TARGET_1", "5000")))
    kpi_deadline_1: str = field(default_factory=lambda: os.getenv("KPI_DEADLINE_1", "2026-12-17"))
    kpi_target_2: int = field(default_factory=lambda: int(os.getenv("KPI_TARGET_2", "10000")))
    kpi_deadline_2: str = field(default_factory=lambda: os.getenv("KPI_DEADLINE_2", "2027-02-17"))
    kpi_like_view_min: float = field(default_factory=lambda: float(os.getenv("KPI_LIKE_VIEW_MIN", "4")))
    posting_slots: str = field(default_factory=lambda: os.getenv("POSTING_SLOTS", "11:00,12:00,19:00"))  # chốt 20/11: 11:00 L3 · 12:00 L2 · 19:00 L1

    # Bảng quản trị sản phẩm (Google Sheets, chỉ đọc bằng service account)
    product_sheet_id: str = field(default_factory=lambda: os.getenv("PRODUCT_SHEET_ID", ""))
    product_sheet_range: str = field(
        default_factory=lambda: os.getenv("PRODUCT_SHEET_RANGE", "San_Pham_Affiliate_5_Hanh!A10:O")
    )

    # Hoặc link CSV đã "Xuất bản lên web" (vd. tab WEB_XUAT_BAN) — không cần service account
    product_csv_url: str = field(default_factory=lambda: os.getenv("PRODUCT_CSV_URL", ""))
    # Hộp thư Drive Claude <-> Gemini: GUI_GEMINI, GUI_CLAUDE (đọc phiếu gói SANXUAT-*)
    mailbox_folder_ids: str = field(default_factory=lambda: os.getenv(
        "MAILBOX_FOLDER_IDS", "16C0ZEvMyfdRZ_lcgXdxlN7JhuruaXy9l,1oFj8HZVoIY0CYQkkkyza9d2GCToaQUVC"))
    # Doc "hộp thư đi" (HOP_THU_TOOL__YEUCAU trong GUI_GEMINI) — dùng khi service account không tạo được file mới
    # Thư mục 02_VIDEO_THO_CHO_KIEM_DUYET (clip thô anh Nhơn tạo, P8a) — tool đọc để duyệt trên web
    raw_video_folder_id: str = field(default_factory=lambda: os.getenv("RAW_VIDEO_FOLDER_ID", "1zG9VyoYDtHgYnJs-SH8kqy_bQPdpRTyM"))
    # 04_VIDEO_DA_DUYET_SAN_SANG_DANG: Gemini tải video thành phẩm vào đây → tool tự gắn vào gói (app/finals.py)
    final_video_folder_id: str = field(default_factory=lambda: os.getenv("FINAL_VIDEO_FOLDER_ID", "1JOpC__Wf1E2y-7wxodvZDCU12_gj69AH"))
    mailbox_outbox_doc_id: str = field(default_factory=lambda: os.getenv("MAILBOX_OUTBOX_DOC_ID", "1x6QmTfs7cl2cU-wRUQDZnXLu33dKYeeMNPNjVr04Plg"))

    # Token cho API chỉ-đọc /api/public/* (bảng điều hành khác, Gemini...). Trống = tắt.
    api_token: str = field(default_factory=lambda: os.getenv("API_TOKEN", ""))
    auto_strategy: bool = field(default_factory=lambda: _bool(os.getenv("AUTO_STRATEGY"), False))
    # Veo (Vertex AI) tạo clip thô — mặc định TẮT; mỗi lần chạy phải xác nhận chi phí
    veo_enabled: bool = field(default_factory=lambda: _bool(os.getenv("VEO_ENABLED"), False))
    veo_model: str = field(default_factory=lambda: os.getenv("VEO_MODEL", "fast"))
    veo_resolution: str = field(default_factory=lambda: os.getenv("VEO_RESOLUTION", "720p"))
    veo_budget_usd: float = field(default_factory=lambda: float(os.getenv("VEO_BUDGET_USD", "20")))
    # Giọng thương hiệu Cô Kim (khoá trong app/tts.VOICES), chọn ở trang /giong
    tts_voice: str = field(default_factory=lambda: os.getenv("TTS_VOICE", ""))
    # Thư Claude/Gemini có khối cap_nhat_tool: tự áp dụng khoá an toàn (giờ đăng, KPI). Mặc định TẮT = chờ duyệt.
    auto_apply_updates: bool = field(default_factory=lambda: _bool(os.getenv("AUTO_APPLY_UPDATES"), False))
    # Độ dài 1 clip thô Gemini/Flow tạo ra (giây). App Gemini đang ra 10 giây/clip → mỗi cảnh tối đa ~34 âm tiết.
    clip_seconds: int = field(default_factory=lambda: int(os.getenv("CLIP_SECONDS", "10")))
    # Doc nhận bản tóm tắt tự động sau mỗi lần quét + chiến lược (1 Doc trong GUI_GEMINI, 1 Doc trong GUI_CLAUDE)
    summary_doc_gemini: str = field(default_factory=lambda: os.getenv("SUMMARY_DOC_GEMINI", "13OTXOO8HYr_RqZYJnZj5uu40LWOZhXiQJzhGp_HxhM8"))
    summary_doc_claude: str = field(default_factory=lambda: os.getenv("SUMMARY_DOC_CLAUDE", "1U4g6gMgcNy5oaL6jtOmCp9FEF1QFWKLxG50cK6zCMVE"))
    # Hồ sơ giọng Cô Kim (lời dặn cho Gemini TTS) — trống = app/defaults/co_kim_voice.md
    tts_style: str = field(default_factory=lambda: _default_text("co_kim_voice.md", "TTS_STYLE"))
    # Doc nhận báo cáo đồng thuận (API + Claude in Chrome) trong GUI_GEMINI — tool ghi đè sau mỗi báo cáo Chrome
    consensus_doc_gemini: str = field(default_factory=lambda: os.getenv("CONSENSUS_DOC_GEMINI", "110M2BH7w_jzTwXMg_Dg_cC8VqHF7fE4yuY3g1f7npgU"))
    # Bộ quy tắc kịch bản (tổng hợp mọi chỉnh sửa) — tool tự kèm vào mọi thư cho Gemini và lời nhắc Gemini API
    script_rules: str = field(default_factory=lambda: _default_text("script_rules.md", "SCRIPT_RULES"))
    # Số gói đã giữ ngoài tool (Claude gửi phiếu trực tiếp) → gói mới của tool bắt đầu từ số này + 1
    goi_reserved_until: int = field(default_factory=lambda: int(os.getenv("GOI_RESERVED_UNTIL", "34")))
    # Tuần thử nghiệm KHÔNG quảng bá (anh Nhơn chốt 24/11): tool không gợi ý bật Quảng bá, Gemini không viết kế hoạch quảng cáo
    ads_paused: bool = field(default_factory=lambda: _bool(os.getenv("ADS_PAUSED"), True))
    # Bối cảnh quảng bá đã chạy (để AI không nhầm view trả phí là view tự nhiên) — trống = app/defaults/ads_context.md
    ads_context: str = field(default_factory=lambda: _default_text("ads_context.md", "ADS_CONTEXT"))

    notebooklm_mode: str = field(default_factory=lambda: os.getenv("NOTEBOOKLM_MODE", "local"))
    export_dir: str = field(default_factory=lambda: os.getenv("EXPORT_DIR", "exports"))
    google_service_account_file: str = field(
        default_factory=lambda: os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "secrets/service-account.json")
    )
    google_doc_id_report: str = field(default_factory=lambda: os.getenv("GOOGLE_DOC_ID_REPORT", ""))
    google_doc_id_strategy: str = field(default_factory=lambda: os.getenv("GOOGLE_DOC_ID_STRATEGY", ""))
    notebooklm_project_number: str = field(default_factory=lambda: os.getenv("NOTEBOOKLM_PROJECT_NUMBER", ""))
    notebooklm_location: str = field(default_factory=lambda: os.getenv("NOTEBOOKLM_LOCATION", "global"))
    notebooklm_notebook_id: str = field(default_factory=lambda: os.getenv("NOTEBOOKLM_NOTEBOOK_ID", ""))

    @property
    def tiktok_redirect_uri(self) -> str:
        return f"{self.base_url}/auth/tiktok/callback"

    @property
    def notebooklm_modes(self) -> list[str]:
        return [m.strip() for m in self.notebooklm_mode.split(",") if m.strip() and m.strip() != "off"]


# Các khóa có thể chỉnh trên web app (lưu trong DB, ghi đè .env)
EDITABLE_KEYS = {
    "scan_interval_hours": float,
    "scan_times": str,
    "max_videos_per_scan": int,
    "gemini_model": str,
    "channel_context": str,
    "gemini_backend": str,
    "gemini_vertex_location": str,
    "gemini_vertex_project": str,
    "content_rules": str,
    "kpi_target_1": int,
    "kpi_deadline_1": str,
    "kpi_target_2": int,
    "kpi_deadline_2": str,
    "kpi_like_view_min": float,
    "posting_slots": str,
    "product_sheet_id": str,
    "product_sheet_range": str,
    "product_csv_url": str,
    "mailbox_folder_ids": str,
    "mailbox_outbox_doc_id": str,
    "raw_video_folder_id": str,
    "final_video_folder_id": str,
    "gemini_price_input": float,
    "gemini_price_output": float,
    "usd_vnd_rate": float,
    "auto_strategy": lambda v: _bool(str(v)),
    "veo_enabled": lambda v: _bool(str(v)),
    "veo_model": str,
    "veo_resolution": str,
    "veo_budget_usd": float,
    "tts_voice": str,
    "tts_style": str,
    "summary_doc_gemini": str,
    "clip_seconds": int,
    "auto_apply_updates": lambda v: _bool(str(v)),
    "ads_paused": lambda v: _bool(str(v)),
    "consensus_doc_gemini": str,
    "ads_context": str,
    "script_rules": str,
    "goi_reserved_until": int,
    "summary_doc_claude": str,
    "notebooklm_mode": str,
    "google_doc_id_report": str,
    "google_doc_id_strategy": str,
    "notebooklm_notebook_id": str,
}

# Ô văn bản để trống = dùng nội dung mặc định trong app/defaults/
DEFAULT_TEXT_KEYS = {
    "channel_context": ("channel_context.md", "CHANNEL_CONTEXT"),
    "content_rules": ("content_rules.md", "CONTENT_RULES"),
    "tts_style": ("co_kim_voice.md", "TTS_STYLE"),
    "ads_context": ("ads_context.md", "ADS_CONTEXT"),
    "script_rules": ("script_rules.md", "SCRIPT_RULES"),
}

settings = Settings()


def apply_overrides(overrides: dict[str, str]) -> None:
    for key, raw in overrides.items():
        if key not in EDITABLE_KEYS or raw is None:
            continue
        if raw == "" and key in DEFAULT_TEXT_KEYS:
            setattr(settings, key, _default_text(*DEFAULT_TEXT_KEYS[key]))
            continue
        if raw == "" and EDITABLE_KEYS[key] is not str:
            continue  # ô số để trống: giữ giá trị cũ
        try:
            setattr(settings, key, EDITABLE_KEYS[key](raw))
        except (TypeError, ValueError):
            pass
