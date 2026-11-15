"""
Exercise library for the Mini App: search, filters, "fits my profile",
substitutes and image URLs. Reuses the plan rules in services/exercises.py,
so the library and the plans always agree on what a user can do.
"""
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from database.models import Exercise
from services.exercise_media import find_images
from services.exercises import (DIFFICULTY_LEVEL, EXPERIENCE_LEVEL, UserFilter, equipment_ok,
                                get_injury_rules, injury_ok, is_available, rank_key)
from utils.texts import SUPPORTED_LANGUAGES, label

MAX_QUERY = 60


def unavailable_reasons(exercise: Exercise, user: UserFilter,
                        rules: dict[str, set[str]] | None = None) -> list[str]:
    """Why an exercise isn't in this user's plans: 'equipment', 'level', 'injury' (empty = fits)."""
    reasons = []
    if not equipment_ok(exercise, user.equipment):
        reasons.append("equipment")
    if DIFFICULTY_LEVEL[exercise.difficulty] == 2 and EXPERIENCE_LEVEL[user.experience] < 2:
        reasons.append("level")
    if not injury_ok(exercise, user.injuries, rules):
        reasons.append("injury")
    return reasons


def _normalize(text: str) -> str:
    return " ".join(text.casefold().replace("-", " ").replace("ё", "е").split())


def _search_text(exercise: Exercise) -> str:
    """Name, id and every muscle's name in every language, so 'грудь' finds chest exercises."""
    parts = [exercise.name, exercise.id]
    for muscle in [exercise.muscle_group, *(exercise.secondary_muscles or [])]:
        parts += [label("muscle", muscle, lang) for lang in SUPPORTED_LANGUAGES]
    return _normalize(" ".join(parts))


@dataclass(frozen=True)
class Filters:
    q: str = ""
    muscle: str | None = None        # primary OR secondary muscle
    equipment: str | None = None
    difficulty: str | None = None
    home: bool = False                # home-friendly only
    fits: bool = False                # only what fits the user's profile


def search(catalog: list[Exercise], filters: Filters, user: UserFilter | None = None) -> list[Exercise]:
    """Matching exercises, A-Z by name."""
    words = _normalize(filters.q[:MAX_QUERY]).split()
    rules = get_injury_rules() if user is not None else None
    result = []
    for ex in catalog:
        if filters.muscle and filters.muscle != ex.muscle_group \
                and filters.muscle not in (ex.secondary_muscles or []):
            continue
        if filters.equipment and ex.equipment != filters.equipment:
            continue
        if filters.difficulty and ex.difficulty != filters.difficulty:
            continue
        if filters.home and not ex.home_friendly:
            continue
        if filters.fits and user is not None and not is_available(ex, user, rules):
            continue
        if words:
            text = _search_text(ex)
            if not all(word in text for word in words):
                continue
        result.append(ex)
    return sorted(result, key=lambda ex: ex.name.casefold())


def substitutes(exercise: Exercise, catalog: dict[str, Exercise], user: UserFilter | None,
                limit: int = 6) -> list[Exercise]:
    """
    Curated substitute_ids first (in order), then same muscle and movement type.
    With a profile, ones that fit come first, ranked like the plan generator does.
    """
    seen = {exercise.id}
    picks: list[Exercise] = []
    for sub_id in exercise.substitute_ids or []:
        sub = catalog.get(sub_id)
        if sub is not None and sub.id not in seen:
            picks.append(sub)
            seen.add(sub.id)
    similar = [ex for ex in catalog.values() if ex.id not in seen
               and ex.muscle_group == exercise.muscle_group
               and ex.movement_type == exercise.movement_type]
    if user is not None:
        rules = get_injury_rules()
        similar.sort(key=lambda ex: rank_key(ex, user))
        picks += similar
        # Stable: curated order kept within each group.
        picks.sort(key=lambda ex: not is_available(ex, user, rules))
    else:
        picks += similar
    return picks[:limit]


@dataclass(frozen=True)
class Media:
    kind: str | None          # "animation" (start + peak), "photo" or None
    start: str | None = None
    peak: str | None = None
    still: str | None = None  # thumbnail / single image


def _url(path: Path) -> str:
    stat = path.stat()
    # The version changes when the file does, so week-long caching is safe.
    return f"/static/exercises/{quote(path.name)}?v={stat.st_mtime_ns:x}{stat.st_size:x}"


def media(exercise_id: str, image_dir: Path) -> Media:
    images = find_images(exercise_id, image_dir)
    if images.kind is None:
        return Media(kind=None)
    if images.kind == "animation":
        return Media(kind="animation", start=_url(images.start), peak=_url(images.peak),
                     still=_url(images.start))
    return Media(kind="photo", still=_url(images.still))


def media_report(catalog: list[Exercise], image_dir: Path) -> dict[str, list[str]]:
    """Which exercises have both frames (animation), one image, or none."""
    report: dict[str, list[str]] = {"both": [], "one": [], "none": []}
    for ex in catalog:
        kind = find_images(ex.id, image_dir).kind
        report["both" if kind == "animation" else "one" if kind == "photo" else "none"].append(ex.id)
    return report
