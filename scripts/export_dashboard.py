"""Chuyển /api/public/summary của TikTok Manager thành các tệp JSON {rows, meta} cho Bảng điều hành kênh.

Cách dùng: python3 scripts/export_dashboard.py <summary.json> <thư_mục_ra>
(Hoặc lấy thẳng từ API: GET /api/public/dashboard/<tên>.json — không cần script.)
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from app.dashboard_export import build  # noqa: E402


def main(src: str, out: str) -> None:
    d = json.load(open(src, encoding="utf-8"))
    os.makedirs(out, exist_ok=True)
    for name, payload in build(d).items():
        with open(os.path.join(out, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
    print("OK", (d.get("latest") or {}).get("taken_at"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
