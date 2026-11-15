import json
from datetime import timedelta

import pytest

from database.enums import Diet
from database.models import MealLog
from services import foods, meals, reminders, users
from services.foods import FoodDataError, validate_foods
from services.validation import ValidationError

PROFILE = {
    "goal": "lean_bulk", "age": 27, "sex": "male", "height_cm": 180, "weight_kg": 80,
    "experience": "intermediate", "training_days": 4, "equipment": "full_gym",
    "injuries": [], "diet": "none",
}


async def make_user(session, telegram_id=1, diet="none"):
    user = await users.get_or_create_user(session, telegram_id)
    await users.save_profile(session, user, {**PROFILE, "diet": diet})
    return user


# ---------- Food list ----------

def test_real_food_list_is_valid_and_sensible():
    items = foods.all_foods()
    assert len(items) >= 40
    assert {f.category for f in items} == set(foods.CATEGORIES)
    for f in items:
        assert f.protein_g * 4 <= f.kcal + 10


def food(**overrides):
    entry = {"id": "x", "name": "X", "serving": "1", "kcal": 100, "protein_g": 10,
             "category": "protein", "diet": "vegan"}
    return {**entry, **overrides}


@pytest.mark.parametrize("entries,expected", [
    ([food(), food()], "duplicate id"),
    ([food(protein_g=50)], "exceeds total kcal"),
    ([food(category="drinks")], "category must be"),
    ([food(diet="keto")], "diet must be"),
    ([food(kcal=-1)], "kcal must be"),
    ([food(id="Bad Id")], "lowercase-with-dashes"),
    ([food(name="")], "'name' must be"),
])
def test_food_validation_errors(entries, expected):
    with pytest.raises(FoodDataError) as error:
        validate_foods({"foods": entries})
    assert any(expected in p for p in error.value.problems), error.value.problems


@pytest.mark.parametrize("diet,forbidden", [
    (Diet.VEGAN, {"vegetarian", "pescatarian", "meat"}),
    (Diet.VEGETARIAN, {"pescatarian", "meat"}),
    (Diet.PESCATARIAN, {"meat"}),
    (Diet.NONE, set()),
])
def test_diet_filter(diet, forbidden):
    allowed = foods.foods_for(diet)
    assert allowed and not {f.diet for f in allowed} & forbidden
    for idea in foods.protein_ideas(diet):
        assert idea.diet not in forbidden and idea.protein_g >= 15


# ---------- Manual parsing ----------

@pytest.mark.parametrize("text,expected", [
    ("650 40", (None, 650, 40.0)),
    ("650kcal 40g", (None, 650, 40.0)),
    ("chicken wrap 650 40", ("chicken wrap", 650, 40.0)),
    ("2 eggs 145 13", ("2 eggs", 145, 13.0)),
    ("shake 300 22,5", ("shake", 300, 22.5)),
])
def test_parse_manual(text, expected):
    assert meals.parse_manual(text) == expected


@pytest.mark.parametrize("text", ["650", "lots of food", "", "abc 40"])
def test_parse_manual_rejects(text):
    with pytest.raises(ValidationError):
        meals.parse_manual(text)


@pytest.mark.parametrize("kcal,protein,key", [
    (0, 0, "err_meal_kcal"), (5000, 10, "err_meal_kcal"),
    (500, 400, "err_meal_protein_range"), (100, 40, "err_meal_protein"),
])
def test_validate_entry(kcal, protein, key):
    with pytest.raises(ValidationError) as error:
        meals.validate_entry(kcal, protein)
    assert error.value.text_key == key


# ---------- Logging and totals ----------

async def test_log_servings_totals_and_delete(session_factory):
    async with session_factory() as s:
        user = await make_user(s)
        chicken = foods.get_food("chicken-breast")
        entry = await meals.log_food(s, user, chicken)
        await meals.set_servings(s, entry, 1.5)
        assert (entry.kcal, entry.protein_g) == (375, 69.0)
        manual = await meals.log_manual(s, user, "Wrap", 650, 40)
        with pytest.raises(ValidationError):
            await meals.set_servings(s, manual, 2)        # manual entries have no serving size

        today = await meals.local_today(s, user)
        summary = await meals.day_summary(s, user, today)
        assert (summary.kcal, summary.protein_g) == (1025, 109.0)
        assert summary.kcal_left == summary.targets.calories - 1025
        assert [e.name for e in summary.entries] == ["Chicken breast", "Wrap"]

        await meals.delete_entry(s, manual)
        assert (await meals.day_summary(s, user, today)).kcal == 375
        assert [f.id for f in await meals.recent_foods(s, user, "none")] == ["chicken-breast"]


async def test_week_average_ignores_today_and_empty_days(session_factory):
    async with session_factory() as s:
        user = await make_user(s)
        today = await meals.local_today(s, user)
        for days_ago, kcal, protein in ((1, 2800, 150), (3, 2400, 130), (9, 9999, 999)):
            s.add(MealLog(user_id=user.id, day=today - timedelta(days=days_ago), name="x",
                          kcal=kcal, protein_g=protein))
        s.add(MealLog(user_id=user.id, day=today, name="today", kcal=500, protein_g=10))
        await s.commit()
        assert await meals.week_average(s, user, today) == (2600, 140, 2)


async def test_day_follows_user_time_zone(session_factory):
    async with session_factory() as s:
        user = await make_user(s)
        await reminders.enable(s, user, "UTC+14:00")
        settings = await reminders.get_settings(s, user)
        entry = await meals.log_manual(s, user, None, 500, 30)
        assert entry.day == reminders.local_now(settings).date()


async def test_recent_foods_respect_diet_change(session_factory):
    async with session_factory() as s:
        user = await make_user(s)
        await meals.log_food(s, user, foods.get_food("tofu"))
        await meals.log_food(s, user, foods.get_food("salmon"))
        assert [f.id for f in await meals.recent_foods(s, user, "none")] == ["salmon", "tofu"]
        assert [f.id for f in await meals.recent_foods(s, user, "vegan")] == ["tofu"]


async def test_deleting_user_removes_meals(session_factory):
    from sqlalchemy import func, select
    async with session_factory() as s:
        user = await make_user(s, telegram_id=77)
        await meals.log_manual(s, user, None, 500, 30)
    async with session_factory() as s:
        await users.delete_user_data(s, 77)
        assert await s.scalar(select(func.count()).select_from(MealLog)) == 0


def test_foods_json_file_parses():
    raw = json.loads(foods.FOODS_FILE.read_text())
    assert len(validate_foods(raw)) == len(raw["foods"])
