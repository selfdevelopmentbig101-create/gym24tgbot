from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from database.models import Achievement, BodyWeightLog, SetLog, WorkoutSession
from services import achievements, adjust, plans, users, workouts
from services.achievements import daily_streak, weekly_streak
from services.exercise_import import import_exercises, load_exercises_file
from services.nutrition import calculate_targets, targets_for_profile

PROFILE = {
    "goal": "lean_bulk", "age": 27, "sex": "male", "height_cm": 180, "weight_kg": 80,
    "experience": "intermediate", "training_days": 3, "equipment": "full_gym",
    "injuries": [], "diet": "none",
}
MON = date(2026, 11, 9)  # a Monday


async def setup_user(session, telegram_id=1):
    await import_exercises(session, load_exercises_file())
    user = await users.get_or_create_user(session, telegram_id)
    await users.save_profile(session, user, PROFILE)
    plan = await plans.generate_for_user(session, user)
    return user, plan


# ---------- Streak maths ----------

def test_weekly_streak_counts_full_weeks_and_keeps_current_week_alive():
    week1 = [MON - timedelta(days=14), MON - timedelta(days=12), MON - timedelta(days=10)]
    week2 = [MON - timedelta(days=7), MON - timedelta(days=5), MON - timedelta(days=3)]
    # This week only 1 of 3 so far: streak is still the 2 previous weeks.
    assert weekly_streak(week1 + week2 + [MON], MON + timedelta(days=1), 3) == (2, 1)
    # This week done too.
    this_week = [MON, MON + timedelta(days=2), MON + timedelta(days=4)]
    assert weekly_streak(week1 + week2 + this_week, MON + timedelta(days=5), 3) == (3, 3)
    # A short week breaks it.
    assert weekly_streak(week1 + week2[:2], MON, 3) == (0, 0)


def test_daily_protein_streak():
    today = date(2026, 11, 14)
    days = {today - timedelta(days=i): 170 for i in range(1, 5)}
    assert daily_streak(days, today, 160) == 4                  # today not hit yet: still alive
    assert daily_streak({**days, today: 165}, today, 160) == 5
    assert daily_streak({**days, today - timedelta(days=2): 100}, today, 160) == 1


# ---------- Achievements ----------

async def test_achievements_unlock_once_and_survive_deletion_cascade(session_factory):
    async with session_factory() as s:
        user, plan = await setup_user(s, telegram_id=31)
        assert await achievements.check_new(s, user) == []
        ws = await workouts.start(s, user, plan, 0)
        await workouts.log_set(s, user, ws, 60, 8)
        await workouts.log_set(s, user, ws, 62.5, 8)     # a PR
        await workouts.finish(s, user, ws)
        codes = [a.code for a in await achievements.check_new(s, user)]
        assert codes == ["first_workout", "first_pr"]
        assert await achievements.check_new(s, user) == []   # not unlocked twice
        stats = await achievements.compute_stats(s, user)
        assert (stats.workouts, stats.prs, stats.week_done, stats.week_goal) == (1, 1, 1, 3)
    async with session_factory() as s:
        await users.delete_user_data(s, 31)
        assert (await s.scalars(select(Achievement))).first() is None


# ---------- Calories ----------

def test_calorie_adjust_is_added_but_floor_still_applies():
    base = calculate_targets(weight_kg=80, height_cm=180, age=30, sex="male", training_days=4,
                             goal="lean_bulk")
    up = calculate_targets(weight_kg=80, height_cm=180, age=30, sex="male", training_days=4,
                           goal="lean_bulk", calorie_adjust=150)
    assert up.calories == base.calories + 150
    low = calculate_targets(weight_kg=50, height_cm=160, age=60, sex="female", training_days=2,
                            goal="recomp", calorie_adjust=-300)
    assert low.calories >= low.bmr - 5


async def add_weights(session, user, now, pairs):
    for days_ago, kg in pairs:
        session.add(BodyWeightLog(user_id=user.id, weight_kg=kg, logged_at=now - timedelta(days=days_ago)))
    await session.commit()


async def test_calorie_suggestion_after_two_slow_weeks(session_factory):
    async with session_factory() as s:
        user, _ = await setup_user(s)
        now = datetime.now(timezone.utc)
        assert await adjust.calorie_suggestion(s, user, now) is None
        # Flat weight for 3 weeks: lean bulk wants ~0.08-0.2 kg/week.
        await add_weights(s, user, now, [(d, 80.0) for d in (1, 4, 8, 11, 15, 18)])
        suggestion = await adjust.calorie_suggestion(s, user, now)
        assert suggestion.delta == 150
        before = targets_for_profile(user.profile).calories
        assert await adjust.apply_calories(s, user, 150) == before + 150
        assert await adjust.calorie_suggestion(s, user, now) is None      # cooldown

        # Changing goal resets the tweak.
        await users.update_profile_field(s, user, "goal", "bulk")
        assert user.profile.calorie_adjust == 0


async def test_calorie_suggestion_respects_limits_and_fast_gain(session_factory):
    async with session_factory() as s:
        user, _ = await setup_user(s)
        now = datetime.now(timezone.utc)
        await add_weights(s, user, now, [(18, 79.0), (15, 79.0), (11, 79.8), (8, 79.8),
                                         (4, 80.6), (1, 80.6)])        # +0.8 kg/week
        assert (await adjust.calorie_suggestion(s, user, now)).delta == -150
        user.profile.calorie_adjust = -300                            # already at the limit
        await s.commit()
        assert await adjust.calorie_suggestion(s, user, now) is None
        with pytest.raises(ValueError):
            await adjust.apply_calories(s, user, 500)


# ---------- Deload ----------

async def log_bench(session, user, plan, weight, reps, days_ago):
    ws = await workouts.start(session, user, plan, 0)
    for _ in range(3):
        await workouts.log_set(session, user, ws, weight, reps)
    await workouts.finish(session, user, ws)
    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    ws.started_at = ws.finished_at = when
    for row in ws.sets:
        row.created_at = when
    await session.commit()


async def test_deload_suggested_when_two_lifts_stall_and_applied(session_factory):
    async with session_factory() as s:
        user, plan = await setup_user(s)
        first, second = plan.days[0].exercises[0].exercise_id, plan.days[0].exercises[1].exercise_id
        assert await adjust.deload_suggestion(s, user) is None

        # Two exercises, 5 sessions each, best set never improves after the 2nd session.
        for days_ago, reps in ((20, 6), (16, 8), (12, 8), (8, 7), (4, 8)):
            ws = await workouts.start(s, user, plan, 0)
            for index in (0, 1):
                await workouts.enter_exercise(s, user, ws, index)
                await workouts.log_set(s, user, ws, 60, reps)
            await workouts.finish(s, user, ws)
            when = datetime.now(timezone.utc) - timedelta(days=days_ago)
            ws.started_at = ws.finished_at = when
            for row in ws.sets:
                row.created_at = when
            await s.commit()

        stalled = await adjust.deload_suggestion(s, user)
        assert {e.id for e in stalled} == {first, second}

        until = await adjust.start_deload(s, user)
        assert until - date.today() <= timedelta(days=7)
        assert await adjust.deload_suggestion(s, user) is None         # active now

        ws = await workouts.start(s, user, plan, 0)
        assert ws.items[0]["sets"] == 2                                # 3 sets -> 2
        assert ws.draft_weight == 55.0                                 # 60 kg x 0.9 -> 55 (2.5 kg steps)
        hint, _ = await workouts.suggestion_for(s, user, ws, 0)
        assert hint.kind == "deload"
        await workouts.log_set(s, user, ws)
        summary = await workouts.finish(s, user, ws)
        assert all(ex.next_time is None for ex in summary.exercises)


async def test_no_deload_when_progressing(session_factory):
    async with session_factory() as s:
        user, plan = await setup_user(s)
        for days_ago, weight in ((20, 50), (16, 52.5), (12, 55), (8, 57.5), (4, 60)):
            await log_bench(s, user, plan, weight, 8, days_ago)
        assert await adjust.stalled_exercises(s, user) == []


def test_deload_maths():
    assert [adjust.deload_sets(n) for n in (2, 3, 4, 5)] == [2, 2, 2, 3]
    assert adjust.deload_weight(100) == 90 and adjust.deload_weight(62.5) == 55


async def test_counts_helpers(session_factory):
    from sqlalchemy import func, select
    async with session_factory() as s:
        user, plan = await setup_user(s)
        await log_bench(s, user, plan, 40, 10, 1)
        assert await s.scalar(select(func.count()).select_from(WorkoutSession)) == 1
        assert await s.scalar(select(func.count()).select_from(SetLog)) == 3
