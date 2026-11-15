"""Stage 4 API: programs (current / created / available), days, exercises, calendar, load."""
from datetime import date, datetime, timedelta, timezone

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import api.main as api_main
from database.models import WorkoutSession
from services import plans, users
from services.exercise_import import import_exercises, load_exercises_file
from tests.test_api import TOKEN, auth, sign_init_data
from tests.test_api_profile import ANSWERS

ALICE = {"id": 8001, "first_name": "Alice", "language_code": "en"}
BOB = {"id": 8002, "first_name": "Bob", "language_code": "en"}
H, HB = auth(sign_init_data(ALICE)), auth(sign_init_data(BOB))


@pytest_asyncio.fixture
async def client(session_factory):
    async with session_factory() as s:
        await import_exercises(s, load_exercises_file())
    app = api_main.create_app(session_factory=session_factory, bot_token=TOKEN)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        c.session_factory = session_factory
        for headers in (H, HB):
            await c.post("/api/me/disclaimer", headers=headers)
            assert (await c.put("/api/profile", json=ANSWERS, headers=headers)).status_code == 200
        yield c


async def call(client, method, path, status=200, headers=H, **kwargs):
    response = await client.request(method, path, headers=headers, **kwargs)
    assert response.status_code == status, response.text
    return response.json() if response.content else None


async def test_onboarding_plan_is_the_current_program(client):
    data = await call(client, "GET", "/api/programs")
    current = data["current"]
    assert current["kind"] == "template" and current["template_days"] == 3 and current["is_current"]
    assert current["workouts_per_week"] == 3 and current["week"] == 1 and current["completed"] == 0
    assert current["total"] == 24 and current["next_day_index"] == 0
    assert current["started_on"] == date.today().isoformat()
    assert data["created"] == []
    assert [t["days"] for t in data["available"]] == [2, 3, 4, 5, 6]
    assert [t["recommended"] for t in data["available"]] == [False, True, False, False, False]


async def test_create_custom_program_fill_it_and_activate(client):
    p = await call(client, "POST", "/api/programs", 201,
                   json={"name": "  My   split ", "weeks": 6, "workouts_per_week": 2, "goal": "strength"})
    assert p["name"] == "My split" and p["kind"] == "custom" and not p["is_current"]
    assert [d["name_key"] + d["suffix"] for d in p["days"]] == ["custom1", "custom2"]

    # Empty programs can't be activated.
    assert (await call(client, "POST", f"/api/programs/{p['id']}/activate", 409))["detail"] == "program_empty"

    day = p["days"][0]["id"]
    d = await call(client, "POST", f"/api/days/{day}/exercises", 201, json={"exercise_id": "bench-press"})
    item = d["exercises"][0]
    assert (item["sets"], item["rep_min"], item["rep_max"], item["rest_seconds"]) == (4, 4, 6, 180)  # strength
    await call(client, "POST", f"/api/days/{day}/exercises", 409, json={"exercise_id": "bench-press"})
    await call(client, "POST", f"/api/days/{day}/exercises", 404, json={"exercise_id": "nope"})
    d = await call(client, "POST", f"/api/days/{day}/exercises", 201, json={"exercise_id": "lateral-raise"})

    # Edit sets/reps, reorder, validation.
    second = d["exercises"][1]["id"]
    d = await call(client, "PATCH", f"/api/days/{day}/exercises/{second}",
                   json={"sets": 5, "rep_min": 12, "rep_max": 15, "position": 0})
    assert d["exercises"][0]["id"] == second and d["exercises"][0]["sets"] == 5
    for bad in ({"sets": 0}, {"rep_min": 20, "rep_max": 10}, {"rest_seconds": 9999}, {"position": 5}):
        await call(client, "PATCH", f"/api/days/{day}/exercises/{second}", 422, json=bad)

    # Activate: the bot's current plan is now this program; the old one is saved.
    p = await call(client, "POST", f"/api/programs/{p['id']}/activate")
    assert p["is_current"] and p["week"] == 1
    data = await call(client, "GET", "/api/programs")
    assert data["current"]["id"] == p["id"] and len(data["created"]) == 1
    async with client.session_factory() as s:
        current = await plans.get_plan(s, await users.get_user(s, ALICE["id"]))
        assert current.id == p["id"] and current.days[0].exercises[0].exercise_id == "lateral-raise"

    # The current program can't be deleted; the saved one can.
    await call(client, "DELETE", f"/api/programs/{p['id']}", 409)
    await call(client, "DELETE", f"/api/programs/{data['created'][0]['id']}", 204)


async def test_days_add_rename_reorder_delete(client):
    p = (await call(client, "GET", "/api/programs"))["current"]
    pid = p["id"]
    p = await call(client, "POST", f"/api/programs/{pid}/days", 201, json={"name": "Arms <b>&</b> abs"})
    new = p["days"][-1]
    assert new["name"] == "Arms <b>&</b> abs" and new["name_key"] == "custom" and p["edited"]
    p = await call(client, "PATCH", f"/api/programs/{pid}/days/{new['id']}", json={"position": 0})
    assert p["days"][0]["id"] == new["id"] and [d["index"] for d in p["days"]] == [0, 1, 2, 3]
    p = await call(client, "PATCH", f"/api/programs/{pid}/days/{new['id']}", json={"name": "Arms"})
    assert p["days"][0]["name"] == "Arms"
    await call(client, "PATCH", f"/api/programs/{pid}/days/{new['id']}", 422, json={"name": "   "})
    await call(client, "PATCH", f"/api/programs/{pid}/days/{new['id']}", 422, json={"name": "x" * 31})
    p = await call(client, "DELETE", f"/api/programs/{pid}/days/{new['id']}")
    assert len(p["days"]) == 3
    for _ in range(4):
        await call(client, "POST", f"/api/programs/{pid}/days", 201, json={})
    assert (await call(client, "POST", f"/api/programs/{pid}/days", 409, json={}))["detail"] == "too_many_days"


async def test_edited_programs_survive_profile_changes_and_reset_restores(client):
    p = (await call(client, "GET", "/api/programs"))["current"]
    detail = await call(client, "GET", f"/api/programs/{p['id']}")
    day = detail["days"][0]
    await call(client, "DELETE", f"/api/days/{day['id']}/exercises/{day['exercises'][0]['id']}")

    # Profile change: the edited program is kept as the user left it.
    saved = await call(client, "PATCH", "/api/profile", json={"equipment": "bodyweight"})
    assert not saved["plan_rebuilt"]
    detail = await call(client, "GET", f"/api/programs/{p['id']}")
    assert len(detail["days"][0]["exercises"]) == len(day["exercises"]) - 1 and detail["edited"]

    # Reset: rebuilt from the template for the new equipment.
    detail = await call(client, "POST", f"/api/programs/{p['id']}/reset")
    assert not detail["edited"]
    assert all(i["exercise"]["fits"] for d in detail["days"] for i in d["exercises"])

    # Unedited again: the next profile change rebuilds it.
    saved = await call(client, "PATCH", "/api/profile", json={"equipment": "full_gym"})
    assert saved["plan_rebuilt"]


async def test_template_program_goal_change_and_substitute(client):
    p = await call(client, "POST", "/api/programs", 201,
                   json={"template_days": 6, "goal": "hypertrophy", "weeks": 4, "activate": True})
    assert p["split"] == "ppl" and p["workouts_per_week"] == 6 and p["is_current"] and p["name"] is None
    assert (await call(client, "GET", "/api/programs"))["current"]["id"] == p["id"]
    await call(client, "POST", "/api/programs", 404, json={"template_days": 9})

    # Goal change re-sets sets/reps for the new training style.
    p = await call(client, "PATCH", f"/api/programs/{p['id']}", json={"goal": "endurance", "name": "Summer"})
    assert p["goal"] == "endurance" and p["name"] == "Summer"
    assert all(i["rep_min"] >= 15 or i["timed"] for d in p["days"] for i in d["exercises"])
    p = await call(client, "PATCH", f"/api/programs/{p['id']}", json={"name": None})
    assert p["name"] is None
    await call(client, "PATCH", f"/api/programs/{p['id']}", 422, json={"weeks": 0})
    await call(client, "PATCH", f"/api/programs/{p['id']}", 422, json={"goal": "fun"})

    day = p["days"][0]
    item = day["exercises"][0]
    d = await call(client, "POST", f"/api/days/{day['id']}/exercises/{item['id']}/substitute", json={})
    swapped = d["exercises"][0]["exercise"]["id"]
    assert swapped != item["exercise"]["id"]
    d = await call(client, "POST", f"/api/days/{day['id']}/exercises/{item['id']}/substitute",
                   json={"exercise_id": "push-up"})
    assert d["exercises"][0]["exercise"]["id"] == "push-up"


async def test_programs_are_private(client):
    alice = (await call(client, "GET", "/api/programs"))["current"]
    detail = await call(client, "GET", f"/api/programs/{alice['id']}")
    day, item = detail["days"][0]["id"], detail["days"][0]["exercises"][0]["id"]
    for method, path, body in (
        ("GET", f"/api/programs/{alice['id']}", None),
        ("PATCH", f"/api/programs/{alice['id']}", {"name": "mine"}),
        ("DELETE", f"/api/programs/{alice['id']}", None),
        ("POST", f"/api/programs/{alice['id']}/activate", None),
        ("POST", f"/api/programs/{alice['id']}/days", {}),
        ("GET", f"/api/days/{day}", None),
        ("POST", f"/api/days/{day}/exercises", {"exercise_id": "push-up"}),
        ("PATCH", f"/api/days/{day}/exercises/{item}", {"sets": 2}),
        ("DELETE", f"/api/days/{day}/exercises/{item}", None),
        ("GET", f"/api/energy?day={day}", None),
    ):
        response = await client.request(method, path, headers=HB, json=body)
        assert response.status_code == 404, (method, path, response.text)
    assert (await call(client, "GET", f"/api/programs/{alice['id']}"))["name"] is None   # unchanged


async def test_calendar_marks_done_missed_and_planned(client):
    p = (await call(client, "GET", "/api/programs"))["current"]
    today = date.today()
    async with client.session_factory() as s:
        user = await users.get_user(s, ALICE["id"])
        program = await plans.get_plan(s, user)
        program.started_on = today - timedelta(days=21)
        noon = datetime.combine(today - timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc) \
            + timedelta(hours=12)
        s.add(WorkoutSession(user_id=user.id, day_index=0, name_key="full_body", suffix="A",
                             items=[], started_at=noon - timedelta(hours=1), finished_at=noon))
        await s.commit()
    data = await call(client, "GET", "/api/calendar?month=" + today.strftime("%Y-%m"))
    by_day = {d["date"]: d["status"] for d in data["days"]}
    assert by_day[(today - timedelta(days=1)).isoformat()] == "done"
    assert data["schedule"] == [0, 2, 4] and data["done"] >= 1
    for iso, status in by_day.items():
        day = date.fromisoformat(iso)
        if status == "missed":
            assert day < today and day.weekday() in (0, 2, 4)
        if status == "planned":
            assert day >= today and day.weekday() in (0, 2, 4)
    assert p["id"]
    await call(client, "GET", "/api/calendar?month=2026-13", 422)


async def test_energy_reports_load_and_warnings(client):
    p = await call(client, "POST", "/api/programs", 201,
                   json={"name": "Chest blast", "weeks": 4, "workouts_per_week": 1})
    day = p["days"][0]["id"]
    for ex in ("bench-press", "db-bench-press", "incline-bench-press", "incline-db-press", "cable-fly"):
        d = await call(client, "POST", f"/api/days/{day}/exercises", 201, json={"exercise_id": ex})
        await call(client, "PATCH", f"/api/days/{day}/exercises/{d['exercises'][-1]['id']}", json={"sets": 5})
    energy = await call(client, "GET", f"/api/energy?day={day}")
    assert energy["day"]["sets"] == 25 and energy["day"]["minutes"] > 60
    assert energy["day"]["muscles"][0] == {"muscle": "chest", "sets": 25}
    keys = {(w["key"], w.get("muscle")) for w in energy["warnings"]}
    assert ("muscle_session_high", "chest") in keys and ("weekly_high", "chest") in keys
    levels = {w["muscle"]: w["level"] for w in energy["week"]}
    assert levels["chest"] == "high" and levels["triceps"] in ("ok", "low", "high")
