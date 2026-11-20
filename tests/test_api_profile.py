"""Stage 2 API: disclaimer, onboarding answers, targets (macros + goal date)."""
from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import api.main as api_main
from database.enums import Goal, Sex
from services import plans, users
from services.exercise_import import import_exercises, load_exercises_file
from services.nutrition import calculate_targets, estimate_goal_date, split_fat_carbs
from tests.test_api import TOKEN, auth, sign_init_data

ALICE = {"id": 6001, "first_name": "Alice", "language_code": "ru"}
BOB = {"id": 6002, "first_name": "Bob", "language_code": "en"}

ANSWERS = {
    "goal": "lean_bulk", "age": 27, "sex": "male", "height_cm": 180, "weight_kg": 75,
    "experience": "beginner", "training_days": 3, "equipment": "full_gym",
    "injuries": ["knee"], "diet": "none", "target_weight_kg": 80,
}


@pytest_asyncio.fixture
async def client(session_factory):
    async with session_factory() as s:
        await import_exercises(s, load_exercises_file())
    sent = []

    async def notifier(telegram_id, lang):
        sent.append((telegram_id, lang))

    app = api_main.create_app(session_factory=session_factory, bot_token=TOKEN, notifier=notifier)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        c.sent, c.session_factory = sent, session_factory
        yield c


def as_user(user):
    return auth(sign_init_data(user))


async def onboarded(client, user=ALICE, **changes):
    assert (await client.post("/api/me/disclaimer", headers=as_user(user))).status_code == 204
    response = await client.put("/api/profile", json={**ANSWERS, **changes}, headers=as_user(user))
    assert response.status_code == 200, response.text
    return response.json()


# ---------- calculator ----------

def test_macros_add_up_to_calories():
    t = calculate_targets(weight_kg=75, height_cm=180, age=27, sex=Sex.MALE,
                          training_days=3, goal=Goal.LEAN_BULK)
    kcal = t.protein_g * 4 + t.carbs_g * 4 + t.fat_g * 9
    assert abs(kcal - t.calories) <= 40          # rounding to 5 g
    assert t.fat_g >= 0.6 * 75 and t.carbs_g > 0


def test_fat_floor_and_no_negative_carbs():
    fat, carbs = split_fat_carbs(1500, 300, 120)  # tiny budget, lots of protein
    assert fat == 70 and carbs == 0               # 0.6 g/kg * 120 kg = 72 -> 70


def test_goal_date_range():
    today = date(2026, 1, 1)
    goal = estimate_goal_date(75, 80, (0.08, 0.19), today)
    assert goal.to_gain_kg == 5
    assert goal.earliest_date < goal.estimated_date < goal.latest_date
    assert goal.earliest_date == today + timedelta(days=round(5 / 0.19 * 7))
    assert estimate_goal_date(75, None, (0.08, 0.19), today) is None
    # 74 < 75: the target itself says lose, even though the goal's rates are gains.
    loss = estimate_goal_date(75, 74, (0.08, 0.19), today)
    assert loss.to_gain_kg == -1 and loss.earliest_date > today
    assert estimate_goal_date(75, 80, (0.0, 0.0), today) is None     # recomposition


# ---------- HTTP ----------

async def test_config_has_the_same_limits_as_the_bot(client):
    rules = (await client.get("/api/config", headers=as_user(ALICE))).json()["profile_rules"]
    assert rules["age"] == [16, 80] and rules["training_days"] == [2, 6]
    assert rules["weight_kg"] == [35, 250] and rules["target_weight_kg"] == [35, 200]
    assert "lean_bulk" in rules["goals"] and "knee" in rules["injuries"]


async def test_config_offers_the_goal_cards_for_each_sex(client):
    rules = (await client.get("/api/config", headers=as_user(ALICE))).json()["profile_rules"]
    assert rules["goals_by_sex"]["male"] == ["bulk", "lean_bulk", "recomp"]
    assert rules["goals_by_sex"]["female"] == [
        "lose_weight", "gain_muscle", "improve_health", "get_in_shape"]


async def test_weight_loss_goal_accepts_a_lower_target(client):
    data = await onboarded(client, goal="lose_weight", sex="female", target_weight_kg=70)
    targets = data["targets"]
    assert data["profile"]["goal"] == "lose_weight" and data["profile"]["target_weight_kg"] == 70
    assert targets["profile_goal"] == "lose_weight"
    assert targets["surplus"] < 0 and targets["weekly_gain_kg"][1] < 0
    assert targets["goal"]["to_gain_kg"] == -5
    assert date.fromisoformat(targets["goal"]["estimated_date"]) > date.today()


async def test_goal_weight_can_point_either_way(client):
    # The goal is weight loss, but 80 > 75: the target itself means gain.
    data = await onboarded(client, goal="lose_weight", sex="female", target_weight_kg=80)
    assert data["profile"]["target_weight_kg"] == 80
    assert data["targets"]["goal"]["to_gain_kg"] == 5
    assert data["targets"]["surplus"] < 0   # the calorie goal still follows the chosen goal


async def test_onboarding_needs_login_and_disclaimer(client):
    assert (await client.put("/api/profile", json=ANSWERS)).status_code == 401
    response = await client.put("/api/profile", json=ANSWERS, headers=as_user(ALICE))
    assert response.status_code == 409 and response.json()["detail"] == "disclaimer_required"


async def test_full_onboarding_builds_plan_targets_and_tells_the_chat(client):
    data = await onboarded(client)
    assert data["plan_ready"] and data["plan_rebuilt"]
    assert data["profile"]["injuries"] == ["knee"] and data["profile"]["target_weight_kg"] == 80
    targets = data["targets"]
    assert targets["calories"] > targets["tdee"] and targets["carbs_g"] > 0
    assert targets["goal"]["to_gain_kg"] == 5
    assert date.fromisoformat(targets["goal"]["estimated_date"]) > date.today()
    assert client.sent == [(ALICE["id"], "ru")]   # chat gets the menu, in the user's language

    me = (await client.get("/api/me", headers=as_user(ALICE))).json()
    assert me["profile_complete"] and me["disclaimer_accepted"]
    assert (await client.get("/api/targets", headers=as_user(ALICE))).json() == targets
    # Same data the bot uses: the profile and the plan exist in the shared database.
    async with client.session_factory() as s:
        user = await users.get_user(s, ALICE["id"])
        assert user.profile.goal == Goal.LEAN_BULK
        assert await plans.get_plan(s, user) is not None

    # Saving again (e.g. re-running onboarding) doesn't message the chat twice.
    await onboarded(client)
    assert len(client.sent) == 1


@pytest.mark.parametrize("changes, field, error", [
    ({"age": 12}, "age", "err_age"),
    ({"height_cm": 300}, "height_cm", "err_height"),
    ({"weight_kg": 20}, "weight_kg", "err_weight"),
    ({"training_days": 7}, "training_days", "err_generic"),
    ({"target_weight_kg": 34}, "target_weight_kg", "err_target_weight"),     # below 35 kg
    ({"target_weight_kg": 201}, "target_weight_kg", "err_target_weight"),    # above 200 kg
    ({"goal": "recomp"}, "target_weight_kg", "err_target_weight"),          # recomp has no target
])
async def test_invalid_answers_are_rejected_with_a_field_and_key(client, changes, field, error):
    await client.post("/api/me/disclaimer", headers=as_user(ALICE))
    response = await client.put("/api/profile", json={**ANSWERS, **changes}, headers=as_user(ALICE))
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["field"] == field
    assert detail["error"] == error


async def test_unknown_choice_is_rejected(client):
    await client.post("/api/me/disclaimer", headers=as_user(ALICE))
    response = await client.put("/api/profile", json={**ANSWERS, "goal": "cut"}, headers=as_user(ALICE))
    assert response.status_code == 422


async def test_patch_changes_answers_and_rebuilds_plan_only_when_needed(client):
    first = await onboarded(client)
    h = as_user(ALICE)

    response = (await client.patch("/api/profile", json={"weight_kg": 77}, headers=h)).json()
    assert not response["plan_rebuilt"]
    assert response["targets"]["calories"] > first["targets"]["calories"]
    assert response["targets"]["goal"]["to_gain_kg"] == 3

    response = (await client.patch("/api/profile", json={"equipment": "bodyweight"}, headers=h)).json()
    assert response["plan_rebuilt"]

    response = (await client.patch("/api/profile", json={"target_weight_kg": None}, headers=h)).json()
    assert response["profile"]["target_weight_kg"] is None and response["targets"]["goal"] is None

    await client.patch("/api/profile", json={"target_weight_kg": 85}, headers=h)
    response = (await client.patch("/api/profile", json={"goal": "recomp"}, headers=h)).json()
    assert response["profile"]["target_weight_kg"] is None   # recomp: goal weight dropped
    assert response["targets"]["surplus"] == 0 or response["targets"]["goal"] is None

    bad = await client.patch("/api/profile", json={"age": None}, headers=h)
    assert bad.status_code == 422


async def test_patch_to_weight_loss_keeps_a_target_above_current(client):
    await onboarded(client)   # lean bulk, current 75, goal weight 80
    h = as_user(ALICE)

    response = (await client.patch("/api/profile", json={"goal": "lose_weight"}, headers=h)).json()
    assert response["profile"]["target_weight_kg"] == 80   # allowed: target says gain
    assert response["targets"]["surplus"] < 0              # calories still follow the goal
    assert response["targets"]["goal"]["to_gain_kg"] == 5

    response = (await client.patch("/api/profile", json={"target_weight_kg": 70}, headers=h)).json()
    assert response["profile"]["target_weight_kg"] == 70
    assert response["targets"]["goal"]["to_gain_kg"] == -5


async def test_users_only_see_their_own_profile(client):
    await onboarded(client)
    for path in ("/api/profile", "/api/targets"):
        response = await client.get(path, headers=as_user(BOB))
        assert response.status_code == 404 and response.json()["detail"] == "no_profile"
    assert (await client.patch("/api/profile", json={"age": 30}, headers=as_user(BOB))).status_code == 404
