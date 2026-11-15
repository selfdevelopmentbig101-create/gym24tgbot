"""
Load data/core_exercises.json into the `exercises` table.

- Every problem in the file is collected and reported at once, so you can fix
  them all in one go.
- Re-running is safe: existing rows are updated, new ones added.
- secondary_muscles: from data/secondary_muscles.json (or the entry itself), validated.
- form_tips: if an entry has a "form_tips" key, it's imported; otherwise the
  value already in the database is kept (so tips added in the DB aren't lost).
- Exercises removed from the JSON are marked inactive, not deleted, because
  plans and workout logs may still point to them.
"""
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.enums import Injury
from database.models import Exercise

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EXERCISES_FILE = DATA_DIR / "core_exercises.json"
INJURY_FILE = DATA_DIR / "injury_exclusions.json"
SECONDARY_MUSCLES_FILE = DATA_DIR / "secondary_muscles.json"

DIFFICULTIES = ("beginner", "intermediate", "advanced")
MOVEMENT_TYPES = ("compound", "isolation")
REQUIRED_FIELDS = {
    "id": str,
    "name": str,
    "muscle_group": str,
    "equipment": str,
    "difficulty": str,
    "movement_type": str,
    "home_friendly": bool,
    "substitute_ids": list,
}
# Lowercase letters, digits and dashes: safe as a file name and in button data.
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_ID_LENGTH = 40  # Telegram button data is limited to 64 bytes in total


class ExerciseDataError(ValueError):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__(f"{len(problems)} problem(s) in exercise data:\n- " + "\n- ".join(problems))


@dataclass
class ImportReport:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    deactivated: list[str] = field(default_factory=list)


def validate_exercises(records: object) -> list[dict]:
    """Check structure, types, allowed values, unique IDs and substitute IDs."""
    if not isinstance(records, list):
        raise ExerciseDataError(["The file must contain a JSON list of exercises."])

    problems: list[str] = []
    seen: set[str] = set()

    for index, entry in enumerate(records):
        where = f"entry #{index + 1}"
        if not isinstance(entry, dict):
            problems.append(f"{where}: must be an object")
            continue
        ex_id = entry.get("id")
        if isinstance(ex_id, str):
            where = f"'{ex_id}'"

        for name, expected in REQUIRED_FIELDS.items():
            if name not in entry:
                problems.append(f"{where}: missing field '{name}'")
            elif not isinstance(entry[name], expected):
                problems.append(f"{where}: '{name}' must be {expected.__name__}")

        if isinstance(ex_id, str):
            if not ID_PATTERN.match(ex_id) or len(ex_id) > MAX_ID_LENGTH:
                problems.append(f"{where}: id must be lowercase-with-dashes, max {MAX_ID_LENGTH} chars")
            if ex_id in seen:
                problems.append(f"{where}: duplicate id")
            seen.add(ex_id)
        if entry.get("difficulty") not in DIFFICULTIES:
            problems.append(f"{where}: difficulty must be one of {DIFFICULTIES}")
        if entry.get("movement_type") not in MOVEMENT_TYPES:
            problems.append(f"{where}: movement_type must be one of {MOVEMENT_TYPES}")
        tips = entry.get("form_tips")
        if tips is not None and not isinstance(tips, str):
            problems.append(f"{where}: form_tips must be text")

    # Second pass: substitutes, now that every ID is known.
    for entry in records:
        if not isinstance(entry, dict) or not isinstance(entry.get("substitute_ids"), list):
            continue
        ex_id = entry.get("id")
        subs = entry["substitute_ids"]
        for sub in subs:
            if sub not in seen:
                problems.append(f"'{ex_id}': substitute '{sub}' does not exist")
            elif sub == ex_id:
                problems.append(f"'{ex_id}': lists itself as a substitute")
        if len(set(map(str, subs))) != len(subs):
            problems.append(f"'{ex_id}': duplicate substitute IDs")

    if problems:
        raise ExerciseDataError(problems)
    return records


def load_exercises_file(path: Path = EXERCISES_FILE,
                        muscles_path: Path | None = None) -> list[dict]:
    """The validated exercise list, with secondary muscles merged in (if the file has none)."""
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ExerciseDataError([f"File not found: {path}"]) from None
    except json.JSONDecodeError as error:
        raise ExerciseDataError([f"Invalid JSON in {path.name}: {error}"]) from None
    records = validate_exercises(records)
    if muscles_path is None:
        muscles_path = path.parent / SECONDARY_MUSCLES_FILE.name
    secondary = load_secondary_muscles(records, muscles_path)
    for entry in records:
        entry.setdefault("secondary_muscles", secondary.get(entry["id"], []))
    return records


def load_secondary_muscles(records: list[dict], path: Path = SECONDARY_MUSCLES_FILE) -> dict[str, list[str]]:
    """exercise id -> secondary muscle groups. Keys starting with '_' are comments."""
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ExerciseDataError([f"Invalid JSON in {path.name}: {error}"]) from None
    primary = {entry["id"]: entry["muscle_group"] for entry in records}
    groups = set(primary.values())
    problems, result = [], {}
    for ex_id, muscles in raw.items():
        if ex_id.startswith("_"):
            continue
        if ex_id not in primary:
            problems.append(f"{path.name}: unknown exercise '{ex_id}'")
            continue
        if not isinstance(muscles, list) or not all(isinstance(m, str) for m in muscles):
            problems.append(f"{path.name}: '{ex_id}' must be a list of muscle groups")
            continue
        problems += [f"{path.name}: '{ex_id}' lists unknown muscle group '{m}'" for m in muscles if m not in groups]
        if primary[ex_id] in muscles:
            problems.append(f"{path.name}: '{ex_id}' lists its primary muscle as secondary")
        if len(set(muscles)) != len(muscles):
            problems.append(f"{path.name}: '{ex_id}' has duplicate muscles")
        result[ex_id] = muscles
    if problems:
        raise ExerciseDataError(problems)
    return result


def load_injury_rules(known_ids: set[str], path: Path = INJURY_FILE) -> dict[str, set[str]]:
    """injury code -> exercise IDs to avoid. Keys starting with '_' are comments."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    valid_injuries = {i.value for i in Injury}
    problems, rules = [], {}
    for injury, ids in raw.items():
        if injury.startswith("_"):
            continue
        if injury not in valid_injuries:
            problems.append(f"{path.name}: unknown injury '{injury}'")
            continue
        unknown = [i for i in ids if i not in known_ids]
        problems += [f"{path.name}: '{injury}' lists unknown exercise '{i}'" for i in unknown]
        rules[injury] = set(ids)
    if problems:
        raise ExerciseDataError(problems)
    return rules


async def import_exercises(session: AsyncSession, records: list[dict]) -> ImportReport:
    """Upsert validated records. Call validate_exercises/load_exercises_file first."""
    report = ImportReport()
    existing = {ex.id: ex for ex in await session.scalars(select(Exercise))}
    columns = [name for name in REQUIRED_FIELDS if name != "id"]

    for position, entry in enumerate(records):
        values = {name: entry[name] for name in columns}
        values["secondary_muscles"] = list(entry.get("secondary_muscles") or [])
        if "form_tips" in entry:
            values["form_tips"] = (entry["form_tips"] or "").strip() or None
        values["active"] = True
        values["sort_order"] = position

        exercise = existing.get(entry["id"])
        if exercise is None:
            session.add(Exercise(id=entry["id"], **values))
            report.created += 1
            continue
        changed = False
        for name, value in values.items():
            if getattr(exercise, name) != value:
                setattr(exercise, name, value)
                changed = True
        if changed:
            report.updated += 1
        else:
            report.unchanged += 1

    file_ids = {entry["id"] for entry in records}
    for ex_id, exercise in existing.items():
        if ex_id not in file_ids and exercise.active:
            exercise.active = False
            report.deactivated.append(ex_id)

    await session.commit()
    logger.info(
        "Exercises imported: %s new, %s updated, %s unchanged, %s deactivated",
        report.created, report.updated, report.unchanged, len(report.deactivated),
    )
    return report
