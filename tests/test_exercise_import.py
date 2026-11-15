import json
from pathlib import Path

import pytest
from sqlalchemy import select

from database.models import Exercise
from services.exercise_import import (
    EXERCISES_FILE,
    ExerciseDataError,
    import_exercises,
    load_exercises_file,
    load_injury_rules,
    validate_exercises,
)


def make(ex_id, subs=(), **overrides):
    entry = {
        "id": ex_id, "name": ex_id.title(), "muscle_group": "chest", "equipment": "dumbbell",
        "difficulty": "beginner", "movement_type": "compound", "home_friendly": True,
        "substitute_ids": list(subs),
    }
    entry.update(overrides)
    return entry


def test_real_file_is_valid():
    records = load_exercises_file()
    assert len(records) == 87
    load_injury_rules({r["id"] for r in records})  # raises if an ID is unknown


@pytest.mark.parametrize("records,expected", [
    ([make("a", ["missing"])], "substitute 'missing' does not exist"),
    ([make("a"), make("a")], "duplicate id"),
    ([make("a", ["a"])], "lists itself"),
    ([make("a", difficulty="expert")], "difficulty must be"),
    ([make("a", movement_type="cardio")], "movement_type must be"),
    ([make("Bad ID")], "lowercase-with-dashes"),
    ([{k: v for k, v in make("a").items() if k != "equipment"}], "missing field 'equipment'"),
    ([make("a", home_friendly="yes")], "'home_friendly' must be bool"),
    ([make("a", ["b", "b"]), make("b")], "duplicate substitute"),
    ({"not": "a list"}, "JSON list"),
])
def test_validation_errors(records, expected):
    with pytest.raises(ExerciseDataError) as error:
        validate_exercises(records)
    assert any(expected in p for p in error.value.problems), error.value.problems


def test_all_problems_reported_together():
    with pytest.raises(ExerciseDataError) as error:
        validate_exercises([make("a", ["x"]), make("b", ["y"], difficulty="hard")])
    assert len(error.value.problems) == 3


def test_injury_rules_reject_unknown_ids(tmp_path: Path):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"knee": ["squat", "nope"], "_comment": "ignored"}))
    with pytest.raises(ExerciseDataError):
        load_injury_rules({"squat"}, path)
    path.write_text(json.dumps({"elbow": ["squat"]}))
    with pytest.raises(ExerciseDataError):
        load_injury_rules({"squat"}, path)


async def test_import_upserts_keeps_form_tips_and_deactivates(session_factory):
    records = json.loads(EXERCISES_FILE.read_text())
    async with session_factory() as session:
        report = await import_exercises(session, records)
        assert report.created == 87

        # Tips written straight into the database survive a re-import...
        bench = await session.get(Exercise, "bench-press")
        bench.form_tips = "Feet planted, shoulder blades back."
        await session.commit()

        changed = [dict(r) for r in records if r["id"] != "bird-dog"]
        changed[0]["name"] = "Bench Press (Barbell)"
        changed[1]["form_tips"] = "Elbows at 45°."   # ...and tips in the JSON are imported.
        report = await import_exercises(session, changed)
        assert (report.created, report.updated, report.deactivated) == (0, 2, ["bird-dog"])

    async with session_factory() as session:
        bench = await session.get(Exercise, "bench-press")
        assert bench.name == "Bench Press (Barbell)"
        assert bench.form_tips == "Feet planted, shoulder blades back."
        assert (await session.get(Exercise, "db-bench-press")).form_tips == "Elbows at 45°."
        assert (await session.get(Exercise, "bird-dog")).active is False
        order = [e.id for e in await session.scalars(select(Exercise).order_by(Exercise.sort_order))]
        assert order[:2] == ["bench-press", "db-bench-press"]
