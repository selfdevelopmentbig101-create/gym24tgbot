"""Stage 4 API: programs, split editor, substitutes, energy warnings, calendar."""
from datetime import datetime, timedelta, timezone

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import api.main as api_main
from database.models import WorkoutSession
from services import users
from services.exercise_import import import_exercises, load_exercises_file
from tests.test_api import TOKEN, auth, sign_init_data
from tests.test_api_profile import ANSWERS

BOB = {"id": 7201, "first_name": "Bob", "language_code": "en"}
H = auth(sign_init_data(BOB))


@pytest_asyncio.fixture
async def client(session_factory, tmp_path):
    async with session_factory() as s:
        await import_exercises(s, load_exercises_file())
    app = api_main.create_app(session_factory=session_factory, bot_token=TOKEN,
                              exercise_images=tmp_path, admin_ids=set())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def call(client, method, path, body=None, status=200, **params):
    response = await client.request(method.upper(), path, json=body, params=params or None, headers=H)
    assert response.status_code == status, response.text
    return response.json() if response.content else None


async def set_profile(client, **changes):
    await client.post("/api/me/disclaimer", headers=H)
    response = await client.put("/api/profile", json={**ANSWERS, **changes}, headers=H)
    assert response.status_code == 200, response.text


def day_by_id(plan, day_id):
    return next(d for d in plan["days"] if d["id"] == day_id)


# ---------- current program ----------

async def test_plan_needs_a_profile(client):
    assert (await client.get("/api/plan")).status_code == 401
    response = await client.get("/api/plan", headers=H)
    assert response.status_code == 409 and response.json()["detail"] == "profile_required"


# ---------- onboarding preview ----------

async def test_split_preview_needs_no_profile(client):
    preview = await call(client, "post", "/api/plan/preview",
                         {"experience": "beginner", "equipment": "bodyweight", "injuries": [], "days": 4})
    assert preview["split"] == "upper_lower"
    assert len(preview["days"]) == 4
    assert [d["name_key"] for d in preview["days"]] == ["upper", "lower", "upper", "lower"]
    assert all(day["exercises"] for day in preview["days"])
    assert {"exercise_id", "name", "sets", "rep_min", "rep_max", "timed", "rest_seconds"} <= \
        set(preview["days"][0]["exercises"][0])


async def test_default_program_with_energy_and_volume(client):
    await set_profile(client)
    plan = await call(client, "get", "/api/plan")
    program = plan["program"]
    assert program["kind"] == "default" and program["status"] == "current"
    assert program["name"] is None and program["name_key"].startswith("split_")
    assert len(plan["days"]) == min(max(ANSWERS["training_days"], 2), 6)
    assert program["week"] == 1 and program["completed"] == 0 and program["percent"] == 0
    upcoming = program["upcoming"]
    assert upcoming["exercises"] == len(plan["days"][upcoming["index"]]["exercises"]) and upcoming["minutes"] >= 10
    for day in plan["days"]:
        assert day["exercises"] and 0 <= day["energy"]["energy_left"] <= 100
    assert plan["weekly_volume"] and {"muscle", "sets", "status"} <= set(plan["weekly_volume"][0])
    assert plan["limits"]["weekly_sets_high"] == 20
    assert program["details"]["focus"] == "hypertrophy" and program["details"]["rep_range"]


# ---------- split editor ----------

async def test_split_editor(client):
    await set_profile(client)
    plan = await call(client, "get", "/api/plan")
    day = plan["days"][0]

    # Rename and move the day.
    plan = await call(client, "patch", f"/api/plan/days/{day['id']}", {"title": "  Heavy day ", "position": 1})
    moved = day_by_id(plan, day["id"])
    assert moved["title"] == "Heavy day" and moved["index"] == 1
    plan = await call(client, "patch", f"/api/plan/days/{day['id']}", {"title": ""})
    assert day_by_id(plan, day["id"])["title"] is None              # back to the default name

    # Add an exercise from the library; adding it twice is refused.
    in_day = {e["exercise_id"] for e in moved["exercises"]}
    new_id = next(x for x in ("hammer-curl", "lateral-raise", "crunches", "leg-extension") if x not in in_day)
    plan = await call(client, "post", f"/api/plan/days/{day['id']}/exercises", {"exercise_id": new_id, "sets": 2})
    entry = next(e for e in day_by_id(plan, day["id"])["exercises"] if e["exercise_id"] == new_id)
    assert entry["sets"] == 2
    await call(client, "post", f"/api/plan/days/{day['id']}/exercises", {"exercise_id": new_id}, status=409)
    await call(client, "post", f"/api/plan/days/{day['id']}/exercises", {"exercise_id": "nope"}, status=404)

    # Change sets/reps and move it to the top; bad numbers are refused.
    plan = await call(client, "patch", f"/api/plan/exercises/{entry['id']}",
                      {"sets": 4, "rep_min": 8, "rep_max": 12, "position": 0})
    first = day_by_id(plan, day["id"])["exercises"][0]
    assert (first["id"], first["sets"], first["rep_min"], first["rep_max"]) == (entry["id"], 4, 8, 12)
    await call(client, "patch", f"/api/plan/exercises/{entry['id']}", {"rep_min": 12, "rep_max": 8}, status=422)
    await call(client, "patch", f"/api/plan/exercises/{entry['id']}", {"sets": 0}, status=422)

    # Remove it again.
    plan = await call(client, "delete", f"/api/plan/exercises/{entry['id']}")
    assert new_id not in {e["exercise_id"] for e in day_by_id(plan, day["id"])["exercises"]}

    # Add and remove a day; the last day can't be removed.
    count = len(plan["days"])
    plan = await call(client, "post", "/api/plan/days", {"title": "Extra"})
    assert len(plan["days"]) == count + 1 and plan["days"][-1]["title"] == "Extra"
    assert plan["days"][-1]["exercises"]                               # filled with defaults
    assert plan["program"]["workouts_per_week"] == count + 1
    plan = await call(client, "delete", f"/api/plan/days/{plan['days'][-1]['id']}")
    assert len(plan["days"]) == count


async def test_substitute_and_other_users_data(client):
    await set_profile(client)
    plan = await call(client, "get", "/api/plan")
    entry = plan["days"][0]["exercises"][0]
    response = await client.post(f"/api/plan/exercises/{entry['id']}/substitute", headers=H)
    assert response.status_code in (200, 409)
    if response.status_code == 200:
        swapped = day_by_id(response.json(), plan["days"][0]["id"])["exercises"]
        assert entry["exercise_id"] not in {e["exercise_id"] for e in swapped if e["id"] == entry["id"]}
    else:
        assert response.json()["detail"] == "no_substitute"

    # Another user can't touch Bob's plan: ids are checked against the logged-in user.
    eve = auth(sign_init_data({"id": 7202, "first_name": "Eve", "language_code": "en"}))
    await client.post("/api/me/disclaimer", headers=eve)
    await client.put("/api/profile", json=ANSWERS, headers=eve)
    response = await client.delete(f"/api/plan/exercises/{entry['id']}", headers=eve)
    assert response.status_code == 404


async def test_energy_warning_when_a_day_is_too_big(client):
    await set_profile(client)
    plan = await call(client, "get", "/api/plan")
    day = plan["days"][0]
    in_day = {e["exercise_id"] for e in day["exercises"]}
    library = (await call(client, "get", "/api/exercises"))["items"]
    extra = [i["id"] for i in library if i["id"] not in in_day and i["id"] != "plank-main"]
    for exercise_id in extra[:12 - len(in_day)]:
        plan = await call(client, "post", f"/api/plan/days/{day['id']}/exercises", {"exercise_id": exercise_id})
    big = day_by_id(plan, day["id"])
    assert "too_many_exercises" in big["energy"]["warnings"] and big["energy"]["demanding"]
    # A 13th exercise is refused (MAX_EXERCISES_PER_DAY).
    await call(client, "post", f"/api/plan/days/{day['id']}/exercises", {"exercise_id": extra[12]}, status=409)
    energy = await call(client, "get", "/api/energy", day=day["id"])
    assert energy["session"]["warnings"] == big["energy"]["warnings"] and energy["weekly_volume"]


# ---------- programs ----------

async def test_create_activate_and_switch_back(client):
    await set_profile(client)
    plan = await call(client, "get", "/api/plan")
    default_id = plan["program"]["id"]
    first_day = plan["days"][0]
    await call(client, "patch", f"/api/plan/days/{first_day['id']}", {"title": "My day"})

    created = await call(client, "post", "/api/programs",
                         {"name": "Strong 4", "weeks": 6, "workouts_per_week": 4, "goal": "strength"}, status=201)
    assert created["status"] == "saved" and created["name"] == "Strong 4"
    tab = await call(client, "get", "/api/programs", tab="created")
    assert [p["id"] for p in tab["items"]] == [created["id"]]
    detail = await call(client, "get", f"/api/programs/{created['id']}")
    assert len(detail["days"]) == 4 and detail["details"]["focus"] == "strength"

    plan = await call(client, "post", f"/api/programs/{created['id']}/activate")
    assert plan["program"]["id"] == created["id"] and len(plan["days"]) == 4
    assert plan["program"]["weeks"] == 6 and plan["program"]["goal"] == "strength"
    saved = await call(client, "get", "/api/programs", tab="created")
    assert default_id in {p["id"] for p in saved["items"]}

    # Switching back restores the old days, including the renamed one.
    plan = await call(client, "post", f"/api/programs/{default_id}/activate")
    assert plan["program"]["id"] == default_id and plan["days"][0]["title"] == "My day"

    # Rename; the current program can't be deleted, a saved one can.
    renamed = await call(client, "patch", f"/api/programs/{created['id']}", {"name": "Power"})
    assert renamed["name"] == "Power"
    await call(client, "delete", f"/api/programs/{default_id}", status=409)
    await call(client, "delete", f"/api/programs/{created['id']}", status=204)
    await call(client, "get", f"/api/programs/{created['id']}", status=404)
    await call(client, "post", "/api/programs", {"name": "", "workouts_per_week": 3}, status=422)


async def test_available_programs_and_reset(client):
    await set_profile(client)
    available = await call(client, "get", "/api/programs", tab="available")
    assert "ppl_6" in {t["key"] for t in available["items"]}
    plan = await call(client, "post", "/api/programs/templates/ppl_6/start")
    assert len(plan["days"]) == 6 and plan["program"]["kind"] == "template"
    assert plan["program"]["name_key"] == "template_ppl_6"
    current = await call(client, "get", "/api/programs", tab="current")
    assert len(current["items"]) == 1
    await call(client, "post", "/api/programs/templates/nope/start", status=404)

    # Reset to default after removing a day.
    plan = await call(client, "delete", f"/api/plan/days/{plan['days'][-1]['id']}")
    assert len(plan["days"]) == 5
    plan = await call(client, "post", f"/api/programs/{plan['program']['id']}/reset")
    assert len(plan["days"]) == 5          # the program now has 5 days; reset refills them
    assert all(d["title"] is None for d in plan["days"])


# ---------- calendar ----------

async def test_calendar_marks_done_and_progress(client, session_factory):
    await set_profile(client)
    await call(client, "get", "/api/plan")
    now = datetime.now(timezone.utc)
    async with session_factory() as s:
        user = await users.get_or_create_user(s, BOB["id"])
        s.add(WorkoutSession(user_id=user.id, day_index=0, name_key="full_body", suffix="A", items=[],
                             started_at=now - timedelta(minutes=50), finished_at=now))
        await s.commit()

    today = now.date()
    calendar = await call(client, "get", "/api/calendar", month=today.strftime("%Y-%m"))
    by_date = {d["date"]: d["status"] for d in calendar["days"]}
    assert by_date[today.isoformat()] == "done" and calendar["counts"]["done"] == 1
    assert set(by_date.values()) <= {"done", "planned", "missed", "rest", "none"}
    await call(client, "get", "/api/calendar", month="2026-13", status=422)

    plan = await call(client, "get", "/api/plan")
    assert plan["program"]["completed"] == 1 and plan["program"]["upcoming"]["in_days"] >= 1
    assert plan["program"]["upcoming"]["index"] == 1 % len(plan["days"])   # the day after day 0
