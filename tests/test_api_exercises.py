"""Stage 3 API: exercise library search, filters, detail, substitutes, images, media report."""
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import api.main as api_main
from services.exercise_import import ExerciseDataError, load_exercises_file, load_secondary_muscles
from services.exercise_import import import_exercises
from tests.test_api import TOKEN, auth, sign_init_data
from tests.test_api_profile import ANSWERS

ALICE = {"id": 7001, "first_name": "Alice", "language_code": "en"}
ADMIN = {"id": 7999, "first_name": "Admin", "language_code": "en"}


@pytest_asyncio.fixture
async def client(session_factory, tmp_path):
    async with session_factory() as s:
        await import_exercises(s, load_exercises_file())
    images = tmp_path / "images"
    images.mkdir()
    # bench-press: start + peak (animation); plank-main: single image.
    for name in ("bench-press-start.webp", "bench-press-peak.webp", "plank-main.webp"):
        (images / name).write_bytes(b"RIFF0000WEBPVP8 fake")
    app = api_main.create_app(session_factory=session_factory, bot_token=TOKEN,
                              exercise_images=images, admin_ids={ADMIN["id"]})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


H = auth(sign_init_data(ALICE))


async def get(client, path, **params):
    response = await client.get(path, params=params, headers=H)
    assert response.status_code == 200, response.text
    return response.json()


async def set_profile(client, **changes):
    await client.post("/api/me/disclaimer", headers=H)
    response = await client.put("/api/profile", json={**ANSWERS, **changes}, headers=H)
    assert response.status_code == 200, response.text


# ---------- data ----------

def test_every_exercise_has_secondary_muscles_entry():
    records = load_exercises_file()
    assert all("secondary_muscles" in r for r in records)
    bench = next(r for r in records if r["id"] == "bench-press")
    assert bench["secondary_muscles"] == ["triceps", "shoulders"]


def test_secondary_muscles_are_validated(tmp_path):
    records = [{"id": "a", "muscle_group": "chest"}, {"id": "b", "muscle_group": "back"}]
    bad = tmp_path / "m.json"
    bad.write_text('{"a": ["chest"], "b": ["wings"], "zzz": []}', encoding="utf-8")
    with pytest.raises(ExerciseDataError) as error:
        load_secondary_muscles(records, bad)
    text = str(error.value)
    assert "primary muscle" in text and "wings" in text and "zzz" in text


# ---------- list and search ----------

async def test_list_needs_login_and_is_sorted(client):
    assert (await client.get("/api/exercises")).status_code == 401
    data = await get(client, "/api/exercises")
    names = [i["name"] for i in data["items"]]
    assert len(names) == data["total"] == 87 and names == sorted(names, key=str.casefold)
    assert data["muscles"][0] == "chest" and "ab wheel" in data["equipment"]
    assert data["difficulties"] == ["beginner", "intermediate", "advanced"]
    assert all(i["fits"] is None for i in data["items"])     # no profile yet


async def test_muscle_filter_includes_secondary(client):
    items = (await get(client, "/api/exercises", muscle="triceps"))["items"]
    ids = {i["id"] for i in items}
    assert "tricep-pushdown" in ids          # primary
    assert "bench-press" in ids              # secondary
    assert "squat" not in ids


@pytest.mark.parametrize("q, expected", [
    ("bench", "bench-press"),
    ("BENCH press", "bench-press"),
    ("грудь", "cable-fly"),                  # Russian muscle name
    ("hip thrust", "hip-thrust"),
    ("romanian-deadlift", "romanian-deadlift"),
])
async def test_search_by_name_or_muscle_in_any_language(client, q, expected):
    ids = [i["id"] for i in (await get(client, "/api/exercises", q=q))["items"]]
    assert expected in ids


async def test_other_filters(client):
    items = (await get(client, "/api/exercises", equipment="cable", difficulty="beginner"))["items"]
    assert items and all(i["equipment"] == "cable" and i["difficulty"] == "beginner" for i in items)
    items = (await get(client, "/api/exercises", home="true"))["items"]
    assert items and all(i["home_friendly"] for i in items)
    assert (await get(client, "/api/exercises", q="zzzz"))["items"] == []
    too_long = await client.get("/api/exercises", params={"q": "x" * 61}, headers=H)
    assert too_long.status_code == 422


async def test_fits_uses_the_same_rules_as_plans(client):
    await set_profile(client, equipment="bodyweight", injuries=["knee"], experience="beginner")
    data = await get(client, "/api/exercises")
    by_id = {i["id"]: i for i in data["items"]}
    assert by_id["push-up"]["fits"] is True
    assert by_id["bench-press"]["fits"] is False             # needs a gym
    assert by_id["split-squat"]["fits"] is False             # knee injury (injury_exclusions.json)
    fitting = (await get(client, "/api/exercises", fits="true"))["items"]
    assert fitting and all(i["fits"] for i in fitting) and len(fitting) < 87


# ---------- detail ----------

async def test_detail_with_animation_and_substitutes(client):
    d = await get(client, "/api/exercises/bench-press")
    assert d["name"] == "Barbell Bench Press" and d["secondary_muscles"] == ["triceps", "shoulders"]
    assert d["media"]["kind"] == "animation"
    assert d["media"]["start"].startswith("/static/exercises/bench-press-start.webp?v=")
    assert d["image"] == d["media"]["still"]
    subs = [s["id"] for s in d["substitutes"]]
    assert subs[:2] == ["db-bench-press", "push-up"]          # curated first
    assert "bench-press" not in subs and len(subs) <= 6
    assert d["reasons"] == [] and d["fits"] is None

    # The image URL is served (week-long cache).
    image = await client.get(d["media"]["start"])
    assert image.status_code == 200 and "max-age=604800" in image.headers["cache-control"]

    plank = await get(client, "/api/exercises/plank-main")
    assert plank["media"]["kind"] == "photo" and plank["media"]["start"] is None
    squat = await get(client, "/api/exercises/squat")
    assert squat["media"] == {"kind": None, "start": None, "peak": None, "still": None}


async def test_detail_explains_why_it_does_not_fit(client):
    await set_profile(client, equipment="home_dumbbells", injuries=["lower_back"], experience="beginner")
    d = await get(client, "/api/exercises/deadlift")
    assert d["fits"] is False and set(d["reasons"]) == {"equipment", "level", "injury"}
    # Substitutes that fit come first.
    fits = [s["fits"] for s in d["substitutes"]]
    assert fits == sorted(fits, reverse=True)


async def test_unknown_exercise(client):
    response = await client.get("/api/exercises/nope", headers=H)
    assert response.status_code == 404 and response.json()["detail"] == "no_exercise"


async def test_media_report_is_admin_only(client):
    assert (await client.get("/api/exercises/media-report", headers=H)).status_code == 403
    report = (await client.get("/api/exercises/media-report", headers=auth(sign_init_data(ADMIN)))).json()
    assert report["both"] == ["bench-press"] and report["one"] == ["plank-main"]
    assert len(report["none"]) == 85
