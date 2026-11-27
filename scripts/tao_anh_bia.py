"""Tạo Ảnh bìa thương hiệu đồng nhất 1080×1920 cho kênh Tiệm Trà Giải Mã _ Cô Kim (@tiemtragiaima).

Đặc điểm chuẩn thương hiệu (Mục A7 — chốt 27/11/2026):
- Tỷ lệ 9:16 (1080×1920), chữ và thẻ thương hiệu nằm gọn trong vùng an toàn 3:4 của lưới hồ sơ TikTok
  (tránh cắt trên/dưới trên trang cá nhân và tránh bị che bởi icon bên phải hay caption ở đáy).
- Không che khuôn mặt & thao tác rót trà của Cô Kim.
- Chuẩn 100% dấu tiếng Việt sắc nét (render bằng HTML/CSS + Chrome Headless, không bị AI vẽ méo chữ).

Cách chạy:
    python scripts/tao_anh_bia.py --bg <anh_canh_1.jpg> --tag "TUỔI NHÂM NGỌ 2002" ^
        --line1 "Năm Đinh Mùi 2027" --line2 "Có Gì Đổi Khác?" --out GOI_36_ANH_BIA_HOOK.png
"""
from __future__ import annotations

import argparse
import base64
import html
import mimetypes
import os
import pathlib
import subprocess
import tempfile

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
]


def _find_chrome() -> str:
    for p in CHROME_CANDIDATES:
        if os.path.isfile(p):
            return p
    raise FileNotFoundError("Không tìm thấy trình duyệt Chrome/Chromium để xuất ảnh bìa PNG.")


def _data_uri(img_path: pathlib.Path) -> str:
    mime = mimetypes.guess_type(img_path.name)[0] or "image/jpeg"
    b64 = base64.b64encode(img_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def build_html(bg_uri: str, tag: str, line1: str, line2: str,
               loai: int = 1, brand: str = "TIỆM TRÀ GIẢI MÃ · CÔ KIM") -> str:
    # Loại 1 (Bát Tự): Vàng ánh kim sang trọng · Loại 3 (Trà sáng): Vàng kem ấm áp dịu nhẹ
    accent_grad = (
        "linear-gradient(135deg, #FFE8A3 0%, #F4BE4F 48%, #D99326 100%)"
        if loai == 1
        else "linear-gradient(135deg, #FFF3CC 0%, #F7CF79 55%, #DF9F3B 100%)"
    )
    tag_bg = (
        "linear-gradient(135deg, #FFE49E 0%, #F3B943 100%)"
        if loai == 1
        else "linear-gradient(135deg, #D9F7E6 0%, #86DFB2 100%)"
    )
    tag_fg = "#240D3A" if loai == 1 else "#0E3B28"
    return f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<style>
  @page {{ size: 1080px 1920px; margin: 0; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    width: 1080px; height: 1920px; overflow: hidden;
    font-family: "Segoe UI", "Roboto", system-ui, -apple-system, sans-serif;
    background: #140821;
  }}
  .canvas {{
    position: relative; width: 1080px; height: 1920px; overflow: hidden;
  }}
  .bg {{
    position: absolute; inset: 0; width: 100%; height: 100%;
    object-fit: cover; object-position: center 22%;
    filter: contrast(1.04) saturate(1.06);
  }}
  /* Viền khung ánh kim tinh tế đậm chất Tiệm Trà Giải Mã */
  .frame {{
    position: absolute; inset: 28px; border-radius: 30px;
    border: 2px solid rgba(245, 201, 106, 0.42);
    box-shadow: inset 0 0 0 1px rgba(255, 244, 210, 0.16);
    pointer-events: none;
  }}
  /* Dải tối nhẹ ở vùng trên và vùng hook (giữ mặt Cô Kim ở 24%–58% sáng rực) */
  .vignette-top {{
    position: absolute; top: 0; left: 0; right: 0; height: 420px;
    background: linear-gradient(180deg, rgba(22, 8, 36, 0.62) 0%, rgba(22, 8, 36, 0.18) 58%, transparent 100%);
  }}
  .vignette-bottom {{
    position: absolute; bottom: 0; left: 0; right: 0; height: 860px;
    background: linear-gradient(0deg, rgba(18, 6, 30, 0.88) 0%, rgba(30, 11, 48, 0.62) 48%, transparent 100%);
  }}

  /* Thẻ thương hiệu đồng nhất trên đầu — nằm phía trên búi tóc Cô Kim, gọn trong vùng an toàn */
  .brand-wrap {{
    position: absolute; top: 150px; left: 0; right: 0;
    display: flex; justify-content: center;
  }}
  .brand-pill {{
    display: inline-flex; align-items: center; gap: 14px;
    padding: 13px 34px; border-radius: 999px;
    background: rgba(34, 13, 56, 0.84);
    border: 2px solid rgba(245, 201, 106, 0.82);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.42), 0 0 22px rgba(245, 201, 106, 0.22);
    color: #FFE7AC; font-size: 26px; font-weight: 700; letter-spacing: 3px;
    text-transform: uppercase;
  }}
  .brand-star {{ color: #FFD166; font-size: 24px; }}

  /* Khối Hook thương hiệu nổi bật (vùng 63%–81%, khoe trọn ấm trà & vẫn an toàn lưới Profile 3:4) */
  .hook-wrap {{
    position: absolute; left: 56px; right: 56px; bottom: 300px;
    display: flex; flex-direction: column; align-items: center; text-align: center;
  }}
  .hook-card {{
    width: 100%;
    padding: 34px 38px 36px;
    border-radius: 34px;
    background: linear-gradient(180deg, rgba(36, 14, 58, 0.78) 0%, rgba(22, 8, 38, 0.88) 100%);
    border: 2.5px solid rgba(245, 201, 106, 0.78);
    box-shadow:
      0 24px 60px rgba(0, 0, 0, 0.58),
      0 0 36px rgba(245, 201, 106, 0.18),
      inset 0 1px 0 rgba(255, 248, 224, 0.3);
  }}
  .tag-badge {{
    display: inline-block;
    padding: 12px 34px;
    margin-bottom: 22px;
    border-radius: 999px;
    background: {tag_bg};
    color: {tag_fg};
    font-size: 34px; font-weight: 900; letter-spacing: 1.8px;
    text-transform: uppercase;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.36), 0 0 20px rgba(255, 214, 107, 0.38);
  }}
  .line1 {{
    font-family: Georgia, "Times New Roman", serif;
    font-size: 74px; font-weight: 700; line-height: 1.14;
    color: #FFFDF7;
    text-shadow: 0 6px 22px rgba(0, 0, 0, 0.72), 0 2px 4px rgba(0, 0, 0, 0.9);
    margin-bottom: 10px;
  }}
  .line2 {{
    font-size: 82px; font-weight: 900; line-height: 1.12;
    letter-spacing: -0.5px;
    background: {accent_grad};
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    filter: drop-shadow(0 6px 14px rgba(0, 0, 0, 0.82)) drop-shadow(0 0 18px rgba(245, 201, 106, 0.34));
  }}
  .divider {{
    width: 180px; height: 3px; margin: 22px auto 0;
    border-radius: 999px;
    background: linear-gradient(90deg, transparent, #F5C96A, transparent);
  }}
</style>
</head>
<body>
  <div class="canvas">
    <img class="bg" src="{bg_uri}" alt="bg">
    <div class="vignette-top"></div>
    <div class="vignette-bottom"></div>
    <div class="frame"></div>
    <div class="brand-wrap">
      <div class="brand-pill"><span class="brand-star">✦</span><span>{html.escape(brand)}</span><span class="brand-star">✦</span></div>
    </div>
    <div class="hook-wrap">
      <div class="hook-card">
        <div class="tag-badge">{html.escape(tag)}</div>
        <div class="line1">{html.escape(line1)}</div>
        <div class="line2">{html.escape(line2)}</div>
        <div class="divider"></div>
      </div>
    </div>
  </div>
</body>
</html>
"""


def render_cover(bg_path: pathlib.Path, out_path: pathlib.Path, tag: str, line1: str, line2: str,
                 loai: int = 1) -> pathlib.Path:
    chrome = _find_chrome()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html_doc = build_html(_data_uri(bg_path), tag, line1, line2, loai=loai)
    with tempfile.TemporaryDirectory(prefix="tt_cover_") as tmp:
        tmp_dir = pathlib.Path(tmp)
        html_file = tmp_dir / "cover.html"
        prof_dir = tmp_dir / "prof"
        html_file.write_text(html_doc, encoding="utf-8")
        cmd = [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--user-data-dir={prof_dir}",
            "--window-size=1080,1920",
            "--force-device-scale-factor=1",
            f"--screenshot={out_path}",
            html_file.resolve().as_uri(),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Xuất ảnh bìa thương hiệu 1080×1920 cho kênh Tiệm Trà Giải Mã")
    ap.add_argument("--bg", required=True, help="Đường dẫn ảnh nền (ảnh Cảnh 1)")
    ap.add_argument("--tag", required=True, help="Nhãn nổi bật phía trên (vd: TUỔI NHÂM NGỌ 2002)")
    ap.add_argument("--line1", required=True, help="Dòng 1 của câu Hook (vd: Năm Đinh Mùi 2027)")
    ap.add_argument("--line2", required=True, help="Dòng 2 nhấn mạnh (vd: Có Gì Đổi Khác?)")
    ap.add_argument("--loai", type=int, default=1, choices=(1, 2, 3), help="Loại video (1=Bát Tự, 3=Trà sáng)")
    ap.add_argument("--out", required=True, help="Đường dẫn file ảnh bìa .png đầu ra")
    args = ap.parse_args()
    p = render_cover(pathlib.Path(args.bg), pathlib.Path(args.out), args.tag, args.line1, args.line2, args.loai)
    print(f"OK: {p} ({p.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
