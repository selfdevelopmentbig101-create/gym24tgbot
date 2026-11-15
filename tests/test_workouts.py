import asyncio
from datetime import timedelta

import pytest

from database.models import WorkoutSession, utcnow
from services import plans, users, workouts
from services.exercise_import import import_exercises, load_exercises_file
from services.rest_timer import RestTimers

PROFILE = {
    "goal": "lean_bulk", "age": 27, "sex": "male", "height_cm": 180, "weight_kg": 75,
    "experience": "intermediate", "training_days": 4, "equipment": "full_gym",
    "injuries": [], "diet": "none",
}


async def setup_user(session, telegram_id=1):
    await import_exercises(session, load_exercises_file())
    user = await users.get_or_create_user(session, telegram_id)
    await users.save_profile(session, user, PROFILE)
    plan = await plans.generate_for_user(session, user)
    return user, plan


async def test_full_session_history_and_suggestions(session_factory):
    async with session_factory() as s:
        user, plan = await setup_user(s)
        assert await workouts.next_day_index(s, user, plan) == 0

        ws = await workouts.start(s, user, plan, 0)
        first = ws.items[0]
        assert first["exercise_id"] == "bench-press"
        assert (ws.draft_weight, ws.draft_reps) == (20.0, 6)   # first time: empty bar

        await workouts.adjust_draft(s, ws, weight_delta=40, reps_delta=4)   # 60 kg x 10
        for _ in range(3):
            await workouts.log_set(s, user, ws)
        assert [x.set_number for x in workouts.sets_for(ws, "bench-press")] == [1, 2, 3]
        assert workouts.item_done(ws, 0)

        summary = await workouts.finish(s, user, ws)
        assert summary.total_sets == 3 and summary.volume_kg == 1800
        assert summary.exercises[0].next_time.kind == "add_weight"
        assert await workouts.next_day_index(s, user, plan) == 1

        # Next bench workout: last time is shown and the draft is pre-filled with +2.5 kg.
        ws2 = await workouts.start(s, user, plan, 2)
        index = await workouts.add_exercise(s, user, ws2, await s.get(workouts.Exercise, "bench-press"))
        await workouts.enter_exercise(s, user, ws2, index)
        hint, previous = await workouts.suggestion_for(s, user, ws2, index)
        assert [p.reps for p in previous] == [10, 10, 10]
        assert (ws2.draft_weight, ws2.draft_reps) == (62.5, 6)

        same = await workouts.same_as_last_time(s, user, ws2)
        assert (same.weight_kg, same.reps) == (60, 10)


async def test_undo_swap_and_validation(session_factory):
    async with session_factory() as s:
        user, plan = await setup_user(s)
        ws = await workouts.start(s, user, plan, 0)

        assert await workouts.undo_last(s, ws) is None
        original = ws.items[0]["exercise_id"]
        sub = await workouts.swap_current(s, user, ws)
        assert sub is not None and ws.items[0]["exercise_id"] == sub.id != original

        await workouts.log_set(s, user, ws, 50, 8)
        with pytest.raises(workouts.LogError):
            await workouts.swap_current(s, user, ws)     # can't swap after logging
        with pytest.raises(workouts.LogError):
            await workouts.log_set(s, user, ws, 600, 8)
        with pytest.raises(workouts.LogError):
            await workouts.log_set(s, user, ws, 50, 0)

        await workouts.enter_exercise(s, user, ws, 1)
        removed = await workouts.undo_last(s, ws)
        assert (removed.weight_kg, removed.reps) == (50, 8)
        assert ws.current_index == 0 and not ws.sets


async def test_empty_workout_is_discarded_and_stale_one_closed(session_factory):
    async with session_factory() as s:
        user, plan = await setup_user(s)
        ws = await workouts.start(s, user, plan, 0)
        assert await workouts.finish(s, user, ws) is None
        assert await workouts.get_active(s, user) is None

        ws = await workouts.start(s, user, plan, 1)
        await workouts.log_set(s, user, ws, 40, 8)
        ws.started_at = utcnow() - timedelta(hours=13)
        await s.commit()
        assert await workouts.get_active(s, user) is None      # auto-finished
        assert (await s.get(WorkoutSession, ws.id)).finished_at is not None


async def test_starting_a_new_workout_closes_the_old_one(session_factory):
    async with session_factory() as s:
        user, plan = await setup_user(s)
        old = await workouts.start(s, user, plan, 0)
        await workouts.log_set(s, user, old, 40, 8)
        new = await workouts.start(s, user, plan, 1)
        assert old.finished_at is not None and (await workouts.get_active(s, user)).id == new.id


async def test_deleting_user_removes_workouts(session_factory):
    from sqlalchemy import func, select
    from database.models import SetLog
    async with session_factory() as s:
        user, plan = await setup_user(s, telegram_id=99)
        ws = await workouts.start(s, user, plan, 0)
        await workouts.log_set(s, user, ws, 40, 8)
    async with session_factory() as s:
        await users.delete_user_data(s, 99)
        assert await s.scalar(select(func.count()).select_from(SetLog)) == 0
        assert await s.scalar(select(func.count()).select_from(WorkoutSession)) == 0


async def test_rest_timer_fires_restarts_and_cancels():
    timers = RestTimers(time_scale=0.001)
    fired = []

    async def done(tag):
        fired.append(tag)

    timers.start(1, 100, lambda: done("a"))
    timers.start(1, 100, lambda: done("b"))   # restart replaces the first timer
    assert timers.remaining(1) == 100
    await timers.wait(1)
    timers.start(2, 100, lambda: done("c"))
    assert timers.cancel(2) is True
    await asyncio.sleep(0.2)
    assert fired == ["b"] and timers.remaining(1) is None
