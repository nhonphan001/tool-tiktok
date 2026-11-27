"""Kiểm tra tự động gắn ảnh cảnh & ảnh bìa thương hiệu từ thư mục 01_KICH_BAN_VA_ANH_AI."""
import io
import zipfile

from app import media, packages, scene_images


def test_parse_image_scenes_and_cover():
    assert scene_images.parse_image("GOI_36_V3_3_CANH_1_NhamNgo2002_RotTraNangSang.jpg") == ("36", "image1")
    assert scene_images.parse_image("GOI_36_V3_3_CANH_7_NhamNgo2002_MoiChenTraBinhLuan.jpg") == ("36", "image7")
    assert scene_images.parse_image("Goi_05_canh_4.png") == ("5", "image4")
    assert scene_images.parse_image("GOI_36_ANH_BIA_HOOK.png") == ("36", "cover_image")
    assert scene_images.parse_image("GOI_36_ANH_BIA_HOOK (1).png") == ("36", "cover_image")
    assert scene_images.parse_image("random_image.jpg") is None


def test_index_prefers_clean_cover_over_duplicate_suffix():
    files = [
        {"id": "1aaaaaaaaaaaaaaaaaaaaaaaaaaa", "name": "GOI_36_ANH_BIA_HOOK.png", "modifiedTime": "2026-11-27T11:47:45Z"},
        {"id": "1bbbbbbbbbbbbbbbbbbbbbbbbbbb", "name": "GOI_36_ANH_BIA_HOOK (1).png", "modifiedTime": "2026-11-27T17:56:46Z"},
        {"id": "1ccccccccccccccccccccccccccc", "name": "GOI_36_V3_3_CANH_1_NhamNgo2002_RotTraNangSang.jpg", "modifiedTime": "2026-11-27T17:55:28Z"},
    ]
    idx = scene_images.index_by_goi(files)
    assert idx["36"]["cover_image"]["id"] == "1aaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert idx["36"]["image1"]["id"] == "1ccccccccccccccccccccccccccc"


def test_sync_attaches_7_scenes_and_cover_to_package(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.database_path", str(tmp_path / "test.db"))
    pid = packages.save({"goi": "36", "title": "Nhâm Ngọ 2002", "loai": 1, "scene1": "Test 1"})
    files = [
        {"id": f"1fileidcanh{i:02d}xxxxxxxxxxxxxxxx", "name": f"GOI_36_V3_3_CANH_{i}_NhamNgo2002.jpg", "modifiedTime": "2026-11-27T17:55:00Z"}
        for i in range(1, 8)
    ] + [
        {"id": "1fileidcoverxxxxxxxxxxxxxxxxx", "name": "GOI_36_ANH_BIA_HOOK.png", "modifiedTime": "2026-11-27T18:13:00Z"},
    ]
    msgs = scene_images.sync(files=files, only_goi="36")
    assert len(msgs) == 1
    assert "7 ảnh cảnh" in msgs[0] and "ảnh bìa" in msgs[0]
    p = packages.get(pid)
    assert p["cover_image"] == "1fileidcoverxxxxxxxxxxxxxxxxx"
    for i in range(1, 8):
        assert p[f"image{i}"] == f"1fileidcanh{i:02d}xxxxxxxxxxxxxxxx"
    assert media.file_id_for(p, "cover_image") == "1fileidcoverxxxxxxxxxxxxxxxxx"


def test_images_zip_includes_cover_and_scenes(tmp_path, monkeypatch):
    cov_f = tmp_path / "cov.png"
    cov_f.write_bytes(b"PNGCOVER")
    sc1_f = tmp_path / "c1.jpg"
    sc1_f.write_bytes(b"JPGSCENE1")

    def fake_fetch(fid):
        if fid == "1fileidcoverxxxxxxxxxxxxxxxxx":
            return str(cov_f), {"name": "GOI_36_ANH_BIA_HOOK.png", "mimeType": "image/png"}
        return str(sc1_f), {"name": "GOI_36_V3_3_CANH_1.jpg", "mimeType": "image/jpeg"}

    monkeypatch.setattr(media, "fetch", fake_fetch)
    p = {
        "cover_image": "1fileidcoverxxxxxxxxxxxxxxxxx",
        "image1": "1fileidcanh01xxxxxxxxxxxxxxxx",
    }
    raw, errs = media.images_zip(p)
    assert not errs
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = z.namelist()
    assert "00_anh_bia_hook__GOI_36_ANH_BIA_HOOK.png" in names
    assert "canh_1__GOI_36_V3_3_CANH_1.jpg" in names
