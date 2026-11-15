"""
Programs and the split editor (database side). Stage 4.

How it fits together:
- The CURRENT program's days ARE the user's workout plan (workout_plans,
  plan_days, plan_exercises), so the bot, reminders and the logger keep working.
- Other programs keep a copy of their days in programs.days_snapshot. Making a
  program current saves the old plan into its program and restores the new one.
- Pure rules: services/program_rules.py (goals, built-in programs, limits) and
  services/energy.py (energy bar, weekly volume, warnings).

Every function raises ProgramError(code) for things the user can't do; the API
turns it into an HTTP error with that code, and the app translates the code.
"""
import logging
import re
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (Exercise, PlanDay, PlanExercise, Program, ReminderSettings, User,
                             WorkoutPlan, WorkoutSession)
from services import energy
from services import program_rules as rules
from services.exercises import UserFilter, get_injury_rules, is_available, load_catalog
from services.plan_generator import PlanSpec, generate_plan, prescription
from services.plans import (generate_for_user, load_plan, make_entry, plan_from_snapshot,
                            substitute_in_plan)

logger = logging.getLogger(__name__)

ImageFor = Callable[[str], "str | None"]   # exercise id -> thumbnail URL


class ProgramError(Exception):
    """Something the user asked for can't be done. `code` is a text key for the app."""

    def __init__(self, code: str, status: int = 409):
        super().__init__(code)
        self.code = code
        self.status = status


# ---------- time helpers ----------

def _zone(name: str | None):
    """Time zone from the reminder settings: "Europe/Berlin" or a fixed "UTC+05:30"."""
    if not name or name == "UTC":
        return timezone.utc
    match = re.fullmatch(r"UTC([+-])(\d{1,2}):(\d{2})", name)
    if match:
        sign = 1 if match.group(1) == "+" else -1
        return timezone(sign * timedelta(hours=int(match.group(2)), minutes=int(match.group(3))))
    try:
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 - unknown name: fall back to UTC
        return timezone.utc


def _as_utc(moment: datetime) -> datetime:
    """SQLite returns naive datetimes; they are UTC."""
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment


async def _finished_since(session: AsyncSession, user_id: int,
                          since: datetime) -> list[tuple[datetime, int | None]]:
    """(finished_at in UTC, plan day index) of finished workouts, oldest first."""
    rows = await session.execute(
        select(WorkoutSession.finished_at, WorkoutSession.day_index)
        .where(WorkoutSession.user_id == user_id, WorkoutSession.finished_at.is_not(None),
               WorkoutSession.finished_at >= since)
        .order_by(WorkoutSession.finished_at))
    return [(_as_utc(finished), day_index) for finished, day_index in rows]


# ---------- loading ----------

async def current_program(session: AsyncSession, user_id: int) -> Program | None:
    return await session.scalar(
        select(Program).where(Program.user_id == user_id, Program.status == "current")
        .order_by(Program.id.desc()))


async def ensure_current(session: AsyncSession, user: User) -> tuple[Program, WorkoutPlan]:
    """The current program and its days. Creates the default program when missing."""
    if user.profile is None:
        raise ProgramError("profile_required")
    plan = await load_plan(session, user.id)
    if plan is None:
        await generate_for_user(session, user)
        plan = await load_plan(session, user.id)
        if plan is None:
            raise ProgramError("no_exercises", 503)
    program = await current_program(session, user.id)
    if program is None:  # a plan made before Stage 4: wrap it in a default program
        started = _as_utc(plan.created_at).date() if plan.created_at else datetime.now(timezone.utc).date()
        program = Program(user_id=user.id, name="", kind="default", goal=rules.DEFAULT_GOAL,
                          weeks=rules.DEFAULT_WEEKS, workouts_per_week=len(plan.days),
                          status="current", started_on=started, days_snapshot={})
        session.add(program)
        await session.commit()
    return program, plan


async def _own_program(session: AsyncSession, user_id: int, program_id: int) -> Program:
    program = await session.scalar(
        select(Program).where(Program.id == program_id, Program.user_id == user_id))
    if program is None:
        raise ProgramError("no_program", 404)
    return program


# ---------- snapshots (saved programs) ----------

def snapshot_of(plan: WorkoutPlan) -> dict:
    """The plan's days as plain data, to keep in programs.days_snapshot."""
    return {"split": plan.split, "days": [
        {"name_key": day.name_key, "suffix": day.suffix, "title": day.title, "exercises": [
            {"exercise_id": e.exercise_id, "sets": e.sets, "rep_min": e.rep_min, "rep_max": e.rep_max,
             "timed": e.timed, "rest_seconds": e.rest_seconds}
            for e in sorted(day.exercises, key=lambda e: e.position)]}
        for day in sorted(plan.days, key=lambda d: d.day_index)]}


def snapshot_from_spec(spec: PlanSpec) -> dict:
    return {"split": spec.split, "days": [
        {"name_key": day.name_key, "suffix": day.suffix, "title": None, "exercises": [
            {"exercise_id": i.exercise_id, "sets": i.sets, "rep_min": i.rep_min, "rep_max": i.rep_max,
             "timed": i.timed, "rest_seconds": i.rest_seconds} for i in day.exercises]}
        for day in spec.days]}


def _generated_snapshot(user: User, days: int, goal: str, catalog: dict[str, Exercise]) -> dict:
    """Default days for a program: the plan generator, adjusted for the goal."""
    spec = generate_plan(list(catalog.values()), UserFilter.from_profile(user.profile), days)
    rules.apply_goal(spec, goal, catalog)
    return snapshot_from_spec(spec)


async def _replace_plan(session: AsyncSession, user_id: int, snapshot: dict,
                        catalog: dict[str, Exercise]) -> None:
    old = await load_plan(session, user_id)
    if old is not None:
        await session.delete(old)
        await session.flush()
    session.add(plan_from_snapshot(user_id, snapshot, catalog))


# ---------- views (what the API returns) ----------

def _split_of(program: Program, plan: WorkoutPlan | None) -> str | None:
    if plan is not None and program.status == "current":
        return plan.split
    return (program.days_snapshot or {}).get("split")


def _name_key(program: Program, split: str | None) -> str | None:
    """Text key for the default name (None when the user named the program)."""
    if program.name:
        return None
    if program.kind == "template" and program.template:
        return "template_" + program.template
    return "split_" + split if split else "program_default"


def program_item(program: Program, plan: WorkoutPlan | None = None) -> dict:
    split = _split_of(program, plan)
    return {"id": program.id, "name": program.name or None, "name_key": _name_key(program, split),
            "kind": program.kind, "goal": program.goal, "weeks": program.weeks,
            "workouts_per_week": program.workouts_per_week, "status": program.status,
            "split": split, "started_on": program.started_on.isoformat() if program.started_on else None}


def _details(program: Program, entries: list[tuple[int, int, int, bool, int]]) -> dict:
    """Focus, volume trend, intensity (RPE) and rep range for the details card."""
    rule = rules.GOAL_RULES.get(program.goal, rules.GOAL_RULES[rules.DEFAULT_GOAL])
    reps = [(lo, hi) for _sets, lo, hi, timed, _rest in entries if not timed]
    return {"focus": program.goal, "volume_trend": rule.volume_trend, "rpe": list(rule.rpe),
            "rep_range": [min(lo for lo, _ in reps), max(hi for _, hi in reps)] if reps else None}


def _minutes(day: PlanDay) -> int:
    return rules.estimate_minutes((e.sets, e.rep_max, e.timed, e.rest_seconds) for e in day.exercises)


def _days_until_training(today: date, weekdays: list[int], skip_today: bool) -> int:
    for offset in range(1 if skip_today else 0, 8):
        if (today + timedelta(days=offset)).weekday() in weekdays:
            return offset
    return 0


async def program_card(session: AsyncSession, user: User, program: Program, plan: WorkoutPlan) -> dict:
    """Current program card: week x of y, % completed, frequency, upcoming workout, details."""
    settings = await session.get(ReminderSettings, user.id)
    tz = _zone(settings.timezone if settings else None)
    today = datetime.now(tz).date()
    start = program.started_on or today
    since = datetime.combine(start, time.min, tzinfo=tz).astimezone(timezone.utc)
    finished = await _finished_since(session, user.id, since)
    days = sorted(plan.days, key=lambda d: d.day_index)

    target = max(1, program.weeks * max(1, program.workouts_per_week))
    next_index = 0
    if finished and finished[-1][1] is not None and days:
        next_index = (finished[-1][1] + 1) % len(days)  # the day after the last one done
    weekdays = rules.training_weekdays(program.workouts_per_week,
                                       settings.workout_days if settings else None)
    done_today = any(f.astimezone(tz).date() == today for f, _ in finished)
    in_days = _days_until_training(today, weekdays, skip_today=done_today)
    upcoming = None
    if days:
        day = days[min(next_index, len(days) - 1)]
        upcoming = {"day_id": day.id, "index": day.day_index, "name_key": day.name_key,
                    "suffix": day.suffix, "title": day.title, "exercises": len(day.exercises),
                    "minutes": _minutes(day), "in_days": in_days,
                    "date": (today + timedelta(days=in_days)).isoformat()}
    entries = [(e.sets, e.rep_min, e.rep_max, e.timed, e.rest_seconds) for d in days for e in d.exercises]
    return {
        **program_item(program, plan),
        "week": min(program.weeks, max(1, (today - start).days // 7 + 1)),
        "completed": len(finished), "target": target,
        "percent": min(100, round(100 * len(finished) / target)),
        "weekdays": weekdays, "upcoming": upcoming,
        "details": {**_details(program, entries),
                    "minutes": round(sum(_minutes(d) for d in days) / len(days)) if days else 0},
    }


def _block(entry: PlanExercise, exercise: Exercise) -> energy.SetBlock:
    return energy.SetBlock(exercise.muscle_group, tuple(exercise.secondary_muscles or ()),
                           exercise.movement_type, entry.sets, entry.timed)


async def plan_view(session: AsyncSession, user: User, image_for: ImageFor) -> dict:
    """Everything the Plan tab and the split editor need, in one response."""
    program, plan = await ensure_current(session, user)
    catalog = await load_catalog(session)
    user_filter = UserFilter.from_profile(user.profile)
    injury_rules = get_injury_rules()
    days_out, week = [], []
    for day in sorted(plan.days, key=lambda d: d.day_index):
        blocks, items = [], []
        for entry in sorted(day.exercises, key=lambda e: e.position):
            ex = catalog.get(entry.exercise_id)
            if ex is not None:
                blocks.append(_block(entry, ex))
            items.append({
                "id": entry.id, "exercise_id": entry.exercise_id,
                "name": ex.name if ex else entry.exercise_id,
                "muscle_group": ex.muscle_group if ex else None,
                "secondary_muscles": list(ex.secondary_muscles or []) if ex else [],
                "movement_type": ex.movement_type if ex else None,
                "image": image_for(entry.exercise_id) if ex else None,
                "fits": is_available(ex, user_filter, injury_rules) if ex else False,
                "position": entry.position, "sets": entry.sets, "rep_min": entry.rep_min,
                "rep_max": entry.rep_max, "timed": entry.timed, "rest_seconds": entry.rest_seconds,
            })
        week.append(blocks)
        days_out.append({"id": day.id, "index": day.day_index, "name_key": day.name_key,
                         "suffix": day.suffix, "title": day.title, "minutes": _minutes(day),
                         "energy": energy.session_load(blocks).as_dict(), "exercises": items})
    return {"program": await program_card(session, user, program, plan), "days": days_out,
            "weekly_volume": [v.as_dict() for v in energy.weekly_volume(week)],
            "limits": energy.limits()}


async def day_energy(session: AsyncSession, user: User, day_id: int) -> dict:
    """Session load for one day plus the week's volume per muscle (GET /api/energy)."""
    _program, plan = await ensure_current(session, user)
    catalog = await load_catalog(session)
    day = _find_day(plan, day_id)

    def blocks(d: PlanDay) -> list[energy.SetBlock]:
        return [_block(e, catalog[e.exercise_id]) for e in d.exercises if e.exercise_id in catalog]

    return {"day_id": day.id, "session": energy.session_load(blocks(day)).as_dict(),
            "weekly_volume": [v.as_dict() for v in energy.weekly_volume([blocks(d) for d in plan.days])],
            "limits": energy.limits()}


# ---------- program lists and details ----------

async def list_programs(session: AsyncSession, user: User, tab: str) -> list[dict]:
    """Current: the one in use. Available: built-in programs. Created: every saved program."""
    program, plan = await ensure_current(session, user)
    if tab == "current":
        return [program_item(program, plan)]
    if tab == "available":
        return [{"key": t.key, "name_key": "template_" + t.key, "workouts_per_week": t.days,
                 "goal": t.goal, "weeks": t.weeks, "split": t.split} for t in rules.TEMPLATES.values()]
    rows = await session.scalars(
        select(Program).where(Program.user_id == user.id, Program.status == "saved")
        .order_by(Program.created_at.desc(), Program.id.desc()))
    return [program_item(p) for p in rows]


async def program_detail(session: AsyncSession, user: User, program_id: int) -> dict:
    current, plan = await ensure_current(session, user)
    program = await _own_program(session, user.id, program_id)
    catalog = await load_catalog(session)
    is_current = program.id == current.id
    days = (snapshot_of(plan) if is_current else (program.days_snapshot or {})).get("days") or []
    out_days, entries = [], []
    for day in days:
        items = day.get("exercises") or []
        entries += [(e["sets"], e["rep_min"], e["rep_max"], bool(e.get("timed")), e["rest_seconds"]) for e in items]
        out_days.append({
            "name_key": day.get("name_key"), "suffix": day.get("suffix") or "", "title": day.get("title"),
            "minutes": rules.estimate_minutes((e["sets"], e["rep_max"], bool(e.get("timed")), e["rest_seconds"])
                                              for e in items),
            "exercises": [{"exercise_id": e["exercise_id"],
                           "name": catalog[e["exercise_id"]].name if e["exercise_id"] in catalog else e["exercise_id"],
                           "sets": e["sets"], "rep_min": e["rep_min"], "rep_max": e["rep_max"],
                           "timed": bool(e.get("timed"))} for e in items],
        })
    minutes = round(sum(d["minutes"] for d in out_days) / len(out_days)) if out_days else 0
    return {**program_item(program, plan if is_current else None),
            "details": {**_details(program, entries), "minutes": minutes}, "days": out_days}


# ---------- creating and switching programs ----------

async def create_program(session: AsyncSession, user: User, name: str, weeks: int,
                         workouts_per_week: int, goal: str, activate_now: bool = False) -> Program:
    """A new program, filled with default days for its goal and frequency."""
    await ensure_current(session, user)
    count = await session.scalar(select(func.count()).select_from(Program).where(Program.user_id == user.id))
    if count >= rules.MAX_PROGRAMS:
        raise ProgramError("too_many_programs")
    catalog = await load_catalog(session)
    snapshot = _generated_snapshot(user, workouts_per_week, goal, catalog)
    program = Program(user_id=user.id, name=name.strip(), kind="custom", goal=goal, weeks=weeks,
                      workouts_per_week=len(snapshot["days"]), status="saved", days_snapshot=snapshot)
    session.add(program)
    await session.commit()
    logger.info("Program created (%s, %s days)", goal, len(snapshot["days"]))
    if activate_now:
        await activate_program(session, user, program.id)
    return program


async def activate_program(session: AsyncSession, user: User, program_id: int) -> None:
    """Make a saved program current. The old plan is kept in its program."""
    current, plan = await ensure_current(session, user)
    target = await _own_program(session, user.id, program_id)
    if target.id == current.id:
        return
    catalog = await load_catalog(session)
    current.days_snapshot = snapshot_of(plan)
    current.status = "saved"
    snapshot = target.days_snapshot or {}
    if not snapshot.get("days"):
        snapshot = _generated_snapshot(user, target.workouts_per_week, target.goal, catalog)
    await _replace_plan(session, user.id, snapshot, catalog)
    target.status = "current"
    target.started_on = datetime.now(timezone.utc).date()
    target.workouts_per_week = len(snapshot["days"])
    target.days_snapshot = {}
    await session.commit()
    logger.info("Program activated")


async def start_template(session: AsyncSession, user: User, key: str) -> Program:
    """Start a built-in program from the Available tab."""
    template = rules.TEMPLATES.get(key)
    if template is None:
        raise ProgramError("no_template", 404)
    await ensure_current(session, user)
    count = await session.scalar(select(func.count()).select_from(Program).where(Program.user_id == user.id))
    if count >= rules.MAX_PROGRAMS:
        raise ProgramError("too_many_programs")
    program = Program(user_id=user.id, name="", kind="template", template=key, goal=template.goal,
                      weeks=template.weeks, workouts_per_week=template.days, status="saved",
                      days_snapshot={})
    session.add(program)
    await session.commit()
    await activate_program(session, user, program.id)
    return program


async def update_program(session: AsyncSession, user: User, program_id: int,
                         changes: dict) -> Program:
    """Rename (empty name = default name) or change the number of weeks."""
    program = await _own_program(session, user.id, program_id)
    if "name" in changes:
        program.name = (changes["name"] or "").strip()
    if changes.get("weeks") is not None:
        program.weeks = changes["weeks"]
    await session.commit()
    return program


async def delete_program(session: AsyncSession, user: User, program_id: int) -> None:
    program = await _own_program(session, user.id, program_id)
    if program.status == "current":
        raise ProgramError("program_is_current")
    await session.delete(program)
    await session.commit()


async def reset_program(session: AsyncSession, user: User, program_id: int) -> None:
    """Back to the default days for this program (the editor's "Reset to default")."""
    current, _plan = await ensure_current(session, user)
    program = await _own_program(session, user.id, program_id)
    if program.id == current.id:
        await generate_for_user(session, user)
        return
    catalog = await load_catalog(session)
    program.days_snapshot = _generated_snapshot(user, program.workouts_per_week, program.goal, catalog)
    await session.commit()


# ---------- split editor (current program) ----------

def _find_day(plan: WorkoutPlan, day_id: int) -> PlanDay:
    for day in plan.days:
        if day.id == day_id:
            return day
    raise ProgramError("no_day", 404)


def _find_entry(plan: WorkoutPlan, entry_id: int) -> tuple[PlanDay, PlanExercise]:
    for day in plan.days:
        for entry in day.exercises:
            if entry.id == entry_id:
                return day, entry
    raise ProgramError("no_plan_exercise", 404)


def _renumber(items: list, attr: str) -> None:
    for i, item in enumerate(sorted(items, key=lambda x: getattr(x, attr))):
        setattr(item, attr, i)


def _move(items: list, item, position: int, attr: str) -> None:
    ordered = sorted(items, key=lambda x: getattr(x, attr))
    ordered.remove(item)
    ordered.insert(max(0, min(position, len(ordered))), item)
    for i, x in enumerate(ordered):
        setattr(x, attr, i)


async def add_day(session: AsyncSession, user: User, title: str | None) -> None:
    """A new day at the end, already filled with default full-body exercises."""
    program, plan = await ensure_current(session, user)
    if len(plan.days) >= rules.MAX_DAYS:
        raise ProgramError("too_many_days")
    catalog = await load_catalog(session)
    spec = generate_plan(list(catalog.values()), UserFilter.from_profile(user.profile), 2)
    rules.apply_goal(spec, program.goal, catalog)
    source = spec.days[0]
    day = PlanDay(day_index=len(plan.days), name_key=source.name_key, suffix="",
                  title=(title or "").strip() or None)
    for position, item in enumerate(source.exercises):
        day.exercises.append(make_entry(position, catalog[item.exercise_id], item.sets, item.rep_min,
                                        item.rep_max, item.timed, item.rest_seconds))
    plan.days.append(day)
    program.workouts_per_week = len(plan.days)
    await session.commit()


async def update_day(session: AsyncSession, user: User, day_id: int, changes: dict) -> None:
    """Rename (empty = default name) and/or move a day to another position."""
    _program, plan = await ensure_current(session, user)
    day = _find_day(plan, day_id)
    if "title" in changes:
        day.title = (changes["title"] or "").strip() or None
    if changes.get("position") is not None:
        _move(plan.days, day, changes["position"], "day_index")
    await session.commit()


async def delete_day(session: AsyncSession, user: User, day_id: int) -> None:
    program, plan = await ensure_current(session, user)
    day = _find_day(plan, day_id)
    if len(plan.days) <= 1:
        raise ProgramError("last_day")
    plan.days.remove(day)
    _renumber(plan.days, "day_index")
    program.workouts_per_week = len(plan.days)
    await session.commit()


def _checked(sets: int, rep_min: int, rep_max: int, rest: int, timed: bool) -> None:
    error = rules.check_prescription(sets, rep_min, rep_max, rest, timed)
    if error:
        raise ProgramError(error, 422)


async def add_exercise(session: AsyncSession, user: User, day_id: int, exercise_id: str,
                       sets: int | None = None, rep_min: int | None = None,
                       rep_max: int | None = None) -> None:
    """Add an exercise from the library to a day (default sets/reps for the goal)."""
    program, plan = await ensure_current(session, user)
    day = _find_day(plan, day_id)
    catalog = await load_catalog(session)
    exercise = catalog.get(exercise_id)
    if exercise is None:
        raise ProgramError("no_exercise", 404)
    if any(e.exercise_id == exercise.id for e in day.exercises):
        raise ProgramError("already_in_day")
    if len(day.exercises) >= rules.MAX_EXERCISES_PER_DAY:
        raise ProgramError("too_many_exercises")
    base = rules.adjust_for_goal(prescription(exercise, UserFilter.from_profile(user.profile).experience),
                                 exercise, program.goal)
    new_sets = sets if sets is not None else base.sets
    low = rep_min if rep_min is not None else base.rep_min
    high = rep_max if rep_max is not None else base.rep_max
    if rep_max is None and low > high:   # only the minimum was given
        high = low
    if rep_min is None and low > high:   # only the maximum was given
        low = high
    _checked(new_sets, low, high, base.rest_seconds, base.timed)
    position = max((e.position for e in day.exercises), default=-1) + 1
    day.exercises.append(make_entry(position, exercise, new_sets, low, high, base.timed, base.rest_seconds))
    await session.commit()


async def update_exercise(session: AsyncSession, user: User, entry_id: int, changes: dict) -> None:
    """Change sets, reps or rest, or move the exercise within its day."""
    _program, plan = await ensure_current(session, user)
    day, entry = _find_entry(plan, entry_id)
    sets = changes.get("sets") if changes.get("sets") is not None else entry.sets
    low = changes.get("rep_min") if changes.get("rep_min") is not None else entry.rep_min
    high = changes.get("rep_max") if changes.get("rep_max") is not None else entry.rep_max
    rest = changes.get("rest_seconds") if changes.get("rest_seconds") is not None else entry.rest_seconds
    _checked(sets, low, high, rest, entry.timed)
    entry.sets, entry.rep_min, entry.rep_max, entry.rest_seconds = sets, low, high, rest
    if changes.get("position") is not None:
        _move(day.exercises, entry, changes["position"], "position")
    await session.commit()


async def delete_exercise(session: AsyncSession, user: User, entry_id: int) -> None:
    _program, plan = await ensure_current(session, user)
    day, entry = _find_entry(plan, entry_id)
    if len(day.exercises) <= 1:
        raise ProgramError("last_exercise")   # a day needs at least one exercise
    day.exercises.remove(entry)
    _renumber(day.exercises, "position")
    await session.commit()


async def substitute_exercise(session: AsyncSession, user: User, entry_id: int) -> None:
    """Swap using substitute_ids, filtered by the user's equipment, level and injuries."""
    _program, plan = await ensure_current(session, user)
    _day, entry = _find_entry(plan, entry_id)
    if await substitute_in_plan(session, user, entry) is None:
        raise ProgramError("no_substitute")


# ---------- calendar ----------

async def calendar(session: AsyncSession, user: User, year: int, month: int) -> dict:
    """
    One marker per day of the month:
    done (a workout was finished), planned (a training day from today on),
    missed (a past training day without a workout, since the program started),
    rest (not a training day), none (before the program started).
    """
    program, _plan = await ensure_current(session, user)
    settings = await session.get(ReminderSettings, user.id)
    tz = _zone(settings.timezone if settings else None)
    today = datetime.now(tz).date()
    first = date(year, month, 1)
    last = (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    since = datetime.combine(first - timedelta(days=1), time.min, tzinfo=timezone.utc)
    done = {f.astimezone(tz).date() for f, _ in await _finished_since(session, user.id, since)}
    weekdays = rules.training_weekdays(program.workouts_per_week,
                                       settings.workout_days if settings else None)
    start = program.started_on or today
    out = []
    day = first
    while day <= last:
        if day in done:
            status = "done"
        elif day.weekday() not in weekdays:
            status = "rest"
        elif day >= today:
            status = "planned"
        elif day >= start:
            status = "missed"
        else:
            status = "none"
        out.append({"date": day.isoformat(), "status": status})
        day += timedelta(days=1)
    counts = {s: sum(1 for d in out if d["status"] == s) for s in ("done", "planned", "missed", "rest")}
    return {"month": f"{year:04d}-{month:02d}", "today": today.isoformat(), "weekdays": weekdays,
            "days": out, "counts": counts}
