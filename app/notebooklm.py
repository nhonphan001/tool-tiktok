"""Đồng bộ báo cáo & chiến lược sang NotebookLM.

Các chế độ (NOTEBOOKLM_MODE, có thể kết hợp bằng dấu phẩy):
- local      : ghi file Markdown vào EXPORT_DIR (tải lên NotebookLM thủ công / thư mục đồng bộ Drive).
- drive      : ghi đè nội dung 2 Google Docs (báo cáo, chiến lược). Thêm 2 Docs này làm nguồn trong
               NotebookLM một lần; mỗi lần cập nhật chỉ cần bấm "Đồng bộ với Google Drive" trên nguồn.
- enterprise : đẩy trực tiếp nguồn văn bản vào notebook qua NotebookLM Enterprise API (Google Cloud).
"""
import logging
import os
from datetime import datetime

import httpx
import markdown as md

from . import db, report
from .config import settings

log = logging.getLogger(__name__)
DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files/{id}?uploadType=media&supportsAllDrives=true"


def _credentials(scopes: list[str]):
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    path = settings.google_service_account_file
    if not path or not os.path.exists(path):
        raise RuntimeError(f"Không tìm thấy file service account: {path}")
    creds = service_account.Credentials.from_service_account_file(path, scopes=scopes)
    creds.refresh(Request())
    return creds


def service_account_email() -> str | None:
    import json

    try:
        with open(settings.google_service_account_file) as f:
            return json.load(f).get("client_email")
    except (OSError, ValueError):
        return None


def _to_html(text_md: str) -> str:
    body = md.markdown(text_md, extensions=["tables"])
    return f"<html><head><meta charset='utf-8'></head><body>{body}</body></html>"


def push_local(name: str, content: str) -> str:
    os.makedirs(settings.export_dir, exist_ok=True)
    latest = os.path.join(settings.export_dir, f"{name}_latest.md")
    dated = os.path.join(settings.export_dir, f"{name}_{datetime.now().strftime('%Y%m%d_%H%M')}.md")
    for p in (latest, dated):
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
    return latest


def push_drive(doc_id: str, content: str) -> None:
    creds = _credentials(["https://www.googleapis.com/auth/drive"])
    r = httpx.patch(
        DRIVE_UPLOAD.format(id=doc_id),
        content=_to_html(content).encode("utf-8"),
        headers={"Authorization": f"Bearer {creds.token}", "Content-Type": "text/html; charset=UTF-8"},
        timeout=60,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"Drive API lỗi {r.status_code}: {r.text[:300]}")


def push_enterprise(source_name: str, content: str) -> None:
    if not (settings.notebooklm_project_number and settings.notebooklm_notebook_id):
        raise RuntimeError("Thiếu NOTEBOOKLM_PROJECT_NUMBER hoặc NOTEBOOKLM_NOTEBOOK_ID")
    loc = settings.notebooklm_location or "global"
    creds = _credentials(["https://www.googleapis.com/auth/cloud-platform"])
    url = (
        f"https://{loc}-discoveryengine.googleapis.com/v1alpha/projects/{settings.notebooklm_project_number}"
        f"/locations/{loc}/notebooks/{settings.notebooklm_notebook_id}/sources:batchCreate"
    )
    r = httpx.post(
        url,
        json={"userContents": [{"textContent": {"sourceName": source_name, "content": content}}]},
        headers={"Authorization": f"Bearer {creds.token}"},
        timeout=60,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"NotebookLM API lỗi {r.status_code}: {r.text[:300]}")


def sync_all(open_id: str) -> list[dict]:
    modes = settings.notebooklm_modes
    if not modes:
        return []
    docs = {
        "report": report.build_report(open_id),
        "strategy": report.build_strategy_doc(open_id),
    }
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    results = []
    for mode in modes:
        for kind, content in docs.items():
            target = f"{mode}:{kind}"
            try:
                if mode == "local":
                    path = push_local(f"tiktok_{kind}", content)
                    msg = f"Đã ghi {path}"
                elif mode == "drive":
                    doc_id = settings.google_doc_id_report if kind == "report" else settings.google_doc_id_strategy
                    if not doc_id:
                        raise RuntimeError(f"Chưa cấu hình Google Doc ID cho '{kind}'")
                    push_drive(doc_id, content)
                    msg = f"Đã cập nhật Google Doc {doc_id}"
                elif mode == "enterprise":
                    if kind == "strategy" and "Chưa có chiến lược" in content:
                        continue
                    push_enterprise(f"TikTok {kind} {stamp}", content)
                    msg = "Đã thêm nguồn vào notebook"
                else:
                    raise RuntimeError(f"Chế độ không hỗ trợ: {mode}")
                db.log_sync(target, "ok", msg)
                results.append({"target": target, "status": "ok", "message": msg})
            except Exception as e:  # noqa: BLE001
                log.warning("Sync %s failed: %s", target, e)
                db.log_sync(target, "error", str(e))
                results.append({"target": target, "status": "error", "message": str(e)})
    return results
