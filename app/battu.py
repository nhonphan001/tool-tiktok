"""Lõi tính Bát Tự Tử Bình — chuyển nguyên văn từ web tra lá số nangtamchatluongsong.vn (bản đã kiểm chứng).

- Lịch âm: thuật toán Hồ Ngọc Đức (múi giờ +7).
- Tiết khí: kinh độ biểu kiến Mặt Trời theo Meeus. Năm đổi tại Lập Xuân (315°), tháng đổi theo tiết.
- Trụ Ngày = (JDN + 49) mod 60. NHẬT CHỦ LUÔN LÀ CAN CỦA TRỤ NGÀY.
- Trụ Giờ theo canh giờ; sinh 23:00–24:00 mặc định tính sang ngày hôm sau (giờ Tý sớm).

Mọi hàm giữ đúng thứ tự phép tính của bản JavaScript gốc; tests/test_battu.py so khớp hai bản.
"""
from __future__ import annotations

import math

CAN = ["Giáp", "Ất", "Bính", "Đinh", "Mậu", "Kỷ", "Canh", "Tân", "Nhâm", "Quý"]
CHI = ["Tý", "Sửu", "Dần", "Mão", "Thìn", "Tỵ", "Ngọ", "Mùi", "Thân", "Dậu", "Tuất", "Hợi"]
HANH = ["Mộc", "Hỏa", "Thổ", "Kim", "Thủy"]
CAN_HANH = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]
CHI_HANH = [4, 2, 0, 0, 2, 1, 1, 2, 3, 3, 2, 4]
# Tàng can: [(can, tỷ trọng)]
TANG_CAN = [
    [(9, 1)], [(5, .6), (9, .3), (7, .1)], [(0, .6), (2, .3), (4, .1)], [(1, 1)],
    [(4, .6), (1, .3), (9, .1)], [(2, .6), (6, .3), (4, .1)], [(3, .7), (5, .3)],
    [(5, .6), (3, .3), (1, .1)], [(6, .6), (8, .3), (4, .1)], [(7, 1)],
    [(4, .6), (7, .3), (3, .1)], [(8, .7), (0, .3)],
]
TIET_TEN = {315: "Lập Xuân", 345: "Kinh Trập", 15: "Thanh Minh", 45: "Lập Hạ", 75: "Mang Chủng", 105: "Tiểu Thử",
            135: "Lập Thu", 165: "Bạch Lộ", 195: "Hàn Lộ", 225: "Lập Đông", 255: "Đại Tuyết", 285: "Tiểu Hàn"}
PI = math.pi


def INT(d: float) -> int:
    return math.floor(d)


def jd_from_date(dd: int, mm: int, yy: int) -> int:
    a = INT((14 - mm) / 12)
    y = yy + 4800 - a
    m = mm + 12 * a - 3
    jd = dd + INT((153 * m + 2) / 5) + 365 * y + INT(y / 4) - INT(y / 100) + INT(y / 400) - 32045
    if jd < 2299161:
        jd = dd + INT((153 * m + 2) / 5) + 365 * y + INT(y / 4) - 32083
    return jd


def jd_to_date(jd: int) -> tuple[int, int, int]:
    if jd > 2299160:
        a = jd + 32044
        b = INT((4 * a + 3) / 146097)
        c = a - INT((b * 146097) / 4)
    else:
        b = 0
        c = jd + 32082
    d = INT((4 * c + 3) / 1461)
    e = c - INT((1461 * d) / 4)
    m = INT((5 * e + 2) / 153)
    return e - INT((153 * m + 2) / 5) + 1, m + 3 - 12 * INT(m / 10), b * 100 + d - 4800 + INT(m / 10)


def new_moon(k: int) -> float:
    T = k / 1236.85
    T2 = T * T
    T3 = T2 * T
    dr = PI / 180
    Jd1 = 2415020.75933 + 29.53058868 * k + 0.0001178 * T2 - 0.000000155 * T3
    Jd1 += 0.00033 * math.sin((166.56 + 132.87 * T - 0.009173 * T2) * dr)
    M = 359.2242 + 29.10535608 * k - 0.0000333 * T2 - 0.00000347 * T3
    Mpr = 306.0253 + 385.81691806 * k + 0.0107306 * T2 + 0.00001236 * T3
    F = 21.2964 + 390.67050646 * k - 0.0016528 * T2 - 0.00000239 * T3
    C1 = (0.1734 - 0.000393 * T) * math.sin(M * dr) + 0.0021 * math.sin(2 * dr * M)
    C1 = C1 - 0.4068 * math.sin(Mpr * dr) + 0.0161 * math.sin(dr * 2 * Mpr)
    C1 = C1 - 0.0004 * math.sin(dr * 3 * Mpr)
    C1 = C1 + 0.0104 * math.sin(dr * 2 * F) - 0.0051 * math.sin(dr * (M + Mpr))
    C1 = C1 - 0.0074 * math.sin(dr * (M - Mpr)) + 0.0004 * math.sin(dr * (2 * F + M))
    C1 = C1 - 0.0004 * math.sin(dr * (2 * F - M)) - 0.0006 * math.sin(dr * (2 * F + Mpr))
    C1 = C1 + 0.0010 * math.sin(dr * (2 * F - Mpr)) + 0.0005 * math.sin(dr * (2 * Mpr + M))
    if T < -11:
        deltat = 0.001 + 0.000839 * T + 0.0002261 * T2 - 0.00000845 * T3 - 0.000000081 * T * T3
    else:
        deltat = -0.000278 + 0.000265 * T + 0.000262 * T2
    return Jd1 + C1 - deltat


def sun_longitude_deg(jd: float) -> float:
    """Kinh độ biểu kiến Mặt Trời (độ, 0..360) tại JD (giờ quốc tế)."""
    T = (jd - 2451545.0) / 36525
    T2 = T * T
    dr = PI / 180
    M = 357.52910 + 35999.05030 * T - 0.0001559 * T2 - 0.00000048 * T * T2
    L0 = 280.46645 + 36000.76983 * T + 0.0003032 * T2
    DL = (1.914600 - 0.004817 * T - 0.000014 * T2) * math.sin(dr * M)
    DL += (0.019993 - 0.000101 * T) * math.sin(dr * 2 * M) + 0.000290 * math.sin(dr * 3 * M)
    omega = 125.04 - 1934.136 * T
    L = L0 + DL - 0.00569 - 0.00478 * math.sin(omega * dr)
    L = math.fmod(L, 360)
    if L < 0:
        L += 360
    return L


def get_new_moon_day(k: int, tz: float) -> int:
    return INT(new_moon(k) + 0.5 + tz / 24)


def get_sun_longitude_seg(day_number: int, tz: float) -> int:
    return INT(sun_longitude_deg(day_number - 0.5 - tz / 24) / 30)


def get_lunar_month11(yy: int, tz: float) -> int:
    off = jd_from_date(31, 12, yy) - 2415021
    k = INT(off / 29.530588853)
    nm = get_new_moon_day(k, tz)
    if get_sun_longitude_seg(nm, tz) >= 9:
        nm = get_new_moon_day(k - 1, tz)
    return nm


def get_leap_month_offset(a11: int, tz: float) -> int:
    k = INT((a11 - 2415021.076998695) / 29.530588853 + 0.5)
    i = 1
    arc = get_sun_longitude_seg(get_new_moon_day(k + i, tz), tz)
    while True:
        last = arc
        i += 1
        arc = get_sun_longitude_seg(get_new_moon_day(k + i, tz), tz)
        if not (arc != last and i < 14):
            break
    return i - 1


def solar2lunar(dd: int, mm: int, yy: int, tz: float = 7) -> dict:
    day_number = jd_from_date(dd, mm, yy)
    k = INT((day_number - 2415021.076998695) / 29.530588853)
    month_start = get_new_moon_day(k + 1, tz)
    if month_start > day_number:
        month_start = get_new_moon_day(k, tz)
    a11 = get_lunar_month11(yy, tz)
    b11 = a11
    if a11 >= month_start:
        lunar_year = yy
        a11 = get_lunar_month11(yy - 1, tz)
    else:
        lunar_year = yy + 1
        b11 = get_lunar_month11(yy + 1, tz)
    lunar_day = day_number - month_start + 1
    diff = INT((month_start - a11) / 29)
    lunar_leap = 0
    lunar_month = diff + 11
    if b11 - a11 > 365:
        leap_month_diff = get_leap_month_offset(a11, tz)
        if diff >= leap_month_diff:
            lunar_month = diff + 10
            if diff == leap_month_diff:
                lunar_leap = 1
    if lunar_month > 12:
        lunar_month -= 12
    if lunar_month >= 11 and diff < 4:
        lunar_year -= 1
    return {"day": lunar_day, "month": lunar_month, "year": lunar_year, "leap": lunar_leap}


def lunar2solar(lunar_day: int, lunar_month: int, lunar_year: int, lunar_leap: int = 0, tz: float = 7) -> dict | None:
    if lunar_month < 11:
        a11 = get_lunar_month11(lunar_year - 1, tz)
        b11 = get_lunar_month11(lunar_year, tz)
    else:
        a11 = get_lunar_month11(lunar_year, tz)
        b11 = get_lunar_month11(lunar_year + 1, tz)
    k = INT(0.5 + (a11 - 2415021.076998695) / 29.530588853)
    off = lunar_month - 11
    if off < 0:
        off += 12
    if b11 - a11 > 365:
        leap_off = get_leap_month_offset(a11, tz)
        leap_month = leap_off - 2
        if leap_month < 0:
            leap_month += 12
        if lunar_leap and lunar_month != leap_month:
            return None
        if lunar_leap or off >= leap_off:
            off += 1
    elif lunar_leap:
        return None
    month_start = get_new_moon_day(k + off, tz)
    d = jd_to_date(month_start + lunar_day - 1)
    back = solar2lunar(d[0], d[1], d[2], tz)  # kiểm tra ngày âm có tồn tại (tháng thiếu 29 ngày)
    if back["day"] != lunar_day or back["month"] != lunar_month:
        return None
    return {"day": d[0], "month": d[1], "year": d[2]}


def instant_jd(dd: int, mm: int, yy: int, h: float, mi: float, tz: float) -> float:
    """JD (giờ quốc tế) của một thời điểm giờ địa phương."""
    return jd_from_date(dd, mm, yy) - 0.5 + (h + mi / 60 - tz) / 24


def find_sun_longitude(target: float, jd_start: float, direction: int) -> float:
    """Thời điểm Mặt Trời đạt kinh độ target gần jd_start, hướng +1 (sau) / -1 (trước)."""
    def dist(L):
        d = math.fmod(target - L, 360)
        if d < 0:
            d += 360
        return d

    jd = jd_start
    if direction > 0:
        jd += dist(sun_longitude_deg(jd)) / 0.9856
    else:
        jd -= math.fmod(360 - dist(sun_longitude_deg(jd)), 360) / 0.9856
    for _ in range(8):
        d = target - sun_longitude_deg(jd)
        d = math.fmod(d + 540, 360) - 180
        jd += d / 0.9856
    return jd


def ganzhi(i: int) -> dict:
    i = ((i % 60) + 60) % 60
    return {"can": i % 10, "chi": i % 12, "idx": i}


def name(p: dict | None) -> str:
    return f"{CAN[p['can']]} {CHI[p['chi']]}" if p else "?"


def la_so(dd: int, mm: int, yy: int, h: int | None = None, mi: int | None = 0, tz: float = 7,
          gioi: str | None = None, ty_muon_sang_ngay_moi: bool = True, lech_phut: float = 0) -> dict:
    """Lập tứ trụ. h=None nếu không rõ giờ. gioi: 'nam' | 'nu' (để tính Đại vận)."""
    co_gio = h is not None
    hh = h if co_gio else 12
    mm_ = (mi or 0) if co_gio else 0
    jd = instant_jd(dd, mm, yy, hh, mm_, tz)
    lam = sun_longitude_deg(jd)

    # Năm: đổi tại Lập Xuân (315°)
    nam = yy
    if mm <= 2 and 270 <= lam < 315:
        nam -= 1
    if mm == 1 and 200 < lam < 315:
        nam = yy - 1
    tu_nam = ganzhi(nam - 4)

    # Tháng: chi theo kinh độ Mặt Trời, Dần bắt đầu tại 315°
    m = INT(math.fmod(lam - 315 + 360, 360) / 30)  # 0 = Dần
    thang_chi = (m + 2) % 12
    thang_can = (tu_nam["can"] * 2 + 2 + m) % 10
    tu_thang = {"can": thang_can, "chi": thang_chi}

    # Giờ dùng cho trụ Ngày và trụ Giờ: giờ đồng hồ (+ hiệu chỉnh giờ mặt trời nếu có)
    jdn = jd_from_date(dd, mm, yy)
    phut = hh * 60 + mm_ + (lech_phut if co_gio else 0)
    while phut < 0:
        phut += 1440
        jdn -= 1
    while phut >= 1440:
        phut -= 1440
        jdn += 1
    if co_gio and ty_muon_sang_ngay_moi and phut >= 23 * 60:
        jdn += 1
    tu_ngay = ganzhi(jdn + 49)

    tu_gio = None
    if co_gio:
        gio_chi = INT((phut + 60) / 120) % 12
        tu_gio = {"can": (tu_ngay["can"] * 2 + gio_chi) % 10, "chi": gio_chi}
    phut_toi_canh = min(math.fmod(phut + 60, 120), 120 - math.fmod(phut + 60, 120)) if co_gio else None

    deg = math.fmod(lam - 315 + 360, 30)
    gio_toi_tiet = min(deg, 30 - deg) / 0.9856 * 24

    am = solar2lunar(dd, mm, yy, tz)

    dai_van = None
    if gioi:
        duong_nam = tu_nam["can"] % 2 == 0
        thuan = (duong_nam and gioi == "nam") or (not duong_nam and gioi == "nu")
        base = 315 + m * 30
        jd_tiet = find_sun_longitude((base + 30) % 360, jd, 1) if thuan else find_sun_longitude(base % 360, jd, -1)
        so_ngay = abs(jd_tiet - jd)
        tuoi_khoi = so_ngay / 3  # 3 ngày = 1 năm
        thang_idx = (tu_nam["can"] * 2 + 2 + m) % 10
        lst = []
        for i in range(1, 9):
            c = ((thang_idx + (i if thuan else -i)) % 10 + 10) % 10
            ch = ((thang_chi + (i if thuan else -i)) % 12 + 12) % 12
            tuoi = tuoi_khoi + (i - 1) * 10
            lst.append({"can": c, "chi": ch, "tu_tuoi": tuoi, "nam_bat_dau": yy + tuoi})
        dai_van = {"thuan": thuan, "tuoi_khoi": tuoi_khoi, "list": lst}

    return {"tru": [tu_nam, tu_thang, tu_ngay, tu_gio], "co_gio": co_gio, "lambda": lam, "gio_toi_tiet": gio_toi_tiet,
            "phut_toi_canh": phut_toi_canh, "phut_mat_troi": phut if co_gio else None, "am": am, "dai_van": dai_van,
            "nhat_chu": tu_ngay["can"]}


def ngu_hanh(ls: dict) -> dict:
    """Cân bằng ngũ hành và gợi ý Dụng Thần (giản lược, mang tính tham khảo)."""
    W_CAN = 1.0
    W_CHI = [1.0, 2.5, 1.2, 1.0]  # năm, tháng, ngày, giờ
    diem = [0.0] * 5
    for i, p in enumerate(ls["tru"]):
        if not p:
            continue
        if i != 2:  # không tính chính Nhật chủ
            diem[CAN_HANH[p["can"]]] += W_CAN
        for c, w in TANG_CAN[p["chi"]]:
            diem[CAN_HANH[c]] += w * W_CHI[i]
    D = CAN_HANH[ls["nhat_chu"]]
    ty_kien, an = diem[D], diem[(D + 4) % 5]
    thuc, tai, quan = diem[(D + 1) % 5], diem[(D + 2) % 5], diem[(D + 3) % 5]
    ho, khac = ty_kien + an, thuc + tai + quan
    ty_le = ho / (ho + khac)
    if ty_le < 0.45:
        trang_thai, dung, hy, ky = "nhuoc", (D + 4) % 5, D, [(D + 2) % 5, (D + 3) % 5]
    elif ty_le > 0.55:
        trang_thai = "vuong"
        if ty_kien >= an:
            dung, hy = (D + 3) % 5, (D + 1) % 5
        else:
            dung, hy = (D + 2) % 5, (D + 1) % 5
        ky = [D, (D + 4) % 5]
    else:
        trang_thai = "can_bang"
        mn = 0
        for e in range(1, 5):
            if diem[e] < diem[mn]:
                mn = e
        dung, hy, ky = mn, (mn + 4) % 5, []
    tong = sum(diem)
    thang_chi = ls["tru"][1]["chi"]
    dieu_hau = None
    if thang_chi in (11, 0, 1) and diem[1] / tong < 0.12:
        dieu_hau = 1
    if thang_chi in (5, 6, 7) and diem[4] / tong < 0.12:
        dieu_hau = 4
    return {"diem": diem, "ty_le_phan_tram": [d / tong for d in diem], "D": D, "ty_le": ty_le,
            "trang_thai": trang_thai, "dung": dung, "hy": hy, "ky": ky, "dieu_hau": dieu_hau}


THAP_THAN = [["Tỷ Kiên", "Kiếp Tài"], ["Thực Thần", "Thương Quan"], ["Thiên Tài", "Chính Tài"],
             ["Thất Sát", "Chính Quan"], ["Thiên Ấn", "Chính Ấn"]]


def thap_than(nhat_chu: int, can: int) -> str:
    rel = (CAN_HANH[can] - CAN_HANH[nhat_chu] + 5) % 5
    return THAP_THAN[rel][0 if (nhat_chu % 2) == (can % 2) else 1]


NAP_AM = ["Hải Trung Kim", "Lô Trung Hỏa", "Đại Lâm Mộc", "Lộ Bàng Thổ", "Kiếm Phong Kim", "Sơn Đầu Hỏa",
          "Giản Hạ Thủy", "Thành Đầu Thổ", "Bạch Lạp Kim", "Dương Liễu Mộc", "Tuyền Trung Thủy", "Ốc Thượng Thổ",
          "Tích Lịch Hỏa", "Tùng Bách Mộc", "Trường Lưu Thủy", "Sa Trung Kim", "Sơn Hạ Hỏa", "Bình Địa Mộc",
          "Bích Thượng Thổ", "Kim Bạch Kim", "Phú Đăng Hỏa", "Thiên Hà Thủy", "Đại Trạch Thổ", "Thoa Xuyến Kim",
          "Tang Đố Mộc", "Đại Khê Thủy", "Sa Trung Thổ", "Thiên Thượng Hỏa", "Thạch Lựu Mộc", "Đại Hải Thủy"]


def chi_so60(p: dict) -> int:
    return ((6 * p["can"] - 5 * p["chi"]) % 60 + 60) % 60


def nap_am(p: dict) -> str:
    return NAP_AM[INT(chi_so60(p) / 2)]


TRUONG_SINH = ["Trường Sinh", "Mộc Dục", "Quan Đới", "Lâm Quan", "Đế Vượng", "Suy", "Bệnh", "Tử", "Mộ", "Tuyệt",
               "Thai", "Dưỡng"]
TS_GOC = [11, 6, 2, 9, 2, 9, 5, 0, 8, 3]


def truong_sinh(can: int, chi: int) -> str:
    k = (chi - TS_GOC[can] + 12) % 12 if can % 2 == 0 else (TS_GOC[can] - chi + 12) % 12
    return TRUONG_SINH[k]


def khong_vong(p: dict) -> list[int]:
    b = ((p["chi"] - p["can"]) % 12 + 12) % 12
    return [(b + 10) % 12, (b + 11) % 12]


TAM_HOP = [[8, 0, 4, 4], [11, 3, 7, 0], [2, 6, 10, 1], [5, 9, 1, 3]]
TAM_HOI = [[2, 3, 4, 0], [5, 6, 7, 1], [8, 9, 10, 3], [11, 0, 1, 4]]
LUC_HOP_HANH = {"0-1": 2, "2-11": 0, "3-10": 1, "4-9": 3, "5-8": 4, "6-7": 1}
NGU_HOP_HANH = {"0-5": 2, "1-6": 3, "2-7": 4, "3-8": 0, "4-9": 1}
TEN_VT = ["Năm", "Tháng", "Ngày", "Giờ"]


def quan_he(tru: list) -> list[dict]:
    ds = []
    ps = [{"p": p, "i": i} for i, p in enumerate(tru) if p]
    for a in range(len(ps)):
        for b in range(a + 1, len(ps)):
            A, Bp = ps[a], ps[b]
            vt = TEN_VT[A["i"]] + "–" + TEN_VT[Bp["i"]]
            c1, c2 = min(A["p"]["can"], Bp["p"]["can"]), max(A["p"]["can"], Bp["p"]["can"])
            if c2 - c1 == 5:
                ds.append({"loai": "hop", "vt": vt, "ten": f"{CAN[A['p']['can']]} – {CAN[Bp['p']['can']]} ngũ hợp hóa "
                                                          f"{HANH[NGU_HOP_HANH[f'{c1}-{c2}']]}"})
            if c2 - c1 == 6 and c1 < 4:
                ds.append({"loai": "xung", "vt": vt, "ten": f"{CAN[A['p']['can']]} – {CAN[Bp['p']['can']]} tương xung"})
            x, y = A["p"]["chi"], Bp["p"]["chi"]
            k1, k2 = min(x, y), max(x, y)
            tx = f"{CHI[x]} – {CHI[y]}"
            if (x + y) % 12 == 1 and x != y:
                ds.append({"loai": "hop", "vt": vt, "ten": f"{tx} lục hợp ({HANH[LUC_HOP_HANH[f'{k1}-{k2}']]})"})
            if abs(x - y) == 6:
                ds.append({"loai": "xung", "vt": vt, "ten": f"{tx} lục xung"})
            if (x + y) % 12 == 7:
                ds.append({"loai": "hai", "vt": vt, "ten": f"{tx} tương hại"})
            if k1 == 0 and k2 == 3:
                ds.append({"loai": "hinh", "vt": vt, "ten": f"{tx} tương hình (vô lễ)"})
            if (k1, k2) in ((2, 5), (5, 8), (2, 8)):
                ds.append({"loai": "hinh", "vt": vt, "ten": f"{tx} tương hình (vô ân)"})
            if (k1, k2) in ((1, 10), (7, 10), (1, 7)):
                ds.append({"loai": "hinh", "vt": vt, "ten": f"{tx} tương hình (cậy thế)"})
            if x == y and x in (4, 6, 9, 11):
                ds.append({"loai": "hinh", "vt": vt, "ten": f"{tx} tự hình"})
    chis = [o["p"]["chi"] for o in ps]
    for a, b, c, e in TAM_HOP:
        co = [z for z in (a, b, c) if z in chis]
        if len(co) == 3:
            ds.append({"loai": "hop", "vt": "Tam hợp", "ten": f"{CHI[a]} – {CHI[b]} – {CHI[c]} tam hợp {HANH[e]} cục"})
        elif len(co) == 2 and b in co:
            ds.append({"loai": "hop", "vt": "Bán hợp", "ten": " – ".join(CHI[z] for z in co) + f" bán hợp {HANH[e]}"})
    for a, b, c, e in TAM_HOI:
        if all(z in chis for z in (a, b, c)):
            ds.append({"loai": "hop", "vt": "Tam hội", "ten": f"{CHI[a]} – {CHI[b]} – {CHI[c]} tam hội {HANH[e]} phương"})
    return ds


def phut_gio_mat_troi(dd: int, mm: int, yy: int, kinh_do: float, tz: float = 7) -> dict:
    """Phương trình thời gian (phút) và số phút cần cộng để ra giờ mặt trời thật."""
    N = jd_from_date(dd, mm, yy) - jd_from_date(1, 1, yy) + 1
    Bg = 2 * PI * (N - 81) / 365
    eot = 9.87 * math.sin(2 * Bg) - 7.53 * math.cos(Bg) - 1.5 * math.sin(Bg)
    return {"lech": 4 * (kinh_do - tz * 15) + eot, "eot": eot, "kinh_do_phut": 4 * (kinh_do - tz * 15)}


def tang_can(chi: int) -> list[dict]:
    return [{"can": c, "w": w} for c, w in TANG_CAN[chi]]


# ---------------------------------------------------------------- tiện ích hiển thị (dùng trong TikTok Manager)
NHAT_CHU_TA = {"Giáp": "cây đại thụ", "Ất": "hoa cỏ, dây leo", "Bính": "mặt trời", "Đinh": "ngọn đèn, ánh nến",
               "Mậu": "núi cao, đất dày", "Kỷ": "đất ruộng vườn", "Canh": "kim loại thô, đao kiếm",
               "Tân": "trang sức, kim loại quý", "Nhâm": "sông lớn, biển cả", "Quý": "mưa móc, sương sớm"}
TRANG_THAI_TEN = {"nhuoc": "Thân nhược", "vuong": "Thân vượng", "can_bang": "Gần cân bằng"}
GIO_CHI_GIUA = {i: (i * 2) % 24 for i in range(12)}  # giờ giữa mỗi canh: Tý 0h, Sửu 2h, ... Hợi 22h


def lap_la_so(dd: int, mm: int, yy: int, h: int | None = None, mi: int | None = 0, gioi: str | None = None,
              lich: str = "duong", nhuan: bool = False, tz: float = 7) -> dict:
    """Lập lá số đầy đủ từ dữ liệu người dùng (dương hoặc âm lịch). Trả về dict để hiển thị/ghi kịch bản."""
    goc = {"dd": dd, "mm": mm, "yy": yy, "lich": lich, "nhuan": nhuan}
    if lich == "am":
        d = lunar2solar(dd, mm, yy, 1 if nhuan else 0, tz)
        if not d:
            raise ValueError(f"Ngày âm lịch {dd}/{mm}{' nhuận' if nhuan else ''}/{yy} không tồn tại")
        dd, mm, yy = d["day"], d["month"], d["year"]
    if not (1 <= mm <= 12 and 1900 <= yy <= 2100) or dd < 1 or dd > 31:
        raise ValueError("Ngày, tháng hoặc năm chưa hợp lệ (năm 1900–2100)")
    import datetime as _dt
    try:
        _dt.date(yy, mm, dd)
    except ValueError:
        raise ValueError(f"Tháng {mm} năm {yy} không có ngày {dd}")
    if h is not None and not (0 <= h <= 23 and 0 <= (mi or 0) <= 59):
        raise ValueError("Giờ sinh không hợp lệ")
    ls = la_so(dd, mm, yy, h, mi or 0, tz, gioi)
    nh = ngu_hanh(ls)
    nc = ls["nhat_chu"]
    tru = ls["tru"]
    canh_bao = []
    if h is None:
        canh_bao.append("Chưa có giờ sinh: lá số chỉ có 3 trụ, phần ngũ hành và Dụng thần chỉ để tham khảo sơ bộ.")
    if ls["gio_toi_tiet"] < 3:
        canh_bao.append(f"Sinh cách ranh giới tiết khí khoảng {ls['gio_toi_tiet']:.1f} giờ: giờ sinh lệch ít phút "
                        "là trụ tháng (có thể cả trụ năm) đổi. Cần giờ sinh chính xác.")
    if h is not None and ls["phut_toi_canh"] is not None and ls["phut_toi_canh"] < 10:
        canh_bao.append(f"Giờ sinh cách ranh giới canh giờ khoảng {ls['phut_toi_canh']:.0f} phút: trụ Giờ có thể "
                        "thuộc canh liền kề nếu giờ khai sinh được làm tròn.")
    if h == 23:
        canh_bao.append("Sinh sau 23:00 nên trụ Ngày đã tính sang ngày hôm sau (giờ Tý sớm).")
    if nh["trang_thai"] == "can_bang" or abs(nh["ty_le"] - 0.45) < 0.04 or abs(nh["ty_le"] - 0.55) < 0.04:
        canh_bao.append("Độ vượng nhược của Nhật chủ sát ngưỡng: Dụng thần chỉ là hướng gợi ý.")
    am = ls["am"]
    am_nam = f"{CAN[(am['year'] - 4 + 6000) % 10]} {CHI[(am['year'] - 4 + 6000) % 12]}"
    return {
        "dau_vao": goc,
        "duong_lich": f"{dd:02d}/{mm:02d}/{yy}",
        "gio": f"{h:02d}:{(mi or 0):02d}" if h is not None else "không rõ giờ",
        "am_lich": f"{am['day']}/{am['month']}{' (nhuận)' if am['leap'] else ''} năm {am_nam}",
        "gioi": gioi,
        "tru": [name(p) if p else None for p in tru],
        "tu_tru": " – ".join(name(p) for p in tru if p),
        "nhat_chu": CAN[nc],
        "nhat_chu_hanh": HANH[CAN_HANH[nc]],
        "nhat_chu_ta": NHAT_CHU_TA[CAN[nc]],
        "thap_than": [("Nhật chủ" if i == 2 else thap_than(nc, p["can"])) if p else None for i, p in enumerate(tru)],
        "tang_can": [[f"{CAN[t['can']]} ({thap_than(nc, t['can'])})" for t in tang_can(p["chi"])] if p else None
                     for p in tru],
        "nap_am": [nap_am(p) if p else None for p in tru],
        "truong_sinh": [truong_sinh(nc, p["chi"]) if p else None for p in tru],
        "khong_vong": [CHI[c] for c in khong_vong(tru[2])],
        "quan_he": [q["ten"] for q in quan_he(tru)],
        "ngu_hanh_diem": {HANH[i]: round(d, 2) for i, d in enumerate(nh["diem"])},
        "trang_thai": TRANG_THAI_TEN[nh["trang_thai"]],
        "dung_than": HANH[nh["dung"]],
        "hy_than": HANH[nh["hy"]],
        "ky_than": [HANH[k] for k in nh["ky"]],
        "dieu_hau": HANH[nh["dieu_hau"]] if nh["dieu_hau"] is not None else None,
        "dai_van": ([{"tru": name(v), "tu_tuoi": round(v["tu_tuoi"], 1), "nam": round(v["nam_bat_dau"])}
                     for v in ls["dai_van"]["list"]] if ls["dai_van"] else None),
        "dai_van_thuan": ls["dai_van"]["thuan"] if ls["dai_van"] else None,
        "canh_bao": canh_bao,
    }


def mo_ta_ngan(r: dict) -> str:
    """Dòng tóm tắt dùng cho kịch bản / khối nhan_video."""
    return (f"{r['duong_lich']} {r['gio']} = {r['tu_tru']} (Nhật chủ {r['nhat_chu']} {r['nhat_chu_hanh']}, "
            f"{r['trang_thai']}, Dụng {r['dung_than']})")
