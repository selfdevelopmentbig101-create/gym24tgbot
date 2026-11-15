"""Save, load and change workout plans in the database.

The plan is the CURRENT program's days (see services/programs.py). The bot, the
reminders and the workout logger read it exactly as before.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Exercise, PlanDay, PlanExercise, Program, User, WorkoutPlan
from services.exercises import UserFilter, load_catalog, pick_substitute
from services.plan_generator import PlanSpec, generate_plan
from services.program_rules import DEFAULT_GOAL, DEFAULT_WEEKS, apply_goal

logger = logging.getLogger(__name__)

# Changing any of these profile fields regenerates the plan.
PLAN_FIELDS = {"experience", "training_days", "equipment", "injuries"}


async def get_plan(session: AsyncSession, user: User) -> WorkoutPlan | None:
    return await session.scalar(select(WorkoutPlan).where(WorkoutPlan.user_id == user.id))


async def load_plan(session: AsyncSession, user_id: int) -> WorkoutPlan | None:
    """The plan freshly read from the database (use after edits in the same session)."""
    return await session.scalar(
        select(WorkoutPlan).where(WorkoutPlan.user_id == user_id)
        .execution_options(populate_existing=True)
    )


def make_entry(position: int, exercise: Exercise, sets: int, rep_min: int, rep_max: int,
               timed: bool, rest_seconds: int) -> PlanExercise:
    """One exercise in a plan day."""
    return PlanExercise(position=position, exercise_id=exercise.id, exercise=exercise, sets=sets,
                        rep_min=rep_min, rep_max=rep_max, timed=timed, rest_seconds=rest_seconds)


def plan_from_spec(user_id: int, spec: PlanSpec, catalog: dict[str, Exercise]) -> WorkoutPlan:
    """A generated plan (services/plan_generator.py) as database rows."""
    plan = WorkoutPlan(user_id=user_id, split=spec.split)
    for day_index, day in enumerate(spec.days):
        plan_day = PlanDay(day_index=day_index, name_key=day.name_key, suffix=day.suffix)
        for position, item in enumerate(day.exercises):
            plan_day.exercises.append(make_entry(
                position, catalog[item.exercise_id], item.sets, item.rep_min, item.rep_max,
                item.timed, item.rest_seconds))
        plan.days.append(plan_day)
    return plan


def plan_from_snapshot(user_id: int, snapshot: dict, catalog: dict[str, Exercise]) -> WorkoutPlan:
    """A saved program's days (programs.days_snapshot) as database rows."""
    plan = WorkoutPlan(user_id=user_id, split=snapshot.get("split") or "custom")
    for day_index, day in enumerate(snapshot.get("days") or []):
        plan_day = PlanDay(day_index=day_index, name_key=day.get("name_key") or "full_body",
                           suffix=day.get("suffix") or "", title=day.get("title"))
        position = 0
        for item in day.get("exercises") or []:
            exercise = catalog.get(item.get("exercise_id"))
            if exercise is None:  # removed from the exercise list since it was saved
                continue
            plan_day.exercises.append(make_entry(
                position, exercise, int(item["sets"]), int(item["rep_min"]), int(item["rep_max"]),
                bool(item.get("timed")), int(item["rest_seconds"])))
            position += 1
        plan.days.append(plan_day)
    return plan


async def generate_for_user(session: AsyncSession, user: User, days: int | None = None,
                            goal: str | None = None) -> WorkoutPlan | None:
    """
    Fresh days for the user's CURRENT program, replacing the old ones.
    Without a program yet, this creates the default program (days per week from
    the profile). A default program follows the profile's training days; a
    created or built-in program keeps its own number of days and its goal.
    """
    if user.profile is None:
        raise ValueError("User has no profile")
    catalog = await load_catalog(session)
    if not catalog:
        logger.error("No exercises in the database; run import_exercises.py")
        return None

    program = await session.scalar(
        select(Program).where(Program.user_id == user.id, Program.status == "current")
        .order_by(Program.id.desc()))
    if days is None:
        own_days = program is not None and program.kind != "default"
        days = program.workouts_per_week if own_days else user.profile.training_days
    if goal is None:
        goal = program.goal if program is not None else DEFAULT_GOAL

    spec = generate_plan(list(catalog.values()), UserFilter.from_profile(user.profile), days)
    apply_goal(spec, goal, catalog)

    await session.execute(delete(WorkoutPlan).where(WorkoutPlan.user_id == user.id))
    plan = plan_from_spec(user.id, spec, catalog)
    session.add(plan)
    if program is None:
        session.add(Program(
            user_id=user.id, name="", kind="default", goal=goal, weeks=DEFAULT_WEEKS,
            workouts_per_week=len(spec.days), status="current",
            started_on=datetime.now(timezone.utc).date(), days_snapshot={}))
    else:
        program.workouts_per_week = len(spec.days)
    await session.commit()
    logger.info("Plan generated (%s, %s days, %s)", spec.split, len(spec.days), goal)
    # Reload so plan.days[...].exercises[...].exercise are all populated.
    session.expunge(plan)
    return await get_plan(session, user)


async def get_or_create_plan(session: AsyncSession, user: User) -> WorkoutPlan | None:
    return await get_plan(session, user) or await generate_for_user(session, user)


async def get_plan_exercise(session: AsyncSession, user: User,
                            plan_exercise_id: int) -> PlanExercise | None:
    """A plan entry, only if it belongs to this user's current plan."""
    return await session.scalar(
        select(PlanExercise)
        .join(PlanDay, PlanExercise.day_id == PlanDay.id)
        .join(WorkoutPlan, PlanDay.plan_id == WorkoutPlan.id)
        .where(PlanExercise.id == plan_exercise_id, WorkoutPlan.user_id == user.id)
        # Load the whole day (needed for Next and position), avoiding lazy loads.
        .options(selectinload(PlanExercise.day).selectinload(PlanDay.exercises)
                 .selectinload(PlanExercise.exercise))
    )


async def substitute_in_plan(session: AsyncSession, user: User,
                             entry: PlanExercise) -> PlanExercise | None:
    """Swap a plan entry for a suitable substitute. Returns None if there's none."""
    catalog = await load_catalog(session)
    current = catalog.get(entry.exercise_id) or entry.exercise
    day = await session.get(PlanDay, entry.day_id)
    in_day = {e.exercise_id for e in day.exercises}
    substitute = pick_substitute(current, catalog, UserFilter.from_profile(user.profile),
                                 exclude_ids=in_day)
    if substitute is None:
        return None
    entry.exercise_id = substitute.id
    entry.exercise = substitute
    await session.commit()
    logger.info("Plan exercise substituted")
    return entry
