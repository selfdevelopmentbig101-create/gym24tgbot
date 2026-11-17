"""Guided workout screen: the workout view carries start/peak image URLs, and an unfinished
workout (with the sets already saved) comes back from /api/train, so the app can resume it."""
from urllib.parse import quote

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import api.main as api_main
from services.exercise_import import import_exercises, load_exercises_file
from tests.test_api import TOKEN, auth, sign_init_data
from tests.test_api_profile import ANSWERS

ERIN = {"id": 7311, "first_name": "Erin", "language_code": "en"}
H = auth(sign_init_data(ERIN))


@pytest_asyncio.fixture
async def env(session_factory, tmp_path):
    async with session_factory() as s:
        await import_exercises(s, load_exercises_file())
    app = api_main.create_app(session_factory=session_factory, bot_token=TOKEN,
                              exercise_images=tmp_path, admin_ids=set())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/me/disclaimer", headers=H)
        response = await c.put("/api/profile", json=ANSWERS, headers=H)
        assert response.status_code == 200, response.text
        yield c, tmp_path


async def call(client, method, path, body=None, status=200):
    response = await client.request(method.upper(), path, json=body, headers=H)
    assert response.status_code == status, response.text
    return response.json() if response.content else None


async def test_items_carry_start_peak_and_still_urls(env):
    client, images = env
    ws = await call(client, "post", "/api/workouts", {"day_index": 0}, status=201)
    first, second = ws["items"][0], ws["items"][1]

    # No image files yet: no media, and the app shows its placeholder.
    assert first["media"] == {"kind": None, "start": None, "peak": None, "still": None}
    assert first["image"] is None

    # Two frames -> an animation (the app crossfades start and peak).
    (images / f"{first['exercise_id']}-start.webp").write_bytes(b"start")
    (images / f"{first['exercise_id']}-peak.webp").write_bytes(b"peak")
    # One image -> a photo (shown as a still).
    (images / f"{second['exercise_id']}.webp").write_bytes(b"single")

    view = await call(client, "get", f"/api/workouts/{ws['id']}")
    media = view["items"][0]["media"]
    assert media["kind"] == "animation"
    assert media["start"].startswith(f"/static/exercises/{quote(first['exercise_id'])}-start.webp?v=")
    assert media["peak"].startswith(f"/static/exercises/{quote(first['exercise_id'])}-peak.webp?v=")
    assert media["still"] == media["start"] == view["items"][0]["image"]

    photo = view["items"][1]["media"]
    assert photo["kind"] == "photo" and photo["start"] is None and photo["peak"] is None
    assert photo["still"].startswith(f"/static/exercises/{quote(second['exercise_id'])}.webp?v=")

    # The same data comes with the active workout of the Train screen.
    active = (await call(client, "get", "/api/train"))["active"]
    assert active["items"][0]["media"]["kind"] == "animation"


async def test_unfinished_workout_resumes_with_saved_sets(env):
    client, _ = env
    ws = await call(client, "post", "/api/workouts", {"day_index": 0}, status=201)
    await call(client, "post", f"/api/workouts/{ws['id']}/sets",
               {"index": 0, "weight_kg": 40, "reps": 10}, status=201)

    # "Closing the Mini App" = nothing to do; opening it again reads the same state back.
    active = (await call(client, "get", "/api/train"))["active"]
    assert active["id"] == ws["id"]
    assert [s["reps"] for s in active["items"][0]["logged"]] == [10]
    assert active["done_sets"] == 1
    if ws["items"][0]["sets"] > 1:                 # still on the first exercise
        assert active["current_index"] == 0
