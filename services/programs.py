"""
Program editing (Mini App Plan tab): create, rename, days, exercises, activate,
reset, plus the calendar and the training-load ("energy") check.
Validation lives here so every caller gets the same rules.
"""
import logging
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Exercise, PlanDay, PlanExercise, User, WorkoutPlan, WorkoutSession
from services import plans
from services.exercises import UserFilter, load_catalog, pick_substitute
from services.plan_generator import TRAINING_GOALS, prescription
from services.reminders import DEFAULT_WORKOUT_DAYS, get_settings, parse_tz

logger = logging.getLogger(__name__)

NAME_MAX = 40
DAY_NAME_MAX = 30
WEEKS_RANGE = (1, 52)
DAYS_RANGE = (1, 7)
EXERCISES_PER_DAY_MAX = 12
SETS_RANGE = (1, 10)
REPS_RANGE = (1, 100)
SECONDS_RANGE = (5, 600)   # timed exercises: reps are seconds
REST_RANGE = (0, 600)


class ProgramError(ValueError):
    """A rule was broken. `code` is shown to the app (and translated there)."""

    def __init__(self, code: str, status: int = 422):
        super().__init__(code)
        self.code, self.status = code, status


def clean_name(value: str, limit: int) -> str:
    """Trim, collapse spaces, drop control characters. Raises if empty or too long."""
    text = "".join(ch for ch in str(value) if unicodedata.category(ch)[0] != "C")
    text = " ".join(text.split())
    if not text:
        raise ProgramError("name_empty")
    if len(text) > limit:
        raise ProgramError("name_too_long")
    return text


def _check(value: int, bounds: tuple[int, int], code: str) -> int:
    if not bounds[0] <= value <= bounds[1]:
        raise ProgramError(code)
    return value


def _edited(program: WorkoutPlan) -> None:
    program.edited = True


def _renumber(days: list[PlanDay]) -> None:
    for index, day in enumerate(days):
        day.day_index = index


# ---------- Programs ----------

async def create_custom(session: AsyncSession, user: User, name: str, weeks: int,
                        workouts_per_week: int, goal: str, activate: bool) -> WorkoutPlan:
    """A program with empty days ("Day 1".."Day N") the user fills from the library."""
    if goal not in TRAINING_GOALS:
        raise ProgramError("bad_goal")
    program = WorkoutPlan(
        user_id=user.id, split="custom", kind="custom", name=clean_name(name, NAME_MAX),
        weeks=_check(weeks, WEEKS_RANGE, "bad_weeks"), goal=goal, is_current=False,
        days=[PlanDay(day_index=i, name_key="custom", suffix=str(i + 1), exercises=[])
              for i in range(_check(workouts_per_week, DAYS_RANGE, "bad_days"))],
    )
    session.add(program)
    await session.flush()
    if activate:
        await plans.make_current(session, user, program)
    await session.commit()
    logger.info("Custom program created (%s days)", workouts_per_week)
    return await reload(session, program)


async def create_from_template(session: AsyncSession, user: User, days: int, goal: str,
                               weeks: int, name: str | None, activate: bool) -> WorkoutPlan:
    if days not in plans.TEMPLATE_DAYS:
        raise ProgramError("bad_template", 404)
    if goal not in TRAINING_GOALS:
        raise ProgramError("bad_goal")
    program = WorkoutPlan(user_id=user.id, split="", goal=goal, is_current=False, days=[],
                          weeks=_check(weeks, WEEKS_RANGE, "bad_weeks"),
                          name=clean_name(name, NAME_MAX) if name else None)
    if not await plans._fill_from_template(session, user, program, days):
        raise ProgramError("no_exercises", 503)
    session.add(program)
    await session.flush()
    if activate:
        await plans.make_current(session, user, program)
    await session.commit()
    logger.info("Program created from the %s-day template", days)
    return await reload(session, program)


async def reload(session: AsyncSession, program: WorkoutPlan) -> WorkoutPlan:
    return await plans._reload(session, program)


async def update_program(session: AsyncSession, program: WorkoutPlan, user: User, *,
                         name: str | None = None, clear_name: bool = False,
                         weeks: int | None = None, goal: str | None = None) -> WorkoutPlan:
    if clear_name:
        program.name = None
    elif name is not None:
        program.name = clean_name(name, NAME_MAX)
    if weeks is not None:
        program.weeks = _check(weeks, WEEKS_RANGE, "bad_weeks")
    if goal is not None and goal != program.goal:
        if goal not in TRAINING_GOALS:
            raise ProgramError("bad_goal")
        program.goal = goal
        # New training style: sets, reps and rest follow it for every exercise.
        experience = UserFilter.from_profile(user.profile).experience
        for day in program.days:
            for item in day.exercises:
                _apply(item, prescription(item.exercise, experience, goal))
    await session.commit()
    return await reload(session, program)


def _apply(item: PlanExercise, p) -> None:
    item.sets, item.rep_min, item.rep_max, item.timed, item.rest_seconds = \
        p.sets, p.rep_min, p.rep_max, p.timed, p.rest_seconds


async def activate(session: AsyncSession, user: User, program: WorkoutPlan) -> WorkoutPlan:
    if not any(day.exercises for day in program.days):
        raise ProgramError("program_empty", 409)
    if not program.is_current:
        program.started_on = None  # a fresh start
    await plans.make_current(session, user, program)
    await session.commit()
    logger.info("Program activated")
    return await reload(session, program)


async def reset(session: AsyncSession, user: User, program: WorkoutPlan) -> WorkoutPlan:
    """Rebuild a template program from its template for the current profile."""
    if program.kind != "template" or not program.template_days:
        raise ProgramError("not_a_template", 409)
    if not await plans._fill_from_template(session, user, program, program.template_days):
        raise ProgramError("no_exercises", 503)
    await session.commit()
    logger.info("Program reset to its template")
    return await reload(session, program)


async def delete_program(session: AsyncSession, program: WorkoutPlan) -> None:
    if program.is_current:
        raise ProgramError("current_program", 409)
    await session.delete(program)
    await session.commit()


# ---------- Days ----------

async def add_day(session: AsyncSession, program: WorkoutPlan, name: str | None) -> PlanDay:
    if len(program.days) >= DAYS_RANGE[1]:
        raise ProgramError("too_many_days", 409)
    index = len(program.days)
    day = (PlanDay(day_index=index, name_key="~" + clean_name(name, DAY_NAME_MAX), suffix="", exercises=[])
           if name else PlanDay(day_index=index, name_key="custom", suffix=str(index + 1), exercises=[]))
    program.days.append(day)
    _edited(program)
    await session.commit()
    return day


async def update_day(session: AsyncSession, program: WorkoutPlan, day: PlanDay, *,
                     name: str | None = None, position: int | None = None) -> None:
    if name is not None:
        day.name_key, day.suffix = "~" + clean_name(name, DAY_NAME_MAX), ""
    if position is not None:
        days = list(program.days)
        _check(position, (0, len(days) - 1), "bad_position")
        days.remove(day)
        days.insert(position, day)
        _renumber(days)
    _edited(program)
    await session.commit()


async def delete_day(session: AsyncSession, program: WorkoutPlan, day: PlanDay) -> None:
    if len(program.days) <= DAYS_RANGE[0]:
        raise ProgramError("last_day", 409)
    program.days.remove(day)
    _renumber(program.days)
    _edited(program)
    await session.commit()


# ---------- Exercises in a day ----------

async def add_exercise(session: AsyncSession, user: User, program: WorkoutPlan, day: PlanDay,
                       exercise_id: str) -> PlanExercise:
    exercise = (await load_catalog(session)).get(exercise_id)
    if exercise is None:
        raise ProgramError("no_exercise", 404)
    if any(item.exercise_id == exercise_id for item in day.exercises):
        raise ProgramError("already_in_day", 409)
    if len(day.exercises) >= EXERCISES_PER_DAY_MAX:
        raise ProgramError("day_full", 409)
    p = prescription(exercise, UserFilter.from_profile(user.profile).experience, program.goal)
    item = PlanExercise(position=len(day.exercises), exercise_id=exercise.id, exercise=exercise,
                        sets=p.sets, rep_min=p.rep_min, rep_max=p.rep_max, timed=p.timed,
                        rest_seconds=p.rest_seconds)
    day.exercises.append(item)
    _edited(program)
    await session.commit()
    return item


async def update_exercise(session: AsyncSession, program: WorkoutPlan, day: PlanDay,
                          item: PlanExercise, changes: dict) -> None:
    sets = changes.get("sets", item.sets)
    rep_min = changes.get("rep_min", item.rep_min)
    rep_max = changes.get("rep_max", item.rep_max)
    rest = changes.get("rest_seconds", item.rest_seconds)
    _check(sets, SETS_RANGE, "bad_sets")
    bounds = SECONDS_RANGE if item.timed else REPS_RANGE
    _check(rep_min, bounds, "bad_reps")
    _check(rep_max, bounds, "bad_reps")
    if rep_min > rep_max:
        raise ProgramError("bad_reps")
    _check(rest, REST_RANGE, "bad_rest")
    item.sets, item.rep_min, item.rep_max, item.rest_seconds = sets, rep_min, rep_max, rest
    if "position" in changes:
        items = list(day.exercises)
        _check(changes["position"], (0, len(items) - 1), "bad_position")
        items.remove(item)
        items.insert(changes["position"], item)
        for position, entry in enumerate(items):
            entry.position = position
        day.exercises.sort(key=lambda e: e.position)
    _edited(program)
    await session.commit()


async def delete_exercise(session: AsyncSession, program: WorkoutPlan, day: PlanDay,
                          item: PlanExercise) -> None:
    day.exercises.remove(item)
    for position, entry in enumerate(day.exercises):
        entry.position = position
    _edited(program)
    await session.commit()


async def substitute(session: AsyncSession, user: User, program: WorkoutPlan, day: PlanDay,
                     item: PlanExercise, exercise_id: str | None) -> PlanExercise:
    """Swap for `exercise_id`, or for the best substitute for the user's equipment and injuries."""
    catalog = await load_catalog(session)
    in_day = {e.exercise_id for e in day.exercises}
    if exercise_id is not None:
        new = catalog.get(exercise_id)
        if new is None:
            raise ProgramError("no_exercise", 404)
        if exercise_id in in_day:
            raise ProgramError("already_in_day", 409)
    else:
        current = catalog.get(item.exercise_id) or item.exercise
        new = pick_substitute(current, catalog, UserFilter.from_profile(user.profile), exclude_ids=in_day)
        if new is None:
            raise ProgramError("no_substitute", 409)
    item.exercise_id, item.exercise = new.id, new
    if exercise_id is not None:
        _edited(program)  # a hand-picked exercise is the user's choice; keep it
    await session.commit()
    return item


# ---------- Program progress ----------

@dataclass(frozen=True)
class Progress:
    week: int | None          # 1-based week of the program (None = not started)
    ends_on: date | None
    completed: int            # workouts finished since the start
    total: int                # weeks x workouts per week
    next_day_index: int | None


async def progress(session: AsyncSession, user: User, program: WorkoutPlan,
                   today: date | None = None) -> Progress:
    today = today or date.today()
    total = program.weeks * max(len(program.days), 1)
    if not program.is_current or program.started_on is None:
        return Progress(None, None, 0, total, None)
    start = program.started_on
    week = min(program.weeks, max(1, (today - start).days // 7 + 1))
    since = datetime.combine(start, time.min, tzinfo=timezone.utc)
    completed = await session.scalar(
        select(func.count(WorkoutSession.id)).where(
            WorkoutSession.user_id == user.id, WorkoutSession.finished_at.is_not(None),
            WorkoutSession.finished_at >= since)) or 0
    from services.workouts import next_day_index  # avoid an import cycle
    nxt = await next_day_index(session, user, program) if program.days else None
    return Progress(week, start + timedelta(days=program.weeks * 7 - 1), min(completed, total), total, nxt)


# ---------- Calendar ----------

@dataclass(frozen=True)
class CalendarDay:
    day: date
    status: str  # "done", "missed", "planned", "rest"


async def calendar(session: AsyncSession, user: User, year: int, month: int,
                   now: datetime | None = None) -> tuple[list[CalendarDay], list[int]]:
    """
    Each day of the month: done (a workout finished that local day), missed (a scheduled
    day since the program started without one), planned (today or later) or rest.
    Scheduled weekdays: the reminder days if set, else a default for workouts per week.
    """
    settings = await get_settings(session, user)
    tz = parse_tz(settings.timezone) if settings else parse_tz("UTC")
    today = (now or datetime.now(tz)).astimezone(tz).date()
    program = await plans.get_plan(session, user)
    per_week = len(program.days) if program else 0
    if settings and settings.workout_days:
        schedule = sorted(set(settings.workout_days))
    else:
        schedule = DEFAULT_WORKOUT_DAYS.get(per_week, list(range(min(per_week, 7))))
    start = program.started_on if program and program.started_on else None

    first = date(year, month, 1)
    last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    rows = await session.scalars(select(WorkoutSession.finished_at).where(
        WorkoutSession.user_id == user.id, WorkoutSession.finished_at.is_not(None),
        WorkoutSession.finished_at >= datetime.combine(first - timedelta(days=1), datetime.min.time()),
        WorkoutSession.finished_at < datetime.combine(last + timedelta(days=2), datetime.min.time())))
    done = set()
    for finished in rows:
        if finished.tzinfo is None:
            finished = finished.replace(tzinfo=timezone.utc)
        done.add(finished.astimezone(tz).date())

    days = []
    for offset in range((last - first).days + 1):
        day = first + timedelta(days=offset)
        if day in done:
            status = "done"
        elif day.weekday() in schedule and day >= today and program is not None:
            status = "planned"
        elif day.weekday() in schedule and start is not None and start <= day < today:
            status = "missed"
        else:
            status = "rest"
        days.append(CalendarDay(day, status))
    return days, schedule


# ---------- Training load ----------

SESSION_MINUTES_HIGH = 90
SESSION_SETS_HIGH = 30
MUSCLE_SESSION_SETS_HIGH = 12
WEEKLY_SETS = (8, 20)       # weekly sets per muscle: below = low, above = high
WORK_SECONDS_PER_SET = 40
SECONDARY_SHARE = 0.5


@dataclass
class Load:
    sets: int = 0
    minutes: int = 0
    muscles: dict[str, float] = field(default_factory=dict)


def day_load(day: PlanDay) -> Load:
    load = Load()
    seconds = 0
    for item in day.exercises:
        ex: Exercise = item.exercise
        load.sets += item.sets
        work = (item.rep_min + item.rep_max) / 2 if item.timed else WORK_SECONDS_PER_SET
        seconds += item.sets * (work + item.rest_seconds)
        load.muscles[ex.muscle_group] = load.muscles.get(ex.muscle_group, 0) + item.sets
        for muscle in ex.secondary_muscles or []:
            load.muscles[muscle] = load.muscles.get(muscle, 0) + item.sets * SECONDARY_SHARE
    load.minutes = round(seconds / 60)
    return load


def energy(program: WorkoutPlan, day: PlanDay) -> dict:
    """The day's load, the week's sets per muscle, and warnings (never blocking)."""
    today = day_load(day)
    week: dict[str, float] = {}
    for other in program.days:
        for muscle, sets in day_load(other).muscles.items():
            week[muscle] = week.get(muscle, 0) + sets
    warnings = []
    if today.minutes > SESSION_MINUTES_HIGH:
        warnings.append({"key": "session_long", "value": today.minutes})
    if today.sets > SESSION_SETS_HIGH:
        warnings.append({"key": "session_many_sets", "value": today.sets})
    for muscle, sets in today.muscles.items():
        if sets > MUSCLE_SESSION_SETS_HIGH:
            warnings.append({"key": "muscle_session_high", "muscle": muscle, "value": sets})
    for muscle, sets in week.items():
        if sets > WEEKLY_SETS[1]:
            warnings.append({"key": "weekly_high", "muscle": muscle, "value": sets})

    def level(sets: float) -> str:
        return "low" if sets < WEEKLY_SETS[0] else "high" if sets > WEEKLY_SETS[1] else "ok"

    return {
        "day": {"sets": today.sets, "minutes": today.minutes,
                "muscles": [{"muscle": m, "sets": s} for m, s in
                            sorted(today.muscles.items(), key=lambda kv: -kv[1])]},
        "week": [{"muscle": m, "sets": s, "level": level(s)}
                 for m, s in sorted(week.items(), key=lambda kv: -kv[1])],
        "warnings": warnings,
    }
