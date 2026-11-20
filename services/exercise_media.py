"""
Exercise images and animations (no Telegram code).

Image files live in assets/exercises/ and are named after the exercise id:
  {id}-start.webp + {id}-peak.webp  -> shown as a looping animation
  {id}.webp or {id}-main.webp       -> single image (e.g. plank-main.webp)
If start/peak are missing we fall back to the single image; if only one of
start/peak exists, that one is shown as a still image.

Animations are built as small looping GIFs: hold the start position, fade to
the peak, hold, fade back. Telegram converts GIFs to looping MP4 itself, so no
ffmpeg is needed. Built files are cached in assets/cache/.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from PIL import Image
except ImportError as error:
    # Pillow ships native DLLs, which Windows Smart App Control can block.
    # The bot still runs; exercise cards are shown as text only.
    Image = None
    logger.warning("Pillow unavailable (%s): exercise images are disabled", error)

ROOT = Path(__file__).resolve().parent.parent
IMAGE_DIR = ROOT / "assets" / "exercises"
CACHE_DIR = ROOT / "assets" / "cache"
EXTENSIONS = (".webp", ".png", ".jpg", ".jpeg")

FRAME_SIZE = 512
HOLD_MS = 900      # how long each position is held
FADE_FRAMES = 4    # in-between frames for the crossfade
FADE_FRAME_MS = 70


@dataclass(frozen=True)
class ExerciseImages:
    start: Path | None = None
    peak: Path | None = None
    single: Path | None = None

    @property
    def kind(self) -> str | None:
        """'animation', 'photo' or None (no images)."""
        if self.start and self.peak:
            return "animation"
        if self.single or self.start or self.peak:
            return "photo"
        return None

    @property
    def still(self) -> Path | None:
        """The image to use when we can't animate."""
        return self.single or self.start or self.peak


@dataclass(frozen=True)
class ExerciseMedia:
    kind: str        # "animation" or "photo"
    path: Path       # file ready to upload
    cache_key: str   # changes whenever the source images change


def _find(base: str, image_dir: Path) -> Path | None:
    for ext in EXTENSIONS:
        path = image_dir / f"{base}{ext}"
        if path.is_file():
            return path
    return None


def find_images(exercise_id: str, image_dir: Path | None = None) -> ExerciseImages:
    image_dir = image_dir or IMAGE_DIR
    start = _find(f"{exercise_id}-start", image_dir)
    peak = _find(f"{exercise_id}-peak", image_dir)
    if start and peak:
        return ExerciseImages(start=start, peak=peak)
    # RepDB names single-frame pictures "<id>-main.webp"; our curated ones use
    # the bare "<id>.webp". Accept both so imported exercises find their image.
    single = _find(exercise_id, image_dir) or _find(f"{exercise_id}-main", image_dir)
    if single:
        return ExerciseImages(single=single)
    return ExerciseImages(start=start, peak=peak)  # one of them, or nothing


def _fingerprint(*paths: Path) -> str:
    """Short hash of file names, sizes and modification times."""
    raw = "|".join(f"{p.name}:{p.stat().st_size}:{p.stat().st_mtime_ns}" for p in paths)
    return hashlib.sha1(raw.encode()).hexdigest()[:10]


def _load_frame(path: Path) -> Image.Image:
    """Open an image, put transparent areas on white, fit it in a square canvas."""
    with Image.open(path) as img:
        img = img.convert("RGBA")
        img.thumbnail((FRAME_SIZE, FRAME_SIZE))
        canvas = Image.new("RGBA", (FRAME_SIZE, FRAME_SIZE), "white")
        offset = ((FRAME_SIZE - img.width) // 2, (FRAME_SIZE - img.height) // 2)
        canvas.alpha_composite(img, offset)
        return canvas.convert("RGB")


def _build_gif(start: Path, peak: Path, target: Path) -> None:
    a, b = _load_frame(start), _load_frame(peak)
    fade_in = [Image.blend(a, b, i / (FADE_FRAMES + 1)) for i in range(1, FADE_FRAMES + 1)]
    fade_out = [Image.blend(b, a, i / (FADE_FRAMES + 1)) for i in range(1, FADE_FRAMES + 1)]
    frames = [a, *fade_in, b, *fade_out]
    durations = [HOLD_MS] + [FADE_FRAME_MS] * FADE_FRAMES + [HOLD_MS] + [FADE_FRAME_MS] * FADE_FRAMES

    palette_frames = [f.convert("P", palette=Image.Palette.ADAPTIVE, colors=255) for f in frames]
    palette_frames[0].save(
        target, save_all=True, append_images=palette_frames[1:],
        duration=durations, loop=0, optimize=True, disposal=1,
    )


def _build_jpeg(source: Path, target: Path) -> None:
    # Telegram photos must be JPEG/PNG; WebP would be shown as a sticker.
    _load_frame(source).save(target, "JPEG", quality=88)


def build_media(exercise_id: str, image_dir: Path | None = None,
                cache_dir: Path | None = None) -> ExerciseMedia | None:
    """Return a ready-to-upload file for this exercise, building it if needed."""
    images = find_images(exercise_id, image_dir)
    cache_dir = cache_dir or CACHE_DIR
    if images.kind is None or Image is None:
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)

    try:
        if images.kind == "animation":
            key = f"{exercise_id}-{_fingerprint(images.start, images.peak)}"
            target = cache_dir / f"{key}.gif"
            if not target.exists():
                _build_gif(images.start, images.peak, target)
            return ExerciseMedia("animation", target, f"anim:{key}")

        key = f"{exercise_id}-{_fingerprint(images.still)}"
        target = cache_dir / f"{key}.jpg"
        if not target.exists():
            _build_jpeg(images.still, target)
        return ExerciseMedia("photo", target, f"photo:{key}")
    except (OSError, ValueError):
        # A broken image file shouldn't break the exercise card: show text only.
        logger.exception("Could not build media for exercise '%s'", exercise_id)
        return None
