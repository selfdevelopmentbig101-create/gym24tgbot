"""Stage 6: levels and XP rules, character mood, level/achievements API, deleting your data."""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import api.main as api_main
from services import levels
from services import xp_config as cfg
from services.exercise_import import import_exercises, load_exercises_file
from tests.test_api import TOKEN, auth, sign_init_data
from tests.test_api_profile import ANSWERS

ELLA = {"id": 7401, "first_name": "Ella", "language_code": "en"}
H = auth(sign_init_data(ELLA))


# ---------- pure rules ----------

def test_levels_and_thresholds():
    assert levels.make_level(0).key == "rookie"
    second = cfg.LEVELS[1][1]
    assert levels.make_level(second - 1).index == 0 and levels.make_level(second).index == 1
    top = levels.make_level(cfg.LEVELS[-1][1] + 5000)
    assert top.key == "pro" and top.next_xp is None and top.to_next == 0 and top.progress == 100
    mid = levels.make_level(second + (cfg.LEVELS[2][1] - second) // 2)
    assert mid.progress == 50 and mid.to_next == cfg.LEVELS[2][1] - mid.xp


def test_earned_xp_starts_everyone_at_rookie():
    assert levels.make_level(0).key == "rookie" and levels.make_level(0).index == 0
    assert levels.earned_xp(2, 1, 1) == 2 * cfg.XP_PER_WORKOUT + cfg.XP_PER_PR + cfg.XP_PER_GOAL_WEEK


def test_energy_recovers_and_mood():
    assert levels.recovered(20, 0) == 20 and levels.recovered(20, cfg.RECOVERY_HOURS) == 100
    assert levels.mood_for(90, 1, False, False) == "celebrating"
    assert levels.mood_for(90, cfg.CELEBRATE_HOURS + 1, True, False) == "celebrating"   # PR: longer
    assert levels.mood_for(10, None, False, True) == "tired"
    assert levels.mood_for(90, 48, False, False) == "rested"


# ---------- API ----------

@pytest_asyncio.fixture
async def client(session_factory, tmp_path):
    async with session_factory() as s:
        await import_exercises(s, load_exercises_file())
    app = api_main.create_app(session_factory=session_factory, bot_token=TOKEN,
                              exercise_images=tmp_path, admin_ids=set())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def setup_profile(client):
    await client.post("/api/me/disclaimer", headers=H)
    response = await client.put("/api/profile", json=ANSWERS, headers=H)
    assert response.status_code == 200, response.text


async def test_new_profile_always_starts_at_rookie(client):
    """Experience only shapes the plan; it must never give free levels or XP."""
    for i, experience in enumerate(("beginner", "intermediate", "advanced")):
        headers = auth(sign_init_data({"id": 7500 + i, "first_name": "New", "language_code": "en"}))
        assert (await client.post("/api/me/disclaimer", headers=headers)).status_code == 204
        response = await client.put("/api/profile", json={**ANSWERS, "experience": experience}, headers=headers)
        assert response.status_code == 200, response.text
        view = (await client.get("/api/me/level", headers=headers)).json()
        assert view["level"]["xp"] == 0
        assert view["level"]["index"] == 0 and view["level"]["key"] == "rookie"


async def test_level_grows_after_a_workout(client):
    assert (await client.get("/api/me/level", headers=H)).status_code == 409   # no profile yet
    await setup_profile(client)
    before = (await client.get("/api/me/level", headers=H)).json()
    assert before["level"]["xp"] == 0
    assert before["level"]["index"] == 0 and before["level"]["key"] == "rookie"
    assert before["mood"] == "rested" and before["energy"] == 100

    ws = (await client.post("/api/workouts", json={"day_index": 0}, headers=H)).json()
    for _ in range(2):
        r = await client.post(f"/api/workouts/{ws['id']}/sets",
                              json={"index": 0, "weight_kg": 40, "reps": 10}, headers=H)
        assert r.status_code == 201, r.text
    during = (await client.get("/api/me/level", headers=H)).json()
    assert during["in_workout"] and during["energy"] < 100
    summary = (await client.post(f"/api/workouts/{ws['id']}/finish", headers=H)).json()
    assert summary["xp_gained"] >= cfg.XP_PER_WORKOUT and summary["level"]["xp"] > before["level"]["xp"]

    after = (await client.get("/api/me/level", headers=H)).json()
    assert after["level"]["xp"] - before["level"]["xp"] >= cfg.XP_PER_WORKOUT
    assert after["mood"] == "celebrating" and after["stats"]["workouts"] == 1

    ach = (await client.get("/api/achievements", headers=H)).json()
    first = next(a for a in ach["items"] if a["code"] == "first_workout")
    assert first["unlocked"] and first["unlocked_at"] and ach["unlocked"] >= 1
    assert ach["total"] == len(ach["items"])


async def test_delete_my_data(client):
    await setup_profile(client)
    await client.get("/api/plan", headers=H)                       # creates a program too
    bad = await client.request("DELETE", "/api/me", json={"confirm": "yes"}, headers=H)
    assert bad.status_code == 422
    ok = await client.request("DELETE", "/api/me", json={"confirm": "DELETE"}, headers=H)
    assert ok.status_code == 204
    assert (await client.get("/api/profile", headers=H)).status_code == 404
    me = (await client.get("/api/me", headers=H)).json()
    assert me["profile_complete"] is False and me["language"] is None
