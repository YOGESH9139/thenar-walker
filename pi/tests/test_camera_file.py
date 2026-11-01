from io import BytesIO

from PIL import Image

from thenar_pi.camera import Camera


def test_file_camera_reads_current_image(tmp_path, monkeypatch):
    path = tmp_path / "shelf.png"
    Image.new("RGB", (16, 12), "red").save(path)
    monkeypatch.setenv("THENAR_CAMERA", f"file:{path}")
    camera = Camera()
    assert camera.kind == "file"
    first = Image.open(BytesIO(camera.jpeg())).convert("RGB")
    assert first.size == (16, 12) and first.getpixel((4, 4))[0] > 200
    Image.new("RGB", (16, 12), "blue").save(path)
    second = Image.open(BytesIO(camera.jpeg())).convert("RGB")
    assert second.getpixel((4, 4))[2] > 200
