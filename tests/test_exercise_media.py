from pathlib import Path

from PIL import Image

from services.exercise_media import build_media, find_images


def write_image(path: Path, color, size=(400, 512), mode="RGB"):
    Image.new(mode, size, color).save(path, "WEBP")


def test_find_images_prefers_start_and_peak(tmp_path):
    write_image(tmp_path / "squat-start.webp", "red")
    write_image(tmp_path / "squat-peak.webp", "blue")
    write_image(tmp_path / "squat.webp", "green")
    images = find_images("squat", tmp_path)
    assert images.kind == "animation"
    assert (images.start.name, images.peak.name) == ("squat-start.webp", "squat-peak.webp")


def test_find_images_falls_back_to_single(tmp_path):
    write_image(tmp_path / "plank-main.webp", "green")
    assert find_images("plank-main", tmp_path).kind == "photo"
    assert find_images("plank-main", tmp_path).still.name == "plank-main.webp"


def test_find_images_single_beats_lonely_start(tmp_path):
    write_image(tmp_path / "dip-start.webp", "red")
    assert find_images("dip", tmp_path).still.name == "dip-start.webp"
    write_image(tmp_path / "dip.webp", "green")
    assert find_images("dip", tmp_path).still.name == "dip.webp"


def test_no_images(tmp_path):
    assert find_images("nothing", tmp_path).kind is None
    assert build_media("nothing", tmp_path, tmp_path / "cache") is None


def test_build_animation_gif_loops_and_is_cached(tmp_path):
    write_image(tmp_path / "squat-start.webp", (255, 0, 0, 0), mode="RGBA")  # transparent
    write_image(tmp_path / "squat-peak.webp", "blue")
    media = build_media("squat", tmp_path, tmp_path / "cache")
    assert media.kind == "animation" and media.path.suffix == ".gif"
    assert media.cache_key.startswith("anim:squat-")
    with Image.open(media.path) as gif:
        assert gif.size == (512, 512)
        assert gif.n_frames == 10           # start, 4 fades, peak, 4 fades
        assert gif.info.get("loop") == 0    # loop forever
        assert gif.convert("RGB").getpixel((256, 256))[0] > 240  # transparency -> white

    mtime = media.path.stat().st_mtime_ns
    again = build_media("squat", tmp_path, tmp_path / "cache")
    assert again.path == media.path and media.path.stat().st_mtime_ns == mtime


def test_changed_images_get_a_new_cache_key(tmp_path):
    write_image(tmp_path / "row-start.webp", "red")
    write_image(tmp_path / "row-peak.webp", "blue")
    first = build_media("row", tmp_path, tmp_path / "cache")
    write_image(tmp_path / "row-peak.webp", "yellow", size=(300, 300))
    assert build_media("row", tmp_path, tmp_path / "cache").cache_key != first.cache_key


def test_single_image_becomes_jpeg(tmp_path):
    write_image(tmp_path / "plank-main.webp", "green")
    media = build_media("plank-main", tmp_path, tmp_path / "cache")
    assert media.kind == "photo" and media.path.suffix == ".jpg"


def test_broken_image_returns_none(tmp_path):
    (tmp_path / "bad-start.webp").write_bytes(b"not an image")
    (tmp_path / "bad-peak.webp").write_bytes(b"not an image")
    assert build_media("bad", tmp_path, tmp_path / "cache") is None
