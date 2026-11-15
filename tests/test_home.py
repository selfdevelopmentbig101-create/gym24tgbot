"""Stage 7: Home tab data (greeting, next workout, this week, nutrition, weight)."""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import api.main as api_main
from services.exercise_import import import_exercises, load_exercises_file
from services.home import part_of_day
from tests.test_api import TOKEN, auth, sign_init_data
from tests.test_api_profile import ANSWERS

FINN = {"id": 7501, "first_name": "Finn", "language_code": "en"}
H = auth(sign_init_data(FINN))


def test_part_of_day():
    assert [part_of_day(h) for h in (6, 13, 19, 23, 3)] == ["morning", "afternoon", "evening", "night", "night"]


@pytest_asyncio.fixture
async def client(session_factory, tmp_path):
    async with session_factory() as s:
        await import_exercises(s, load_exercises_file())
    app = api_main.create_app(session_factory=session_factory, bot_token=TOKEN,
                              exercise_images=tmp_path, admin_ids=set())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_home(client):
    assert (await client.get("/api/home", headers=H)).status_code == 409   # no profile yet
    await client.post("/api/me/disclaimer", headers=H)
    assert (await client.put("/api/profile", json=ANSWERS, headers=H)).status_code == 200

    home = (await client.get("/api/home", headers=H)).json()
    assert home["part_of_day"] in {"morning", "afternoon", "evening", "night"}
    assert len(home["week"]["days"]) == 7 and sum(d["today"] for d in home["week"]["days"]) == 1
    assert home["week"]["done"] == 0 and home["active"] is None
    nxt = home["next_workout"]
    assert nxt["index"] == 0 and nxt["exercises"] > 0 and nxt["minutes"] > 0 and nxt["names"]
    assert home["nutrition"]["calories_target"] > 0 and home["nutrition"]["calories"] == 0
    assert home["weight"]["kg"] == ANSWERS["weight_kg"] and home["weight"]["logged_at"] is None

    ws = (await client.post("/api/workouts", json={"day_index": 0}, headers=H)).json()
    during = (await client.get("/api/home", headers=H)).json()
    assert during["active"]["id"] == ws["id"] and during["active"]["done_sets"] == 0
    r = await client.post(f"/api/workouts/{ws['id']}/sets", json={"index": 0, "weight_kg": 50, "reps": 8}, headers=H)
    assert r.status_code == 201
    await client.post(f"/api/workouts/{ws['id']}/finish", headers=H)

    after = (await client.get("/api/home", headers=H)).json()
    assert after["active"] is None and after["week"]["done"] == 1
    assert after["week"]["sets"] == 1 and after["week"]["volume_kg"] == 400
    assert any(d["trained"] and d["today"] for d in after["week"]["days"])
    train = (await client.get("/api/train", headers=H)).json()
    assert after["next_workout"]["index"] == train["next_index"] != 0 or len(train["days"]) == 1
