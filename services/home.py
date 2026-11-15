"""
Home tab (Stage 7): everything the first screen shows, in one call.

- part of day for the greeting (in the user's time zone from reminder settings)
- the next workout of the current program (or the one in progress)
- this week (Mon-Sun): which days you trained, workouts vs goal, sets, volume, PRs, minutes
- today's calories and protein vs targets (food is logged in the chat until the nutrition stage)
- latest body weight
"""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BodyWeightLog, MealLog, User, WorkoutSession
from services import achievements, programs, reminders, workouts
from services import program_rules as rules
from services.body import aware
from services.nutrition import targets_for_profile


def part_of_day(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "night"


def _is_timed(ws: WorkoutSession, exercise_id: str) -> bool:
    return any(i["exercise_id"] == exercise_id and i["timed"] for i in ws.items)


async def _week(session: AsyncSession, user: User, settings, today: date) -> dict:
    start = today - timedelta(days=today.weekday())
    since = datetime.now(timezone.utc) - timedelta(days=8)   # a little extra; filtered by local date below
    rows = await session.scalars(
        select(WorkoutSession).where(WorkoutSession.user_id == user.id,
                                     WorkoutSession.finished_at.is_not(None),
                                     WorkoutSession.finished_at >= since))
    trained: set[date] = set()
    sets = prs = minutes = 0
    volume = 0.0
    for ws in rows:
        day = reminders.local_now(settings, aware(ws.finished_at)).date()
        if day < start:
            continue
        trained.add(day)
        working = [s for s in ws.sets if not s.warmup]
        sets += len(working)
        prs += sum(1 for s in working if s.pr)
        volume += sum(s.weight_kg * s.reps for s in working if not _is_timed(ws, s.exercise_id))
        minutes += max(1, round((aware(ws.finished_at) - aware(ws.started_at)).total_seconds() / 60))
    days = [start + timedelta(days=i) for i in range(7)]
    return {
        "start": start.isoformat(),
        "days": [{"date": d.isoformat(), "trained": d in trained, "today": d == today} for d in days],
        "sets": sets, "volume_kg": round(volume), "prs": prs, "minutes": minutes,
    }


async def _next_workout(session: AsyncSession, user: User) -> tuple[dict | None, dict | None]:
    active = await workouts.get_active(session, user)
    _program, plan = await programs.ensure_current(session, user)
    days = sorted(plan.days, key=lambda d: d.day_index)
    if not days:
        return None, None
    index = active.day_index if active is not None and active.day_index is not None \
        else await workouts.next_day_index(session, user, plan)
    day = next((d for d in days if d.day_index == index), days[0])
    entries = sorted(day.exercises, key=lambda e: e.position)
    muscles: list[str] = []
    for e in entries:
        group = e.exercise.muscle_group if e.exercise else None
        if group and group not in muscles:
            muscles.append(group)
    nxt = {
        "index": day.day_index, "name_key": day.name_key, "suffix": day.suffix, "title": day.title,
        "exercises": len(entries),
        "minutes": rules.estimate_minutes((e.sets, e.rep_max, e.timed, e.rest_seconds) for e in entries),
        "muscles": muscles[:4],
        "names": [e.exercise.name for e in entries[:3] if e.exercise],
    }
    live = None
    if active is not None:
        live = {"id": active.id,
                "done_sets": sum(len(workouts.sets_for(active, i["exercise_id"])) for i in active.items),
                "planned_sets": sum(i["sets"] for i in active.items),
                "name_key": active.name_key, "suffix": active.suffix}
    return nxt, live


async def home_view(session: AsyncSession, user: User) -> dict:
    settings = await reminders.get_settings(session, user)
    now = reminders.local_now(settings)
    today = now.date()
    stats = await achievements.compute_stats(session, user)
    week = await _week(session, user, settings, today)
    week.update({"done": stats.week_done, "goal": stats.week_goal, "streak_weeks": stats.week_streak})
    nxt, live = await _next_workout(session, user)

    targets = targets_for_profile(user.profile)
    eaten = (await session.execute(
        select(func.coalesce(func.sum(MealLog.kcal), 0), func.coalesce(func.sum(MealLog.protein_g), 0))
        .where(MealLog.user_id == user.id, MealLog.day == today))).one()
    weight = await session.scalar(
        select(BodyWeightLog).where(BodyWeightLog.user_id == user.id)
        .order_by(BodyWeightLog.logged_at.desc()).limit(1))
    return {
        "part_of_day": part_of_day(now.hour),
        "today": today.isoformat(),
        "week": week,
        "next_workout": nxt,
        "active": live,
        "nutrition": {"calories": int(eaten[0]), "calories_target": targets.calories,
                      "protein_g": round(float(eaten[1])), "protein_target": round(targets.protein_g)},
        "weight": {"kg": weight.weight_kg if weight else user.profile.weight_kg,
                   "logged_at": aware(weight.logged_at).isoformat() if weight else None},
    }
