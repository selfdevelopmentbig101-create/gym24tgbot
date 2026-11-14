from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from database.models import BodyWeightLog, ReminderSettings, WorkoutSession
from services import body, charts, plans, records, reminders, users, workouts
from services.exercise_import import import_exercises, load_exercises_file
from services.scheduler import ReminderScheduler
from services.validation import ValidationError

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


# ---------- 1RM and PRs ----------

def test_e1rm_epley():
    assert records.e1rm(100, 1) == 100
    assert records.e1rm(100, 10) == pytest.approx(133.33, abs=0.01)
    assert records.e1rm(100, 13) is None      # too many reps to be reliable
    assert records.e1rm(0, 10) is None        # bodyweight only


async def test_pr_detection_and_records(session_factory):
    async with session_factory() as s:
        user, plan = await setup_user(s)
        ws = await workouts.start(s, user, plan, 0)
        first = await workouts.log_set(s, user, ws, 60, 8)
        assert first.pr is False                       # first ever set is not a "PR"
        same = await workouts.log_set(s, user, ws, 60, 8)
        assert same.pr is False
        better = await workouts.log_set(s, user, ws, 62.5, 8)
        assert better.pr is True and better.previous_best == pytest.approx(76, abs=0.01)
        await workouts.finish(s, user, ws)

        prs = await records.personal_records(s, user)
        assert prs[0].exercise.id == "bench-press" and prs[0].best_weight == 62.5
        assert prs[0].heaviest_kg == 62.5
        history = await records.e1rm_history(s, user, "bench-press",
                                             datetime.now(timezone.utc) - timedelta(days=1))
        assert len(history) == 1 and history[0][1] == pytest.approx(79.17, abs=0.01)
        assert [e.id for e in await records.logged_exercises(s, user)] == ["bench-press"]


# ---------- Body weight and measurements ----------

async def test_weight_logging_updates_profile_and_trend(session_factory):
    async with session_factory() as s:
        user, _ = await setup_user(s)
        await body.log_weight(s, user, "76,2")
        assert user.profile.weight_kg == 76.2 and await body.last_weight(s, user) == 76.2
        with pytest.raises(ValidationError):
            await body.log_weight(s, user, "500")

        now = datetime.now(timezone.utc)
        for days_ago, kg in ((13, 75.0), (10, 75.2), (5, 75.4), (2, 75.6)):
            s.add(BodyWeightLog(user_id=user.id, weight_kg=kg, logged_at=now - timedelta(days=days_ago)))
        await s.commit()
        # last 7 days: 75.4, 75.6, 76.2 (avg 75.73); week before: 75.0, 75.2 (avg 75.1)
        assert await body.weekly_trend(s, user, now) == pytest.approx(0.63, abs=0.01)


@pytest.mark.parametrize("trend,target,expected", [
    (0.15, (0.08, 0.19), "on_track"), (0.0, (0.08, 0.19), "slow"), (0.5, (0.08, 0.19), "fast"),
    (0.1, (0.0, 0.0), "on_track"), (-0.5, (0.0, 0.0), "slow"),
])
def test_classify_trend(trend, target, expected):
    assert body.classify_trend(trend, target) == expected


async def test_measurements(session_factory):
    async with session_factory() as s:
        user, _ = await setup_user(s)
        await body.log_measurement(s, user, "waist", "82,5 cm")
        await body.log_measurement(s, user, "waist", "82")
        await body.log_measurement(s, user, "arm", 36)
        assert await body.last_measurements(s, user) == {"waist": 82.0, "arm": 36.0}
        for kind, value in (("waist", "5"), ("neck", "40"), ("waist", "abc")):
            with pytest.raises(ValidationError):
                await body.log_measurement(s, user, kind, value)


def test_charts_render_png():
    days = [date(2026, 11, d) for d in range(1, 8)]
    png = charts.line_chart("Weight", "kg", [("w", days, [75, 75.2, 75.1, 75.4, 75.3, 75.6, 75.5])],
                            show_average=True)
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 5000
    assert charts.bar_chart("Volume", "kg", days, [0, 1000, 0, 2000, 0, 0, 1500])[:4] == b"\x89PNG"
    assert charts.moving_average([1, 2, 3, 4], window=2) == [1, 1.5, 2.5, 3.5]


# ---------- Time zones and reminders ----------

@pytest.mark.parametrize("name,offset", [
    ("UTC", 0), ("UTC+05:30", 330), ("UTC-03:30", -210), ("UTC+14:00", 840),
])
def test_parse_fixed_offsets(name, offset):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert reminders.parse_tz(name).utcoffset(now) == timedelta(minutes=offset)
    assert reminders.offset_name(offset) == (name if name != "UTC" else "UTC+00:00")


def test_parse_iana_and_invalid():
    berlin = reminders.parse_tz("Europe/Berlin")
    assert berlin.utcoffset(datetime(2026, 7, 1)) == timedelta(hours=2)   # summer time
    assert berlin.utcoffset(datetime(2026, 1, 1)) == timedelta(hours=1)
    for bad in ("Mars/Olympus", "", "UTC+5"):
        assert not reminders.is_valid_tz(bad)


async def test_enable_defaults_bounds_and_trained_on(session_factory):
    async with session_factory() as s:
        user, plan = await setup_user(s)
        settings = await reminders.enable(s, user, "UTC+05:30")
        assert settings.workout_days == [0, 1, 3, 4]      # 4 training days
        assert (settings.weighin_mode, settings.nudge_enabled) == ("weekly", True)

        start, end = reminders.local_day_bounds_utc(settings, date(2026, 11, 14))
        assert start == datetime(2026, 11, 13, 18, 30, tzinfo=timezone.utc)
        assert end - start == timedelta(days=1)

        today = reminders.local_now(settings).date()
        assert not await reminders.trained_on(s, user, settings, today)
        await workouts.start(s, user, plan, 0)
        assert await reminders.trained_on(s, user, settings, today)

        when = await reminders.reschedule(s, settings, 1)
        assert when.date() == today + timedelta(days=1) and when.strftime("%H:%M") == "18:00"
        await reminders.workout_finished(s, user)
        assert settings.rescheduled_for is None and settings.missed_streak == 0


async def test_scheduler_builds_jobs_from_settings():
    calls = []

    async def notify(kind, user_id):
        calls.append((kind, user_id))

    scheduler = ReminderScheduler(notify)
    scheduler.start()
    try:
        settings = ReminderSettings(
            user_id=7, timezone="Europe/Berlin", workout_enabled=True, workout_days=[0, 2, 4],
            workout_time="18:00", weighin_mode="weekly", weighin_day=6, weighin_time="08:00",
            nudge_enabled=True, nudge_time="21:00",
            rescheduled_for=datetime.now(timezone.utc) + timedelta(hours=3),
        )
        scheduler.sync(7, settings)
        jobs = scheduler.jobs_for(7)
        assert set(jobs) == {"workout", "nudge", "weighin", "resched"}
        workout_next = jobs["workout"].next_run_time
        assert workout_next.weekday() in (0, 2, 4) and workout_next.strftime("%H:%M") == "18:00"
        assert jobs["weighin"].next_run_time.weekday() == 6
        assert jobs["nudge"].next_run_time.strftime("%H:%M") == "21:00"

        settings.workout_enabled, settings.weighin_mode, settings.rescheduled_for = False, "off", None
        scheduler.sync(7, settings)
        assert scheduler.jobs_for(7) == {}

        settings.weighin_mode = "daily"
        scheduler.sync(7, settings)
        assert set(scheduler.jobs_for(7)) == {"weighin"}
        scheduler.remove_user(7)
        assert scheduler.jobs_for(7) == {}
    finally:
        scheduler.shutdown()


async def test_load_all_and_deletion_cascade(session_factory):
    async with session_factory() as s:
        user, _ = await setup_user(s, telegram_id=55)
        await reminders.enable(s, user, "UTC")
        await body.log_weight(s, user, 76)
        await body.log_measurement(s, user, "waist", 80)
        scheduler = ReminderScheduler(lambda kind, uid: None)
        scheduler.start()
        try:
            assert await scheduler.load_all(s) == 1
            assert "workout" in scheduler.jobs_for(user.id)
        finally:
            scheduler.shutdown()
    async with session_factory() as s:
        await users.delete_user_data(s, 55)
        for model in (ReminderSettings, BodyWeightLog, WorkoutSession):
            assert (await s.scalars(select(model))).first() is None
