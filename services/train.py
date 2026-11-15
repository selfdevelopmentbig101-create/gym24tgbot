"""
Train tab for the Mini App (Stage 5): what the workout-day screen and the live
logger show. Logging itself lives in services/workouts.py (shared with the bot),
so a workout started in the chat can be continued in the app and the other way round.
"""
import logging
from collections.abc import Callable
from datetime import timezone

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Exercise, SetLog, User, WorkoutSession
from services import achievements, energy, levels, plans, programs, reminders, workouts
from services import xp_config
from services import program_rules as rules
from services.exercises import load_catalog
from services.progression import Suggestion

logger = logging.getLogger(__name__)

ImageFor = Callable[[str], "str | None"]   # exercise id -> thumbnail URL


class TrainError(Exception):
    """Something the user asked for can't be done. `code` is a text key for the app."""

    def __init__(self, code: str, status: int = 409):
        super().__init__(code)
        self.code = code
        self.status = status


def _aware(moment):
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def hint_dict(hint: Suggestion | None) -> dict | None:
    """A progressive-overload suggestion (services/progression.py) for the app."""
    if hint is None:
        return None
    return {"kind": hint.kind, "weight_kg": hint.weight_kg, "reps": hint.reps, "params": dict(hint.params)}


def set_dict(entry: SetLog) -> dict:
    return {"id": entry.id, "set_number": entry.set_number, "weight_kg": entry.weight_kg,
            "reps": entry.reps, "rpe": entry.rpe, "warmup": bool(entry.warmup), "pr": bool(entry.pr)}


def superset_labels(items: list[dict]) -> list[str | None]:
    """A1, A2, B1... for exercises in a superset group; None for the others."""
    counts: dict[str, int] = {}
    labels = []
    for item in items:
        group = item.get("group")
        if group:
            counts[group] = counts.get(group, 0) + 1
            labels.append(f"{group}{counts[group]}")
        else:
            labels.append(None)
    return labels


async def _exercise(session: AsyncSession, catalog: dict[str, Exercise], exercise_id: str) -> Exercise:
    return catalog.get(exercise_id) or await session.get(Exercise, exercise_id)


def _block(exercise: Exercise, sets: int, timed: bool) -> energy.SetBlock:
    return energy.SetBlock(exercise.muscle_group, tuple(exercise.secondary_muscles or ()),
                           exercise.movement_type, sets, timed)


# ---------- workout-day screen ----------

async def overview(session: AsyncSession, user: User, image_for: ImageFor) -> dict:
    """The active workout (if any), and every day of the current program with last time's numbers."""
    if user.profile is None:
        raise TrainError("profile_required")
    active = await workouts.get_active(session, user)
    _program, plan = await programs.ensure_current(session, user)
    catalog = await load_catalog(session)
    days = []
    for day in sorted(plan.days, key=lambda d: d.day_index):
        exercises, blocks = [], []
        for entry in sorted(day.exercises, key=lambda e: e.position):
            ex = await _exercise(session, catalog, entry.exercise_id)
            past = await workouts.history(session, user, entry.exercise_id, limit=1)
            blocks.append(_block(ex, entry.sets, entry.timed))
            exercises.append({
                "exercise_id": ex.id, "name": ex.name, "muscle_group": ex.muscle_group,
                "equipment": ex.equipment, "image": image_for(ex.id), "sets": entry.sets, "rep_min": entry.rep_min,
                "rep_max": entry.rep_max, "timed": entry.timed, "rest_seconds": entry.rest_seconds,
                "last": [{"weight_kg": s.weight_kg, "reps": s.reps} for s in (past[0] if past else [])],
            })
        days.append({
            "id": day.id, "index": day.day_index, "name_key": day.name_key, "suffix": day.suffix,
            "title": day.title,
            "minutes": rules.estimate_minutes((e.sets, e.rep_max, e.timed, e.rest_seconds) for e in day.exercises),
            "energy": energy.session_load(blocks).as_dict(), "exercises": exercises,
        })
    return {
        "active": await workout_view(session, user, active, image_for) if active else None,
        "next_index": await workouts.next_day_index(session, user, plan),
        "days": days,
    }


# ---------- live logger ----------

async def workout_view(session: AsyncSession, user: User, ws: WorkoutSession, image_for: ImageFor) -> dict:
    """Everything the live logger shows for one workout."""
    catalog = await load_catalog(session)
    plan = await plans.get_plan(session, user)
    title = None
    if plan is not None and ws.day_index is not None:
        day = next((d for d in plan.days if d.day_index == ws.day_index), None)
        if day is not None and day.name_key == ws.name_key and day.suffix == ws.suffix:
            title = day.title

    labels = superset_labels(ws.items)
    first_open = next((i for i in range(len(ws.items)) if not workouts.item_done(ws, i)), None)
    items, planned_blocks, done_blocks = [], [], []
    for index, item in enumerate(ws.items):
        ex = await _exercise(session, catalog, item["exercise_id"])
        working = workouts.sets_for(ws, ex.id)
        warmups = workouts.sets_for(ws, ex.id, warmup=True)
        hint, previous = await workouts.suggestion_for(session, user, ws, index)
        block = _block(ex, item["sets"], item["timed"])
        planned_blocks.append(block)
        done_blocks.append((block, len(working)))
        if len(working) >= item["sets"]:
            status = "completed"
        elif index == first_open:
            status = "current"
        else:
            status = "upcoming"
        items.append({
            "index": index, "exercise_id": ex.id, "name": ex.name, "muscle_group": ex.muscle_group,
            "equipment": ex.equipment, "image": image_for(ex.id),
            "sets": item["sets"], "rep_min": item["rep_min"], "rep_max": item["rep_max"],
            "timed": item["timed"], "rest_seconds": item["rest_seconds"],
            "note": item.get("note"), "group": item.get("group"), "label": labels[index],
            "status": status,
            "logged": [set_dict(s) for s in warmups + working],
            "previous": [{"weight_kg": s.weight_kg, "reps": s.reps} for s in previous],
            "suggestion": hint_dict(hint),
        })
    planned = energy.session_load(planned_blocks)
    return {
        "id": ws.id, "started_at": _aware(ws.started_at).isoformat(),
        "finished": ws.finished_at is not None,
        "day_index": ws.day_index, "name_key": ws.name_key, "suffix": ws.suffix, "title": title,
        "current_index": first_open if first_open is not None else ws.current_index,
        "items": items,
        "done_sets": sum(len(workouts.sets_for(ws, i["exercise_id"])) for i in ws.items),
        "planned_sets": sum(i["sets"] for i in ws.items),
        # The bar drains as working sets are done; warnings come from the planned load.
        "energy": {"left": energy.energy_left(done_blocks), "planned_left": planned.energy_left,
                   "warnings": list(planned.warnings)},
    }


async def open_workout(session: AsyncSession, user: User, workout_id: int,
                       editable: bool = True) -> WorkoutSession:
    """A workout of this user (404 otherwise). Editable = not finished yet (409 otherwise)."""
    ws = await workouts.get_session(session, user, workout_id)
    if ws is None:
        raise TrainError("no_workout", 404)
    if editable and ws.finished_at is not None:
        raise TrainError("workout_finished")
    return ws


async def start_workout(session: AsyncSession, user: User, day_index: int, force: bool) -> WorkoutSession:
    """Start a plan day. An unfinished workout must be continued or finished first (force=True ends it)."""
    if user.profile is None:
        raise TrainError("profile_required")
    active = await workouts.get_active(session, user)
    if active is not None and not force:
        raise TrainError("workout_active")
    _program, plan = await programs.ensure_current(session, user)
    days = sorted(plan.days, key=lambda d: d.day_index)
    if not 0 <= day_index < len(days) or not days[day_index].exercises:
        raise TrainError("bad_day", 422)
    return await workouts.start(session, user, plan, day_index)


async def substitute_item(session: AsyncSession, user: User, ws: WorkoutSession, index: int) -> None:
    if not 0 <= index < len(ws.items):
        raise TrainError("err_bad_exercise", 422)
    ws.current_index = index
    try:
        swapped = await workouts.swap_current(session, user, ws)
    except workouts.LogError as error:
        raise TrainError(error.text_key) from None
    if swapped is None:
        raise TrainError("no_substitute")


async def finish_workout(session: AsyncSession, user: User, ws: WorkoutSession) -> dict:
    """Finish summary: time, sets, volume, PRs, next-time suggestions, new achievements."""
    summary = await workouts.finish(session, user, ws)
    if summary is None:
        return {"discarded": True}
    try:
        # Missed-workout streak resets (the bot rebuilds its reminder jobs from the database).
        await reminders.workout_finished(session, user)
    except Exception:  # noqa: BLE001 - the workout is saved; don't fail the summary
        logger.exception("Could not update reminders after a Mini App workout")
    unlocked: list[str] = []
    try:
        unlocked = [getattr(a, "code", str(a)) for a in (await achievements.check_new(session, user) or [])]
    except Exception:  # noqa: BLE001
        logger.exception("Could not check achievements after a Mini App workout")
    # XP from this workout (the level itself is calculated from all your data).
    prs = sum(1 for ex in summary.exercises for s in ex.sets if s.pr)
    level = await levels.level_view(session, user)
    goal_week = level["week_done"] == level["week_goal"]  # this workout completed the weekly goal
    gained = xp_config.XP_PER_WORKOUT + prs * xp_config.XP_PER_PR + (xp_config.XP_PER_GOAL_WEEK if goal_week else 0)
    before = levels.make_level(max(0, level["level"]["xp"] - gained))
    return {
        "xp_gained": gained, "level": level["level"], "level_up": before.index < level["level"]["index"],
        "discarded": False, "minutes": summary.minutes, "total_sets": summary.total_sets,
        "volume_kg": summary.volume_kg,
        "prs": [ex.exercise.name for ex in summary.exercises if any(s.pr for s in ex.sets)],
        "achievements": unlocked,
        "exercises": [{
            "exercise_id": ex.exercise.id, "name": ex.exercise.name, "timed": ex.timed,
            "equipment": ex.exercise.equipment,
            "sets": [{"weight_kg": s.weight_kg, "reps": s.reps, "pr": bool(s.pr)} for s in ex.sets],
            "next_time": hint_dict(ex.next_time),
        } for ex in summary.exercises],
    }
