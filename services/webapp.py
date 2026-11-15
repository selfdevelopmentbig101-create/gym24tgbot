"""
Telegram Mini App without a server (no Telegram code).

The Mini App (webapp/index.html) is a static page, hosted for free with HTTPS
on GitHub Pages. Data flows like this:
  bot -> app:  the bot puts today's workout (and Premium progress data) into the
               page address after "#", base64url-encoded JSON (build_payload).
  app -> bot:  when you tap Finish, the page calls Telegram.WebApp.sendData();
               Telegram delivers it to the bot as a message (parse_result).
sendData only works when the app is opened from a reply-keyboard button,
which is how /app opens it.
"""
import base64
import json
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from database.models import Exercise, User, WorkoutPlan, utcnow
from services import adjust, body, premium, records, workouts
from services.exercise_media import find_images
from services.progression import SetResult, suggest

PAYLOAD_VERSION = 1
MAX_RESULT_SETS = 150
MAX_URL_LENGTH = 4000  # stay well under typical URL limits in Telegram clients


def encode(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode(text: str) -> dict:
    padded = text + "=" * (-len(text) % 4)
    return json.loads(base64.urlsafe_b64decode(padded).decode())


def _sets(results: list[SetResult]) -> list[list[float]]:
    return [[s.weight_kg, s.reps] for s in results]


def _image_files(exercise_id: str) -> list[str]:
    images = find_images(exercise_id)
    if images.kind == "animation":
        return [images.start.name, images.peak.name]
    if images.still is not None:
        return [images.still.name]
    return []


async def _exercise_entry(session: AsyncSession, user: User, entry, deload: bool) -> dict:
    exercise: Exercise = entry.exercise
    sets = adjust.deload_sets(entry.sets) if deload else entry.sets
    past = await workouts.history(session, user, exercise.id)
    previous = past[0] if past else []
    hint = suggest(previous, rep_min=entry.rep_min, rep_max=entry.rep_max, planned_sets=sets,
                   equipment=exercise.equipment, timed=entry.timed,
                   before_previous=past[1] if len(past) > 1 else None)
    weight = hint.weight_kg
    if deload and previous and not entry.timed:
        weight = adjust.deload_weight(max(s.weight_kg for s in previous))
    item = {"i": exercise.id, "n": exercise.name, "s": sets, "r": [entry.rep_min, entry.rep_max],
            "rs": entry.rest_seconds, "e": exercise.equipment, "p": _sets(previous),
            "g": [weight, hint.reps]}
    if entry.timed:
        item["t"] = 1
    files = _image_files(exercise.id)
    if files:
        item["im"] = files
    return item


async def _progress(session: AsyncSession, user: User) -> dict:
    now = utcnow()
    weights = await body.weights_since(session, user, now - timedelta(days=60))
    data = {"w": [[body.aware(w.logged_at).date().isoformat(), w.weight_kg] for w in weights[-30:]],
            "s": []}
    for exercise in (await records.logged_exercises(session, user, limit=3)):
        history = await records.e1rm_history(session, user, exercise.id, now - timedelta(days=90))
        if len(history) >= 2:
            data["s"].append({"n": exercise.name,
                              "h": [[when.date().isoformat(), round(v, 1)] for when, v in history[-12:]]})
    return data


async def build_payload(session: AsyncSession, user: User, plan: WorkoutPlan, day_index: int,
                        lang: str, day_label: str) -> dict:
    deload = await workouts.in_deload(session, user)
    day = plan.days[day_index]
    payload = {"v": PAYLOAD_VERSION, "l": lang, "d": day_index, "dn": day_label,
               "x": [await _exercise_entry(session, user, e, deload) for e in day.exercises]}
    if deload:
        payload["dl"] = 1
    if premium.has(user, "app_progress"):
        payload["pr"] = await _progress(session, user)
    return payload


def app_url(payload: dict) -> str:
    """The Mini App address with the data after '#'. Drops extras if it gets too long."""
    base = config.webapp_url.split("#")[0]
    url = f"{base}#d={encode(payload)}"
    if len(url) > MAX_URL_LENGTH and "pr" in payload:
        payload = {k: v for k, v in payload.items() if k != "pr"}
        url = f"{base}#d={encode(payload)}"
    if len(url) > MAX_URL_LENGTH:
        for item in payload["x"]:
            item.pop("im", None)
            item["p"] = item["p"][:3]
        url = f"{base}#d={encode(payload)}"
    return url


# ---------- Result from the app ----------

def parse_result(raw: str) -> tuple[int, list[tuple[str, float, int]]]:
    """
    Validate what the Mini App sent: {"v": 1, "d": day index, "s": [[exercise id, kg, reps], ...]}.
    Raises ValueError for anything unexpected.
    """
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("v") != PAYLOAD_VERSION:
        raise ValueError("unknown version")
    day = data.get("d")
    sets = data.get("s")
    if not isinstance(day, int) or not isinstance(sets, list) or not 0 < len(sets) <= MAX_RESULT_SETS:
        raise ValueError("bad shape")
    result = []
    for item in sets:
        if (not isinstance(item, list) or len(item) != 3 or not isinstance(item[0], str)
                or not isinstance(item[1], (int, float)) or not isinstance(item[2], int)):
            raise ValueError("bad set")
        result.append((item[0], float(item[1]), int(item[2])))
    return day, result


async def apply_result(session: AsyncSession, user: User, plan: WorkoutPlan, day_index: int,
                       sets: list[tuple[str, float, int]]):
    """Log the sets as a workout and finish it. Returns (summary, number of skipped sets)."""
    if not 0 <= day_index < len(plan.days):
        raise ValueError("plan changed")
    active = await workouts.get_active(session, user)
    ws = active if active is not None and active.day_index == day_index \
        else await workouts.start(session, user, plan, day_index)
    skipped = 0
    for exercise_id, weight, reps in sets:
        exercise = await session.get(Exercise, exercise_id)
        if exercise is None:
            skipped += 1
            continue
        ws.current_index = await workouts.add_exercise(session, user, ws, exercise)
        try:
            await workouts.log_set(session, user, ws, weight, reps)
        except workouts.LogError:
            skipped += 1
    return await workouts.finish(session, user, ws), skipped
