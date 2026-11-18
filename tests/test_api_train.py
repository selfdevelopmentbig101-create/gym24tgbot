"""Stage 5 API: workout-day screen, live logger (warm-ups, RPE, PRs, edits, supersets, notes), finish."""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import api.main as api_main
from services.exercise_import import import_exercises, load_exercises_file
from tests.test_api import TOKEN, auth, sign_init_data
from tests.test_api_profile import ANSWERS

CARA = {"id": 7301, "first_name": "Cara", "language_code": "en"}
H = auth(sign_init_data(CARA))


@pytest_asyncio.fixture
async def client(session_factory, tmp_path):
    async with session_factory() as s:
        await import_exercises(s, load_exercises_file())
    app = api_main.create_app(session_factory=session_factory, bot_token=TOKEN,
                              exercise_images=tmp_path, admin_ids=set())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/me/disclaimer", headers=H)
        response = await c.put("/api/profile", json=ANSWERS, headers=H)
        assert response.status_code == 200, response.text
        yield c


async def call(client, method, path, body=None, status=200, headers=H):
    response = await client.request(method.upper(), path, json=body, headers=headers)
    assert response.status_code == status, response.text
    return response.json() if response.content else None


async def log(client, ws_id, index, weight, reps, status=201, **extra):
    return await call(client, "post", f"/api/workouts/{ws_id}/sets",
                      {"index": index, "weight_kg": weight, "reps": reps, **extra}, status=status)


async def test_overview_and_start(client):
    overview = await call(client, "get", "/api/train")
    assert overview["active"] is None and overview["next_index"] == 0
    assert overview["days"] and overview["days"][0]["exercises"][0]["last"] == []

    ws = await call(client, "post", "/api/workouts", {"day_index": 0}, status=201)
    assert len(ws["items"]) == len(overview["days"][0]["exercises"])
    assert [i["status"] for i in ws["items"]][:2] == ["current", "upcoming"]
    assert ws["energy"]["left"] == 100 and ws["done_sets"] == 0

    # A second start is refused until the first is finished (or force=True).
    await call(client, "post", "/api/workouts", {"day_index": 1}, status=409)
    assert (await call(client, "get", "/api/train"))["active"]["id"] == ws["id"]
    forced = await call(client, "post", "/api/workouts", {"day_index": 0, "force": True}, status=201)
    assert forced["id"] != ws["id"]


async def test_logging_warmups_prs_and_finish(client):
    # Workout 1: 60 kg x 8 for every planned set of the first exercise.
    ws = await call(client, "post", "/api/workouts", {"day_index": 0}, status=201)
    first = ws["items"][0]
    result = await log(client, ws["id"], 0, 20, 10, warmup=True)
    assert result["set"]["warmup"] and not result["set"]["pr"]
    assert result["workout"]["energy"]["left"] == 100          # warm-ups cost no energy
    assert result["workout"]["items"][0]["status"] == "current"
    for _ in range(first["sets"]):
        result = await log(client, ws["id"], 0, 60, 8, rpe=8)
    view = result["workout"]
    assert view["items"][0]["status"] == "completed" and view["items"][1]["status"] == "current"
    assert view["energy"]["left"] < 100 and view["done_sets"] == first["sets"]
    assert not any(s["pr"] for s in view["items"][0]["logged"])  # first time is never a PR
    summary = await call(client, "post", f"/api/workouts/{ws['id']}/finish")
    assert summary["discarded"] is False and summary["total_sets"] == first["sets"]
    assert summary["exercises"][0]["next_time"]["kind"] in {"add_reps", "add_weight", "repeat"}
    assert (await call(client, "get", "/api/train"))["active"] is None
    await log(client, ws["id"], 0, 60, 8, status=409)            # finished: read-only

    # Workout 2: last time's numbers show; a heavy warm-up is ignored; 70 x 8 is a PR.
    ws2 = await call(client, "post", "/api/workouts", {"day_index": 0}, status=201)
    assert ws2["items"][0]["previous"][0] == {"weight_kg": 60, "reps": 8}
    assert ws2["items"][0]["suggestion"]["kind"]
    warm = await log(client, ws2["id"], 0, 100, 5, warmup=True)
    assert not warm["set"]["pr"]
    result = await log(client, ws2["id"], 0, 70, 8)
    assert result["set"]["pr"] and result["set"]["estimate"] > result["set"]["previous_best"]

    # Fix the set: 50 kg is no longer a PR. Then delete it.
    set_id = result["set"]["id"]
    view = await call(client, "patch", f"/api/workouts/{ws2['id']}/sets/{set_id}", {"weight_kg": 50, "rpe": None})
    edited = next(s for s in view["items"][0]["logged"] if s["id"] == set_id)
    assert edited["weight_kg"] == 50 and not edited["pr"] and edited["rpe"] is None
    view = await call(client, "delete", f"/api/workouts/{ws2['id']}/sets/{set_id}")
    assert set_id not in {s["id"] for s in view["items"][0]["logged"]}


async def test_bad_values_supersets_and_notes(client):
    ws = await call(client, "post", "/api/workouts", {"day_index": 0}, status=201)
    response = await client.post(f"/api/workouts/{ws['id']}/sets",
                                 json={"index": 0, "weight_kg": 60, "reps": 150}, headers=H)
    assert response.status_code == 422 and response.json()["detail"] == "err_set_reps"
    await log(client, ws["id"], 0, 60, 0, status=422)
    await log(client, ws["id"], 0, 60, 8, status=422, rpe=11)
    await log(client, ws["id"], 99, 60, 8, status=422)

    view = await call(client, "patch", f"/api/workouts/{ws['id']}/items/0", {"note": " Seat 4 ", "group": "A"})
    view = await call(client, "patch", f"/api/workouts/{ws['id']}/items/1", {"group": "A"})
    assert [i["label"] for i in view["items"][:2]] == ["A1", "A2"] and view["items"][0]["note"] == "Seat 4"
    view = await call(client, "patch", f"/api/workouts/{ws['id']}/items/0", {"group": None, "note": ""})
    assert view["items"][0]["label"] is None and view["items"][0]["note"] is None
    await call(client, "patch", f"/api/workouts/{ws['id']}/items/0", {"group": "Z"}, status=422)


async def test_substitute_discard_and_privacy(client):
    ws = await call(client, "post", "/api/workouts", {"day_index": 0}, status=201)
    response = await client.post(f"/api/workouts/{ws['id']}/items/0/substitute", headers=H)
    assert response.status_code in (200, 409)
    await log(client, ws["id"], 0, 40, 10)
    response = await client.post(f"/api/workouts/{ws['id']}/items/0/substitute", headers=H)
    assert response.status_code == 409 and response.json()["detail"] == "swap_after_sets"

    # Another user can't see or change this workout.
    dan = auth(sign_init_data({"id": 7302, "first_name": "Dan", "language_code": "en"}))
    await call(client, "get", f"/api/workouts/{ws['id']}", status=404, headers=dan)
    await call(client, "post", f"/api/workouts/{ws['id']}/finish", status=404, headers=dan)

    # A workout with no sets is discarded when finished.
    empty = await call(client, "post", "/api/workouts", {"day_index": 1, "force": True}, status=201)
    assert await call(client, "post", f"/api/workouts/{empty['id']}/finish") == {"discarded": True}
    await call(client, "get", f"/api/workouts/{empty['id']}", status=404)


async def test_splits_choose_and_muscles(client):
    listed = await call(client, "get", "/api/splits")
    splits = listed["splits"]
    assert len(splits) >= 2 and listed["active_index"] == 0
    assert [s["active"] for s in splits].count(True) == 1 and splits[0]["active"]
    second = splits[1]
    assert second["muscles"] and second["energy"]["hard_sets"] > 0

    one = await call(client, "get", f"/api/splits/{second['id']}")
    assert one["id"] == second["id"] and not one["active"]
    await call(client, "get", "/api/splits/999999", status=404)

    chosen = await call(client, "post", f"/api/splits/{second['id']}/activate")
    assert chosen["active_index"] == second["index"]
    assert (await call(client, "get", "/api/train"))["next_index"] == second["index"]

    # Finishing the chosen split hands back to the normal rotation (the day after it).
    ws = await call(client, "post", "/api/workouts", {"day_index": second["index"]}, status=201)
    await log(client, ws["id"], 0, 40, 8)
    await call(client, "post", f"/api/workouts/{ws['id']}/finish")
    after = await call(client, "get", "/api/splits")
    assert after["active_index"] == (second["index"] + 1) % len(splits)

    muscles = (await call(client, "get", "/api/exercises/muscles"))["items"]
    keys = [m["key"] for m in muscles]
    assert "chest" in keys and all(m["image"] == m["key"] + ".png" for m in muscles)
    chest = await call(client, "get", "/api/exercises/muscles/chest")
    assert chest["items"] and all(i["muscle_group"] == "chest" for i in chest["items"])
    assert len(chest["items"]) == next(m["count"] for m in muscles if m["key"] == "chest")
    assert (await call(client, "get", "/api/exercises/muscles/nope"))["items"] == []
