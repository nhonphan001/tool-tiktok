"""Cấu hình ứng dụng: đọc từ biến môi trường (.env), một số giá trị có thể ghi đè từ web app."""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _bool(v: str | None, default: bool = False) -> bool:
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


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
    max_videos_per_scan: int = field(default_factory=lambda: int(os.getenv("MAX_VIDEOS_PER_SCAN", "200")))

    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    channel_context: str = field(default_factory=lambda: os.getenv("CHANNEL_CONTEXT", ""))
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
    "max_videos_per_scan": int,
    "gemini_model": str,
    "channel_context": str,
    "auto_strategy": lambda v: _bool(str(v)),
    "notebooklm_mode": str,
    "google_doc_id_report": str,
    "google_doc_id_strategy": str,
    "notebooklm_notebook_id": str,
}

settings = Settings()


def apply_overrides(overrides: dict[str, str]) -> None:
    for key, raw in overrides.items():
        if key not in EDITABLE_KEYS or raw is None:
            continue
        if raw == "" and EDITABLE_KEYS[key] is not str:
            continue  # ô số để trống: giữ giá trị cũ
        try:
            setattr(settings, key, EDITABLE_KEYS[key](raw))
        except (TypeError, ValueError):
            pass
