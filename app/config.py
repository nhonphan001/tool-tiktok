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
    posting_slots: str = field(default_factory=lambda: os.getenv("POSTING_SLOTS", "07:00,12:00,19:30"))

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
    mailbox_outbox_doc_id: str = field(default_factory=lambda: os.getenv("MAILBOX_OUTBOX_DOC_ID", "1x6QmTfs7cl2cU-wRUQDZnXLu33dKYeeMNPNjVr04Plg"))

    # Token cho API chỉ-đọc /api/public/* (bảng điều hành khác, Gemini...). Trống = tắt.
    api_token: str = field(default_factory=lambda: os.getenv("API_TOKEN", ""))
    auto_strategy: bool = field(default_factory=lambda: _bool(os.getenv("AUTO_STRATEGY"), False))

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
    "gemini_price_input": float,
    "gemini_price_output": float,
    "usd_vnd_rate": float,
    "auto_strategy": lambda v: _bool(str(v)),
    "notebooklm_mode": str,
    "google_doc_id_report": str,
    "google_doc_id_strategy": str,
    "notebooklm_notebook_id": str,
}

# Ô văn bản để trống = dùng nội dung mặc định trong app/defaults/
DEFAULT_TEXT_KEYS = {
    "channel_context": ("channel_context.md", "CHANNEL_CONTEXT"),
    "content_rules": ("content_rules.md", "CONTENT_RULES"),
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
