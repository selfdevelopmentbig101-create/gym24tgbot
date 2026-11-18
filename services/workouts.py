"""
Workout sessions and set logging (no Telegram code). Shared by the bot and the Mini App.

Flow: start() copies a plan day into a session -> log_set() for each set ->
finish() returns a summary. The "draft" (weight/reps on the bot's Log button) is
pre-filled from today's last set, or from the overload suggestion.

Stage 5 (Mini App logger) adds: warm-up sets (never count for PRs, progression,
volume or "sets done"), optional RPE, editing/deleting any set, and per-exercise
notes and superset groups (stored in the session's items).
"""
import logging
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Exercise, SetLog, User, WorkoutPlan, WorkoutSession, utcnow  # noqa: F401
from services import adjust, records, reminders
from services.exercises import UserFilter, load_catalog, pick_substitute
from services.plan_generator import prescription
from services.progression import SetResult, Suggestion, suggest

logger = logging.getLogger(__name__)

MAX_WEIGHT_KG = 500.0
MAX_REPS = 100
MAX_SECONDS = 600
MAX_NOTE = 200
SUPERSET_GROUPS = ("A", "B", "C", "D")
STALE_AFTER = timedelta(hours=12)  # an unfinished workout older than this is closed


class LogError(ValueError):
    """Invalid set values. text_key is shown to the user."""

    def __init__(self, text_key: str):
        super().__init__(text_key)
        self.text_key = text_key


@dataclass
class ExerciseSummary:
    exercise: Exercise
    sets: list[SetLog]
    next_time: Suggestion | None
    timed: bool = False


@dataclass
class WorkoutSummary:
    name_key: str
    suffix: str
    minutes: int
    total_sets: int
    volume_kg: float
    exercises: list[ExerciseSummary] = field(default_factory=list)


def _aware(dt):
    """SQLite returns naive datetimes; treat them as UTC."""
    from datetime import timezone
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------- Reading ----------

async def get_active(session: AsyncSession, user: User) -> WorkoutSession | None:
    """The unfinished workout, if any. Very old unfinished workouts are closed first."""
    ws = await session.scalar(
        select(WorkoutSession)
        .where(WorkoutSession.user_id == user.id, WorkoutSession.finished_at.is_(None))
        .order_by(WorkoutSession.id.desc())
    )
    if ws is not None and utcnow() - _aware(ws.started_at) > STALE_AFTER:
        await finish(session, user, ws)
        return None
    return ws


async def get_session(session: AsyncSession, user: User, session_id: int) -> WorkoutSession | None:
    ws = await session.get(WorkoutSession, session_id)
    return ws if ws is not None and ws.user_id == user.id else None


def sets_for(ws: WorkoutSession, exercise_id: str, warmup: bool = False) -> list[SetLog]:
    """Today's working sets for an exercise (warmup=True: its warm-up sets instead)."""
    return [s for s in ws.sets if s.exercise_id == exercise_id and bool(s.warmup) == warmup]


def item_done(ws: WorkoutSession, index: int) -> bool:
    item = ws.items[index]
    return len(sets_for(ws, item["exercise_id"])) >= item["sets"]


def all_done(ws: WorkoutSession) -> bool:
    return all(item_done(ws, i) for i in range(len(ws.items)))


async def history(session: AsyncSession, user: User, exercise_id: str,
                  exclude_session_id: int | None = None, limit: int = 2) -> list[list[SetResult]]:
    """Working sets from the most recent workouts with this exercise, newest first."""
    query = (
        select(SetLog.session_id)
        .where(SetLog.user_id == user.id, SetLog.exercise_id == exercise_id,
               SetLog.warmup.is_(False))
        .group_by(SetLog.session_id)
        .order_by(func.max(SetLog.id).desc())
        .limit(limit)
    )
    if exclude_session_id is not None:
        query = query.where(SetLog.session_id != exclude_session_id)
    session_ids = list(await session.scalars(query))
    result = []
    for sid in session_ids:
        rows = await session.scalars(
            select(SetLog).where(SetLog.session_id == sid, SetLog.exercise_id == exercise_id,
                                 SetLog.warmup.is_(False))
            .order_by(SetLog.set_number)
        )
        result.append([SetResult(r.weight_kg, r.reps) for r in rows])
    return result


async def suggestion_for(session: AsyncSession, user: User, ws: WorkoutSession,
                         index: int) -> tuple[Suggestion, list[SetResult]]:
    """The overload suggestion for an exercise, plus last workout's sets."""
    item = ws.items[index]
    exercise = await session.get(Exercise, item["exercise_id"])
    past = await history(session, user, item["exercise_id"], exclude_session_id=ws.id)
    previous = past[0] if past else []
    hint = suggest(previous, rep_min=item["rep_min"], rep_max=item["rep_max"],
                   planned_sets=item["sets"], equipment=exercise.equipment,
                   timed=item["timed"], before_previous=past[1] if len(past) > 1 else None)
    if previous and not item["timed"] and await in_deload(session, user):
        weight = adjust.deload_weight(max(s.weight_kg for s in previous))
        hint = Suggestion("deload", weight, item["rep_min"], {"weight": weight, "low": item["rep_min"]})
    return hint, previous


async def in_deload(session: AsyncSession, user: User) -> bool:
    today = reminders.local_now(await reminders.get_settings(session, user)).date()
    return user.profile is not None and adjust.deload_active(user.profile, today)


async def next_day_index(session: AsyncSession, user: User, plan: WorkoutPlan) -> int:
    """The plan day after the last finished workout (day 1 if none)."""
    last = await session.scalar(
        select(WorkoutSession.day_index)
        .where(WorkoutSession.user_id == user.id, WorkoutSession.finished_at.is_not(None),
               WorkoutSession.day_index.is_not(None))
        .order_by(WorkoutSession.finished_at.desc(), WorkoutSession.id.desc())
    )
    chosen = getattr(plan, "active_day_index", None)
    if chosen is not None and 0 <= chosen < len(plan.days):
        return chosen  # the split the user chose in Train > Splits
    if last is None or not plan.days:
        return 0
    return (last + 1) % len(plan.days)


# ---------- Changing ----------

async def start(session: AsyncSession, user: User, plan: WorkoutPlan, day_index: int) -> WorkoutSession:
    """Start a workout from a plan day (closes any unfinished one first)."""
    active = await get_active(session, user)
    if active is not None:
        await finish(session, user, active)

    day = plan.days[day_index]
    deload = await in_deload(session, user)
    items = [
        {"exercise_id": e.exercise_id,
         "sets": adjust.deload_sets(e.sets) if deload else e.sets,
         "rep_min": e.rep_min, "rep_max": e.rep_max, "timed": e.timed,
         "rest_seconds": e.rest_seconds}
        for e in sorted(day.exercises, key=lambda e: e.position)
    ]
    ws = WorkoutSession(user_id=user.id, day_index=day_index, name_key=day.name_key,
                        suffix=day.suffix, items=items, sets=[])
    session.add(ws)
    await session.commit()
    logger.info("Workout started")
    await enter_exercise(session, user, ws, 0)
    return ws


async def add_exercise(session: AsyncSession, user: User, ws: WorkoutSession,
                       exercise: Exercise) -> int:
    """Add an exercise to today's workout (or find it). Returns its index."""
    for index, item in enumerate(ws.items):
        if item["exercise_id"] == exercise.id:
            return index
    p = prescription(exercise, UserFilter.from_profile(user.profile).experience)
    ws.items = ws.items + [{"exercise_id": exercise.id, "sets": p.sets, "rep_min": p.rep_min,
                            "rep_max": p.rep_max, "timed": p.timed, "rest_seconds": p.rest_seconds}]
    await session.commit()
    return len(ws.items) - 1


async def enter_exercise(session: AsyncSession, user: User, ws: WorkoutSession, index: int) -> None:
    """Make `index` the current exercise and pre-fill the draft."""
    index %= len(ws.items)
    ws.current_index = index
    today = sets_for(ws, ws.items[index]["exercise_id"])
    if today:
        ws.draft_weight, ws.draft_reps = today[-1].weight_kg, today[-1].reps
    else:
        hint, _ = await suggestion_for(session, user, ws, index)
        ws.draft_weight, ws.draft_reps = hint.weight_kg, hint.reps
    await session.commit()


async def adjust_draft(session: AsyncSession, ws: WorkoutSession,
                       weight_delta: float = 0, reps_delta: int = 0) -> None:
    timed = ws.items[ws.current_index]["timed"]
    ws.draft_weight = min(max(0.0, round(ws.draft_weight + weight_delta, 2)), MAX_WEIGHT_KG)
    ws.draft_reps = min(max(1, ws.draft_reps + reps_delta), MAX_SECONDS if timed else MAX_REPS)
    await session.commit()


def _check_values(item: dict, weight: float, reps: int, rpe: float | None) -> None:
    if not 0 <= weight <= MAX_WEIGHT_KG:
        raise LogError("err_set_weight")
    if not 1 <= reps <= (MAX_SECONDS if item["timed"] else MAX_REPS):
        raise LogError("err_set_reps")
    if rpe is not None and not 1 <= rpe <= 10:
        raise LogError("err_set_rpe")


async def _mark_pr(session: AsyncSession, user: User, entry: SetLog, timed: bool) -> None:
    """PR = beats your previous best estimated 1RM. Warm-ups and first-ever sets never count."""
    previous_best = await records.best_e1rm(session, user, entry.exercise_id,
                                            exclude_set_id=entry.id)
    estimate = None if timed or entry.warmup else records.e1rm(entry.weight_kg, entry.reps)
    entry.pr = bool(previous_best and estimate and estimate > previous_best + 0.01)
    entry.previous_best = previous_best  # not stored; used for the "new PR" message
    entry.estimate = estimate


async def log_set(session: AsyncSession, user: User, ws: WorkoutSession,
                  weight: float | None = None, reps: int | None = None, *,
                  index: int | None = None, rpe: float | None = None,
                  warmup: bool = False) -> SetLog:
    """
    Log a set (defaults: the current exercise and the draft values).
    The Mini App passes the exercise `index`, plus optional RPE and the warm-up flag.
    """
    if index is not None:
        if not 0 <= index < len(ws.items):
            raise LogError("err_bad_exercise")
        ws.current_index = index
    item = ws.items[ws.current_index]
    weight = ws.draft_weight if weight is None else weight
    reps = ws.draft_reps if reps is None else reps
    _check_values(item, weight, reps, rpe)

    entry = SetLog(user_id=user.id, exercise_id=item["exercise_id"],
                   set_number=len(sets_for(ws, item["exercise_id"], warmup)) + 1,
                   weight_kg=round(float(weight), 2), reps=int(reps),
                   rpe=None if rpe is None else round(float(rpe) * 2) / 2, warmup=warmup)
    await _mark_pr(session, user, entry, item["timed"])
    ws.sets.append(entry)
    if not warmup:
        ws.draft_weight, ws.draft_reps = entry.weight_kg, entry.reps
    await session.commit()
    return entry


def _find_set(ws: WorkoutSession, set_id: int) -> SetLog:
    for entry in ws.sets:
        if entry.id == set_id:
            return entry
    raise LogError("err_no_set")


def _item_of(ws: WorkoutSession, exercise_id: str) -> dict:
    return next((i for i in ws.items if i["exercise_id"] == exercise_id),
                {"timed": False, "exercise_id": exercise_id})


async def edit_set(session: AsyncSession, user: User, ws: WorkoutSession, set_id: int,
                   changes: dict) -> SetLog:
    """Fix a logged set (weight, reps, RPE). The PR mark is checked again."""
    entry = _find_set(ws, set_id)
    item = _item_of(ws, entry.exercise_id)
    weight = changes["weight_kg"] if changes.get("weight_kg") is not None else entry.weight_kg
    reps = changes["reps"] if changes.get("reps") is not None else entry.reps
    rpe = changes["rpe"] if "rpe" in changes else entry.rpe
    _check_values(item, weight, reps, rpe)
    entry.weight_kg, entry.reps = round(float(weight), 2), int(reps)
    entry.rpe = None if rpe is None else round(float(rpe) * 2) / 2
    await _mark_pr(session, user, entry, item.get("timed", False))
    await session.commit()
    return entry


async def delete_set(session: AsyncSession, ws: WorkoutSession, set_id: int) -> SetLog:
    """Remove one set; the other sets of that exercise are renumbered."""
    entry = _find_set(ws, set_id)
    ws.sets.remove(entry)
    for kind in (False, True):
        for number, s in enumerate(sets_for(ws, entry.exercise_id, kind), start=1):
            s.set_number = number
    await session.commit()
    return entry


async def update_item(session: AsyncSession, ws: WorkoutSession, index: int, changes: dict) -> None:
    """A note for one exercise, or its superset group ("A".."D", None = no superset)."""
    if not 0 <= index < len(ws.items):
        raise LogError("err_bad_exercise")
    items = [dict(i) for i in ws.items]
    if "note" in changes:
        note = (changes["note"] or "").strip()[:MAX_NOTE]
        items[index]["note"] = note or None
    if "group" in changes:
        group = changes["group"]
        if group is not None and group not in SUPERSET_GROUPS:
            raise LogError("err_bad_group")
        items[index]["group"] = group
    ws.items = items  # reassign so SQLAlchemy notices the JSON change
    await session.commit()


async def same_as_last_time(session: AsyncSession, user: User,
                            ws: WorkoutSession) -> SetResult | None:
    """Last workout's matching set (same set number, else its last set)."""
    item = ws.items[ws.current_index]
    past = await history(session, user, item["exercise_id"], exclude_session_id=ws.id, limit=1)
    if not past:
        return None
    number = len(sets_for(ws, item["exercise_id"]))  # 0-based index of the next set
    previous = past[0]
    return previous[number] if number < len(previous) else previous[-1]


async def undo_last(session: AsyncSession, ws: WorkoutSession) -> SetLog | None:
    """Remove the most recently logged set and jump back to its exercise."""
    if not ws.sets:
        return None
    last = ws.sets[-1]
    ws.sets.remove(last)
    for index, item in enumerate(ws.items):
        if item["exercise_id"] == last.exercise_id:
            ws.current_index = index
    ws.draft_weight, ws.draft_reps = last.weight_kg, last.reps
    await session.commit()
    return last


async def swap_current(session: AsyncSession, user: User, ws: WorkoutSession) -> Exercise | None:
    """Replace the current exercise (e.g. machine taken). Only if no sets logged for it yet."""
    item = ws.items[ws.current_index]
    if sets_for(ws, item["exercise_id"]) or sets_for(ws, item["exercise_id"], True):
        raise LogError("swap_after_sets")
    catalog = await load_catalog(session)
    current = catalog.get(item["exercise_id"]) or await session.get(Exercise, item["exercise_id"])
    substitute = pick_substitute(current, catalog, UserFilter.from_profile(user.profile),
                                 exclude_ids={i["exercise_id"] for i in ws.items})
    if substitute is None:
        return None
    items = [dict(i) for i in ws.items]
    items[ws.current_index]["exercise_id"] = substitute.id
    ws.items = items  # reassign so SQLAlchemy notices the JSON change
    await session.commit()
    await enter_exercise(session, user, ws, ws.current_index)
    return substitute


async def finish(session: AsyncSession, user: User, ws: WorkoutSession) -> WorkoutSummary | None:
    """Close the workout. Returns a summary, or None if nothing was logged (it's discarded)."""
    if not ws.sets:
        await session.delete(ws)
        await session.commit()
        logger.info("Empty workout discarded")
        return None

    ws.finished_at = utcnow()
    # A split chosen in Train > Splits counts as done once its workout is finished;
    # after that the normal rotation continues from it.
    plan = await session.scalar(select(WorkoutPlan).where(WorkoutPlan.user_id == user.id))
    if plan is not None and plan.active_day_index is not None and plan.active_day_index == ws.day_index:
        plan.active_day_index = None
    await session.commit()

    working = [s for s in ws.sets if not s.warmup]
    summary = WorkoutSummary(
        name_key=ws.name_key, suffix=ws.suffix,
        minutes=max(1, round((_aware(ws.finished_at) - _aware(ws.started_at)).total_seconds() / 60)),
        total_sets=len(working),
        volume_kg=round(sum(s.weight_kg * s.reps for s in working
                            if not _is_timed(ws, s.exercise_id)), 1),
    )
    deload = await in_deload(session, user)
    for item in ws.items:
        done = sets_for(ws, item["exercise_id"])
        if not done:
            continue
        exercise = await session.get(Exercise, item["exercise_id"])
        hint = None if deload else suggest(
            [SetResult(s.weight_kg, s.reps) for s in done], rep_min=item["rep_min"],
            rep_max=item["rep_max"], planned_sets=item["sets"],
            equipment=exercise.equipment, timed=item["timed"])
        summary.exercises.append(ExerciseSummary(exercise, done, hint, item["timed"]))
    logger.info("Workout finished (%s sets)", summary.total_sets)
    return summary


def _is_timed(ws: WorkoutSession, exercise_id: str) -> bool:
    return any(i["exercise_id"] == exercise_id and i["timed"] for i in ws.items)
