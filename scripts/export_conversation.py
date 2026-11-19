"""Xuất cuộc trò chuyện Claude Code (.jsonl) thành Markdown đọc được để sao lưu.

Giữ: tin nhắn người dùng + câu trả lời của Claude (văn bản). Bỏ: nội dung công cụ, suy nghĩ nội bộ, ảnh.
Che: token/khoá (JWT, AIza…, ghp_…, sk-…, khoá riêng), email.
Dùng: python3 scripts/export_conversation.py <file.jsonl> <out.md>
"""
import json
import re
import sys

REDACT = [
    (re.compile(r"eyJ[A-Za-z0-9_-]{20,}(\.[A-Za-z0-9_-]{10,}){0,2}"), "[ĐÃ CHE: token]"),
    (re.compile(r"AIza[0-9A-Za-z_-]{30,}|AQ\.[A-Za-z0-9_-]{30,}|ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}"), "[ĐÃ CHE: khoá]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[ĐÃ CHE: khoá riêng]"),
    (re.compile(r"[\w.+-]+@(?!nangtam-gemini\.iam)[\w-]+\.[\w.]+"), "[email]"),
    (re.compile(r"(_sat=)[A-Za-z0-9._-]+"), r"\1[ĐÃ CHE]"),
]
SKIP_PREFIX = ("<system-reminder>", "<command-", "<local-command", "Caveat:", "<task-notification")


def clean(t: str) -> str:
    for rx, rep in REDACT:
        t = rx.sub(rep, t)
    t = re.sub(r"<system-reminder>.*?</system-reminder>", "", t, flags=re.S)
    return t.strip()


def texts(content) -> list[str]:
    if isinstance(content, str):
        return [content]
    out = []
    for part in content or []:
        if isinstance(part, dict) and part.get("type") == "text":
            out.append(part.get("text") or "")
        elif isinstance(part, dict) and part.get("type") == "image":
            out.append("[ảnh đính kèm]")
    return out


def main(src: str, dst: str) -> None:
    rows = []
    with open(src, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") not in ("user", "assistant") or e.get("isMeta") or e.get("isCompactSummary"):
                continue
            msg = e.get("message") or {}
            role = msg.get("role")
            parts = texts(msg.get("content"))
            if role == "user" and any(isinstance(p, dict) and p.get("type") == "tool_result"
                                      for p in (msg.get("content") or []) if isinstance(msg.get("content"), list)):
                continue
            body = clean("\n\n".join(p for p in parts if p and not p.lstrip().startswith(SKIP_PREFIX)))
            if not body or body == "[ảnh đính kèm]" and role == "assistant":
                continue
            ts = (e.get("timestamp") or "")[:16].replace("T", " ")
            rows.append((role, ts, body))
    # gộp các khối trả lời liên tiếp của Claude trong cùng một lượt
    merged = []
    for role, ts, body in rows:
        if merged and merged[-1][0] == role == "assistant":
            merged[-1] = (role, merged[-1][1], merged[-1][2] + "\n\n" + body)
        else:
            merged.append((role, ts, body))
    out = ["# Sao lưu cuộc trò chuyện – TikTok Manager (Claude Code)", "",
           f"Nguồn: phiên Claude Code của dự án tool-tiktok · {len([m for m in merged if m[0] == 'user'])} lượt hỏi.",
           "Đã bỏ nội dung công cụ/suy nghĩ nội bộ và che token, khoá, email.", ""]
    n = 0
    for role, ts, body in merged:
        if role == "user":
            n += 1
            out += ["---", "", f"## [{n}] Anh Nhơn · {ts} UTC", "", body, ""]
        else:
            out += [f"### Claude", "", body, ""]
    with open(dst, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"{dst}: {n} lượt hỏi, {sum(len(m[2]) for m in merged):,} ký tự")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
