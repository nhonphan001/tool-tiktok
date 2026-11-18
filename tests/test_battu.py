"""Lá số đã kiểm chứng trong tài liệu bàn giao (BAN_GIAO_PHIEN_LAM_VIEC mục 6).

Bản Python được so khớp 0 sai lệch với lõi JavaScript gốc của web tra lá số trên 5.240 ca ngẫu nhiên
(1900–2100, có/không giờ, nam/nữ, âm→dương, ca biên Lập Xuân / 23h)."""
from app import battu as B


def tu_tru(dd, mm, yy, h, mi=0, gioi=None):
    return B.lap_la_so(dd, mm, yy, h, mi, gioi)


def test_verified_charts():
    assert tu_tru(14, 10, 1999, 20)["tu_tru"] == "Kỷ Mão – Giáp Tuất – Kỷ Hợi – Giáp Tuất"
    assert tu_tru(14, 5, 1991, 4)["tu_tru"] == "Tân Mùi – Quý Tỵ – Giáp Thân – Bính Dần"
    r = tu_tru(5, 6, 1995, 18, gioi="nu")  # Gói 13
    assert r["tu_tru"] == "Ất Hợi – Tân Tỵ – Đinh Mão – Kỷ Dậu"
    assert r["nhat_chu"] == "Đinh" and r["nhat_chu_hanh"] == "Hỏa" and r["dung_than"] == "Thủy"
    r = tu_tru(12, 5, 1995, 6)
    assert r["tu_tru"] == "Ất Hợi – Tân Tỵ – Quý Mão – Ất Mão"
    assert r["am_lich"].startswith("13/4 ")


def test_nhat_chu_is_day_stem_not_year_stem():
    r = tu_tru(5, 6, 1995, 18)
    assert r["tru"][2].split()[0] == r["nhat_chu"] == "Đinh"
    assert r["tru"][0].split()[0] == "Ất"  # can năm khác Nhật chủ (lỗi từng gặp ở Gói 3, Gói 13)


def test_lunar_input_and_leap():
    assert tu_tru(12, 5, 1995, 6)["tu_tru"] == B.lap_la_so(13, 4, 1995, 6, 0, lich="am")["tu_tru"]
    assert B.lunar2solar(1, 1, 2026) == {"day": 17, "month": 2, "year": 2026}  # Tết Bính Ngọ
    try:
        B.lap_la_so(31, 2, 1995, 8)
    except ValueError:
        pass
    else:
        raise AssertionError("31/2 phải báo lỗi")


def test_year_changes_at_lap_xuan_and_late_ty_hour():
    # 2026: Lập Xuân ~ 04/02; ngày 03/02 vẫn là năm Ất Tỵ
    assert tu_tru(3, 2, 2026, 12)["tru"][0] == "Ất Tỵ"
    assert tu_tru(5, 2, 2026, 12)["tru"][0] == "Bính Ngọ"
    a, b = tu_tru(1, 3, 2000, 22, 30), tu_tru(1, 3, 2000, 23, 30)
    assert a["tru"][2] != b["tru"][2]  # 23h tính sang ngày hôm sau
    assert tu_tru(1, 3, 2000, None)["tru"][3] is None and len(tu_tru(1, 3, 2000, None)["canh_bao"]) >= 1
