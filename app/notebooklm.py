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


def check_drive() -> list[dict]:
    """Kiểm tra kết nối Google Drive cho chế độ drive: file khóa, quyền sửa từng Doc. Không ghi gì."""
    out = []
    path = settings.google_service_account_file
    email = service_account_email()
    if not email:
        return [{"ok": False, "msg": f"Không đọc được file service account tại {path} (đặt file JSON vào thư mục secrets/ trên VPS)."}]
    out.append({"ok": True, "msg": f"Service account: {email}"})
    try:
        creds = _credentials(["https://www.googleapis.com/auth/drive"])
    except Exception as e:  # noqa: BLE001
        return out + [{"ok": False, "msg": f"Không lấy được quyền truy cập Google: {e}"}]
    for label, doc_id in (("Báo cáo", settings.google_doc_id_report), ("Chiến lược", settings.google_doc_id_strategy)):
        if not doc_id:
            out.append({"ok": False, "msg": f"Chưa điền Google Doc ID — {label}."})
            continue
        r = httpx.get(f"https://www.googleapis.com/drive/v3/files/{doc_id}",
                      params={"fields": "name,mimeType,capabilities(canEdit)", "supportsAllDrives": "true"},
                      headers={"Authorization": f"Bearer {creds.token}"}, timeout=30)
        if r.status_code == 404:
            out.append({"ok": False, "msg": f"{label}: không thấy Doc {doc_id} — chưa chia sẻ cho {email} hoặc sai ID."})
        elif r.status_code == 403 and "accessNotConfigured" in r.text:
            out.append({"ok": False, "msg": "Google Drive API chưa bật trong project Google Cloud của service account."})
        elif r.status_code != 200:
            out.append({"ok": False, "msg": f"{label}: lỗi {r.status_code} {r.text[:200]}"})
        else:
            j = r.json()
            can = (j.get("capabilities") or {}).get("canEdit")
            out.append({"ok": bool(can), "msg": f"{label}: “{j.get('name')}” — " + (
                "có quyền sửa." if can else f"CHỈ XEM được, cần chia sẻ quyền Người chỉnh sửa cho {email}.")})
    return out


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
