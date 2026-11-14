"""
End-to-end test of the Telegram flow without contacting Telegram.

A fake session records every API call the bot makes, and we feed it updates
as if a user were tapping buttons and typing.
"""
from datetime import datetime

import pytest
import pytest_asyncio
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.types import Animation, CallbackQuery, Chat, Message, PhotoSize, Update, User
from sqlalchemy import select

from bot import create_dispatcher
from database.base import create_tables, make_engine, make_session_factory
from database.models import MediaCache
from services import exercise_media, plans, users, workouts
from services.rest_timer import rest_timers
from services.exercise_import import import_exercises, load_exercises_file
from tests.test_texts import assert_valid_telegram_html


class FakeSession(BaseSession):
    """Records requests and returns plausible responses."""

    def __init__(self):
        super().__init__()
        self.calls = []
        self._next_id = 1000
        self.last_markup_message = None  # the bot message whose buttons the user sees

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        name = type(method).__name__
        # Every message the bot sends must be valid Telegram HTML.
        for attr in ("text", "caption"):
            if isinstance(getattr(method, attr, None), str) and name != "AnswerCallbackQuery":
                assert_valid_telegram_html(getattr(method, attr))
        if name == "EditMessageMedia" and method.media.caption:
            assert_valid_telegram_html(method.media.caption)

        if method.__returning__ is Message or "Message" in str(method.__returning__):
            self._next_id += 1
            chat_id = getattr(method, "chat_id", None) or 1
            extra = {}
            media = getattr(method, "media", None)
            if name == "SendAnimation" or (media is not None and media.type == "animation"):
                extra["animation"] = Animation(file_id=f"anim-file-{self._next_id}",
                                               file_unique_id="u", width=512, height=512, duration=2)
            elif name == "SendPhoto" or (media is not None and media.type == "photo"):
                extra["photo"] = [PhotoSize(file_id=f"photo-file-{self._next_id}",
                                            file_unique_id="u", width=512, height=512)]
            else:
                extra["text"] = getattr(method, "text", None) or ""
            message = Message(message_id=self._next_id, date=datetime.now(),
                              chat=Chat(id=chat_id, type="private"),
                              caption=getattr(method, "caption", None), **extra)
            if getattr(method, "reply_markup", None) is not None:
                self.last_markup_message = message
            return message
        return True

    async def stream_content(self, *args, **kwargs):  # pragma: no cover
        yield b""

    async def close(self):
        pass


class FakeUser:
    """Sends messages and taps the buttons of the bot's latest message."""

    _update_id = 0  # shared counter, Telegram update IDs are global

    def __init__(self, env, user_id):
        self.dp, self.bot, self.session = env["dp"], env["bot"], env["session"]
        self.user_id = user_id
        self.chat = Chat(id=user_id, type="private")
        self.tg_user = User(id=user_id, is_bot=False, first_name="Test", language_code="en")

    @property
    def update_id(self):
        return FakeUser._update_id

    def _next_update_id(self):
        FakeUser._update_id += 1
        return FakeUser._update_id

    async def send(self, text):
        self._next_update_id()
        msg = Message(message_id=self.update_id, date=datetime.now(), chat=self.chat,
                      from_user=self.tg_user, text=text)
        await self.dp.feed_update(self.bot, Update(update_id=self.update_id, message=msg))

    def last_markup(self):
        for call in reversed(self.session.calls):
            markup = getattr(call, "reply_markup", None)
            if markup is not None and getattr(markup, "inline_keyboard", None):
                return markup
        raise AssertionError("No inline keyboard sent")

    def last_text(self):
        """Text or caption of the bot's latest message or edit."""
        for call in reversed(self.session.calls):
            media = getattr(call, "media", None)
            for value in (getattr(call, "text", None), getattr(call, "caption", None),
                          getattr(media, "caption", None) if media is not None else None):
                if isinstance(value, str) and value:
                    return value
        return ""

    def last_call(self, name):
        return next(c for c in reversed(self.session.calls) if type(c).__name__ == name)

    async def tap(self, label):
        """Tap a button whose label contains `label`."""
        buttons = [b for row in self.last_markup().inline_keyboard for b in row]
        matches = [b for b in buttons if label in b.text]
        assert matches, f"No button '{label}' in {[b.text for b in buttons]}"
        self._next_update_id()
        message = self.session.last_markup_message
        if message is None or message.chat.id != self.user_id:
            message = Message(message_id=1, date=datetime.now(), chat=self.chat, text="q")
        cq = CallbackQuery(
            id=str(self.update_id), from_user=self.tg_user, chat_instance="ci",
            data=matches[0].callback_data, message=message,
        )
        await self.dp.feed_update(self.bot, Update(update_id=self.update_id, callback_query=cq))


@pytest_asyncio.fixture(scope="module")
async def env():
    # One dispatcher per module: aiogram routers can attach to only one dispatcher.
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    session_factory = make_session_factory(engine)
    async with session_factory() as s:
        await import_exercises(s, load_exercises_file())
    session = FakeSession()
    bot = Bot("123456:TEST-TOKEN-not-real", session=session,
              default=DefaultBotProperties(parse_mode="HTML"))
    dp = create_dispatcher(session_factory, rate_limit_max=1000, rate_limit_window=1)
    yield {"dp": dp, "bot": bot, "session": session, "session_factory": session_factory}
    await engine.dispose()


async def onboard(u: FakeUser):
    await u.send("/start")
    assert "Health disclaimer" in u.last_text()
    await u.tap("I understand")
    assert "Step 1/10" in u.last_text()
    await u.tap("Lean bulk")
    await u.send("abc")                      # invalid -> error, stays on step
    assert "number" in u.last_text()
    await u.send("27")
    await u.tap("Back")                      # back to age
    assert "How old" in u.last_text()
    await u.send("27")
    await u.tap("Male")
    await u.send("500")                      # out of range
    assert "between 130 and 220" in u.last_text()
    await u.send("1.80")
    await u.send("75")
    await u.tap("Beginner")
    await u.tap("3")
    await u.tap("Full gym")
    await u.tap("Knee")                      # toggle on
    await u.tap("Shoulder")                  # toggle on
    await u.tap("Shoulder")                  # toggle off
    await u.tap("Done")
    await u.tap("No restrictions")


async def test_full_onboarding_edit_and_delete(env):
    u, session_factory = FakeUser(env, 4242), env["session_factory"]
    await onboard(u)

    text = u.last_text()
    assert "All set" in text and "Daily targets" in text and "kcal" in text
    async with session_factory() as s:
        user = await users.get_user(s, u.user_id)
        p = user.profile
        assert (p.goal.value, p.age, p.height_cm, p.weight_kg) == ("lean_bulk", 27, 180, 75)
        assert p.injuries == ["knee"]
        assert user.disclaimer_accepted_at is not None

    # Edit weight via /settings -> Edit profile -> Weight: 3 taps + typing.
    await u.send("/settings")
    await u.tap("Edit profile")
    await u.tap("Weight")
    assert "Current: <b>75 kg</b>" in u.last_text()
    await u.send("78.5")
    assert "Updated" in u.last_text() and "78.5 kg" in u.last_text()

    # Edit goal with a button.
    await u.tap("Edit profile")
    await u.tap("Goal")
    await u.tap("Recomposition")
    assert "Recomposition" in u.last_text() and "maintenance" in u.last_text()

    # /start after onboarding does not restart the form.
    await u.send("/start")
    assert "Welcome back" in u.last_text()

    await u.send("/deleteme")
    await u.tap("Yes, delete")
    assert "deleted" in u.last_text()
    async with session_factory() as s:
        assert await users.get_user(s, u.user_id) is None


async def test_profile_requires_onboarding_and_commands_work_mid_form(env):
    u = FakeUser(env, 5151)
    await u.send("/profile")
    assert "/start" in u.last_text()

    await u.send("/start")
    await u.tap("I understand")
    await u.tap("Bulk")
    await u.send("/about")
    assert "Credits" in u.last_text()
    await u.send("/start")                   # resumes the current question
    assert "How old" in u.last_text()
    await u.send("/cancel")
    assert "Cancelled" in u.last_text()

    # A button from the cancelled form is ignored instead of crashing.
    await u.tap("Back")
    last = u.session.calls[-1]
    assert type(last).__name__ == "AnswerCallbackQuery" and "no longer active" in last.text


# ---------- Phase 2: plan, cards, library ----------

async def test_plan_cards_and_substitute(env):
    u, session_factory = FakeUser(env, 6161), env["session_factory"]
    await onboard(u)                       # beginner, full gym, 3 days, knee injury
    assert "plan is ready" in u.last_text()

    await u.send("/plan")
    text = u.last_text()
    assert "Full body" in text and "Day 3 · Full Body C" in text
    assert "Barbell Squat" not in text      # knee injury: squats are excluded

    await u.tap("1 · Full Body A")
    card = u.last_text()
    assert "exercise 1 of 6" in card and "3 × 8–12" in card and "Form tips coming soon" in card

    await u.tap("Next")
    assert "exercise 2 of 6" in u.last_text()

    async with session_factory() as s:
        user = await users.get_user(s, u.user_id)
        before = [e.exercise_id for e in (await plans.get_plan(s, user)).days[0].exercises]
    await u.tap("Substitute")
    assert u.last_call("AnswerCallbackQuery").text == "Swapped in your plan ✅"
    async with session_factory() as s:
        user = await users.get_user(s, u.user_id)
        after = [e.exercise_id for e in (await plans.get_plan(s, user)).days[0].exercises]
    assert before[1] != after[1] and before[0] == after[0] and len(set(after)) == len(after)
    assert "exercise 2 of 6" in u.last_text()

    await u.tap("Log set")                   # opens the workout logger at this exercise
    assert "exercise 2 of 6" in u.last_text() and "Set 1 of 3" in u.last_text()

    await u.send("/plan")
    assert "Your plan" in u.last_text()
    await u.tap("New plan")
    assert "New plan generated" in u.last_text()

    # Changing equipment rebuilds the plan with home exercises only.
    await u.send("/settings")
    await u.tap("Edit profile")
    await u.tap("Equipment")
    await u.tap("Bodyweight only")
    assert "rebuilt" in u.last_text()
    async with session_factory() as s:
        user = await users.get_user(s, u.user_id)
        plan = await plans.get_plan(s, user)
        gear = {e.exercise.equipment for d in plan.days for e in d.exercises}
    assert gear == {"bodyweight"}

    # An outdated card button (plan was rebuilt) is handled gracefully.
    await u.send("/deleteme")
    await u.tap("Yes, delete")
    async with session_factory() as s:
        assert await users.get_user(s, u.user_id) is None


async def test_library_browse_and_substitute(env):
    u = FakeUser(env, 7171)
    await u.send("/exercises")            # works without a profile: shows everything
    assert "Exercise library" in u.last_text()
    await u.tap("Chest")
    assert "Barbell Bench Press" in u.last_text() and "1 of 11" in u.last_text()
    await u.tap("Next")
    assert "Dumbbell Bench Press" in u.last_text() and "2 of 11" in u.last_text()
    await u.tap("Substitute")
    assert "Barbell Bench Press" in u.last_text()
    await u.tap("Muscle groups")
    assert "Pick a muscle group" in u.last_text()


async def test_media_cards_upload_once_then_reuse_file_id(env, tmp_path, monkeypatch):
    from PIL import Image
    monkeypatch.setattr(exercise_media, "IMAGE_DIR", tmp_path)
    monkeypatch.setattr(exercise_media, "CACHE_DIR", tmp_path / "cache")
    for name, color in (("hip-thrust-start", "red"), ("hip-thrust-peak", "blue"),
                        ("glute-bridge", "green")):
        Image.new("RGB", (512, 512), color).save(tmp_path / f"{name}.webp", "WEBP")

    u = FakeUser(env, 8181)
    await u.send("/exercises")
    await u.tap("Glutes")                  # first glutes exercise: hip-thrust (animated)
    first = u.last_call("SendAnimation")
    assert not isinstance(first.animation, str)   # uploaded from disk
    assert "Barbell Hip Thrust" in first.caption

    await u.tap("Next")                    # dumbbell-hip-thrust: no images -> text card
    assert u.last_call("DeleteMessage") and "Dumbbell Hip Thrust" in u.last_text()
    await u.tap("Next")                    # glute-bridge: single image -> photo
    assert "Glute Bridge" in u.last_call("SendPhoto").caption
    await u.tap("Substitute")              # -> dumbbell-hip-thrust (text again)
    await u.send("/exercises")
    await u.tap("Glutes")
    again = u.last_call("SendAnimation")
    assert isinstance(again.animation, str) and again.animation.startswith("anim-file-")

    async with env["session_factory"]() as s:
        keys = {row.key.split(":")[0] for row in await s.scalars(select(MediaCache))}
    assert keys == {"anim", "photo"}


# ---------- Phase 3: workout logger ----------

@pytest.fixture(autouse=True)
def no_stray_timers():
    yield
    rest_timers.cancel_all()
    rest_timers.time_scale = 1.0


async def onboard_intermediate(u: FakeUser):
    await u.send("/start")
    await u.tap("I understand")
    await u.tap("Lean bulk")
    for text, taps in (("27", ["Male"]), ("180", []), ("80", ["Intermediate", "4", "Full gym", "None",
                                                              "No restrictions"])):
        await u.send(text)
        for label in taps:
            await u.tap(label)


async def test_workout_logging_flow(env):
    u = FakeUser(env, 9191)
    await onboard_intermediate(u)

    await u.send("/workout")
    text = u.last_text()
    assert "Today: Day 1 · Upper A" in text and "Barbell Bench Press" in text

    await u.tap("Start workout")              # 2 taps from /workout to the logger
    card = u.last_text()
    assert "Barbell Bench Press" in card and "First time" in card and "Set 1 of 3" in card
    assert "Log 20 kg × 6" in [b.text for row in u.last_markup().inline_keyboard for b in row][4]

    # Adjust and log: +2.5 kg x 4 taps... use typing for a big jump instead.
    await u.send("60x10")
    assert "1. 60 kg × 10" in u.last_text() and "Set 2 of 3" in u.last_text()
    assert u.last_call("DeleteMessage")       # old card removed, new card at the bottom

    rest_timers.time_scale = 0.0001
    await u.tap("Log 60 kg × 10")             # 1 tap: same set again
    assert "2. 60 kg × 10" in u.last_text()
    await rest_timers.wait(u.user_id)
    rest_timers.time_scale = 1.0              # later timers stay pending (shared in-memory DB in tests)
    note = u.last_call("SendMessage")
    assert "Rest over" in note.text and "set 3" in note.text

    await u.tap("Log 60 kg × 10")             # from the notification: it becomes the card
    assert "3. 60 kg × 10" in u.last_text() and "All sets done" in u.last_text()

    await u.tap("Undo")
    assert "3. 60 kg" not in u.last_text() and "Removed" in u.last_call("AnswerCallbackQuery").text
    await u.tap("+1 rep")
    await u.tap("Log 60 kg × 11")
    assert "3. 60 kg × 11" in u.last_text()

    await u.tap("Next")
    assert "Pull-Up" in u.last_text() or "exercise 2 of 7" in u.last_text()
    await u.send("8")                         # reps only: uses the draft weight (BW)
    assert "1. BW × 8" in u.last_text()

    await u.tap("Exercises")
    assert "✅ Barbell Bench Press" in str(u.last_markup().inline_keyboard)
    await u.tap("Back")

    await u.tap("Finish")
    summary = u.last_text()
    assert "Workout done: Upper A" in summary and "4 sets" in summary
    assert "Barbell Bench Press: add weight → 62.5 kg" in summary
    assert "Next workout: <b>Day 2 · Lower A</b>" in summary

    # Old card buttons after finishing are handled.
    await u.tap("Finish")
    assert "has ended" in u.last_call("AnswerCallbackQuery").text

    # Next Upper A: last time is shown and the overload suggestion is pre-filled.
    async with env["session_factory"]() as s:
        user = await users.get_user(s, u.user_id)
        plan = await plans.get_plan(s, user)
        ws = await workouts.start(s, user, plan, 0)
        hint, previous = await workouts.suggestion_for(s, user, ws, 0)
        assert [p.reps for p in previous] == [10, 10, 11] and hint.kind == "add_weight"
        assert ws.draft_weight == 62.5
    await u.send("/workout")                  # resumes the active workout
    card = u.last_text()
    assert "Last time: 60 kg × 10 · 60 kg × 10 · 60 kg × 11" in card and "add weight" in card
    buttons = [b.text for row in u.last_markup().inline_keyboard for b in row]
    assert "Log 62.5 kg × 6" in " ".join(buttons)
    await u.tap("Same as last time")
    assert "1. 60 kg × 10" in u.last_text()


async def test_typed_set_without_workout_and_with_bad_values(env):
    u = FakeUser(env, 9292)
    await onboard_intermediate(u)
    await u.send("60x8")
    assert "No workout in progress" in u.last_text()
    await u.send("/workout")
    await u.tap("Start workout")
    await u.send("900x8")
    assert "between 0 and 500" in u.last_text()
    await u.tap("Finish")
    assert "Nothing was logged" in u.last_text()


# ---------- Phase 4: progress and reminders ----------

async def test_progress_weight_measurements_and_charts(env):
    u = FakeUser(env, 10101)
    await onboard_intermediate(u)              # 80 kg in onboarding

    await u.send("/progress")
    assert "No weigh-ins yet" in u.last_text()
    await u.tap("Log weight")
    assert "Log body weight" in u.last_text()
    await u.tap("+0.5")
    await u.tap("Log 80.5 kg")                 # 3 taps from /progress
    text = u.last_text()
    assert "Logged <b>80.5 kg</b>" in text and "daily targets were updated" in text

    await u.send("/weight 80,9")               # typed with a comma
    assert "80.9 kg" in u.last_text()
    await u.send("/weight")
    await u.send("81.2")                       # typing while the weight logger is open
    assert "81.2 kg" in u.last_text()
    async with env["session_factory"]() as s:
        user = await users.get_user(s, u.user_id)
        assert user.profile.weight_kg == 81.2

    await u.send("/measure")
    await u.tap("Waist")
    assert "type the value" in u.last_text()
    await u.send("84")
    assert "Waist: <b>84 cm</b>" in u.last_text()
    await u.send("/measure")
    await u.tap("Waist")
    await u.tap("-1")
    await u.tap("Log 83 cm")
    assert "83 cm" in u.last_text()

    await u.send("/progress")
    assert "81.2 kg" in u.last_text() and "Waist 83 cm" in u.last_text()
    await u.tap("Weight chart")                # 3 weigh-ins today -> chart
    photo = u.last_call("SendPhoto")
    assert photo.photo.filename == "chart.png"
    await u.tap("Week")                        # switch range: edits the image in place
    assert type(u.session.calls[-1]).__name__ == "EditMessageMedia"
    await u.tap("Progress")
    assert "Your progress" in u.last_text()
    await u.tap("Strength chart")
    assert "No weighted sets" in u.last_text()


async def test_prs_in_workout_and_progress(env):
    u = FakeUser(env, 10202)
    await onboard_intermediate(u)
    await u.send("/workout")
    await u.tap("Start workout")
    await u.send("60x8")
    await u.send("62.5x8")                     # beats the previous estimated 1RM
    assert "2. 62.5 kg × 8 🏆" in u.last_text()
    await u.tap("Finish")
    assert "New PRs" in u.last_text() and "Barbell Bench Press" in u.last_text()
    await u.send("/progress")
    await u.tap("All PRs")
    assert "Barbell Bench Press: <b>79.2 kg</b> from 62.5 kg × 8" in u.last_text()

    # A second Upper A workout gives the bench strength chart two points.
    await u.send("/workout")
    await u.tap("1 · Upper A")
    await u.tap("Start workout")
    assert "Barbell Bench Press" in u.last_text()
    await u.send("65x6")
    await u.tap("Finish")
    await u.send("/progress")
    await u.tap("Strength chart")
    photos_before = sum(type(c).__name__ == "SendPhoto" for c in u.session.calls)
    await u.tap("Barbell Bench Press")
    assert sum(type(c).__name__ == "SendPhoto" for c in u.session.calls) == photos_before + 1


async def test_reminders_setup_and_nudges(env):
    from handlers.reminders import make_notifier
    from services.scheduler import ReminderScheduler, set_scheduler

    u = FakeUser(env, 10303)
    await onboard_intermediate(u)               # 4 training days
    notify = make_notifier(env["bot"], env["session_factory"])
    scheduler = ReminderScheduler(notify)
    scheduler.start()
    set_scheduler(scheduler)
    try:
        await u.send("/reminders")
        assert "Reminders</b> are off" in u.last_text()
        await u.tap(next(b.text for row in u.last_markup().inline_keyboard for b in row
                         if b.callback_data.endswith(":120")))   # the UTC+2 button
        text = u.last_text()
        assert "Mon, Tue, Thu, Fri at 18:00" in text and "UTC+02:00" in text
        async with env["session_factory"]() as s:
            user = await users.get_user(s, u.user_id)
        assert set(scheduler.jobs_for(user.id)) == {"workout", "nudge", "weighin", "summary"}

        await u.tap("🕕 18:00")                                     # workout time picker
        await u.tap("07:00")
        assert "at 07:00" in u.last_text()
        await u.tap("Days")
        await u.tap("Sat")
        await u.tap("Done")
        assert "Mon, Tue, Thu, Fri, Sat at 07:00" in u.last_text()
        await u.tap("Weigh-in: weekly")                           # -> off
        assert "Weigh-in: <b>off</b>" in u.last_text()
        assert "weighin" not in scheduler.jobs_for(user.id)

        # Typed IANA time zone.
        await u.tap("Time zone")
        await u.send("Mars/Base")
        assert "don't know that time zone" in u.last_text()
        await u.send("Europe/Berlin")
        assert "Europe/Berlin" in u.last_text()

        # Workout reminder: sent when not trained yet, with a start button.
        await notify("workout", user.id)
        assert "Workout day!" in u.last_text() and "Day 1" in u.last_text()

        # Missed-workout nudge x3 -> offers a lighter schedule.
        for _ in range(3):
            await notify("nudge", user.id)
        assert "missed 3 planned workouts" in u.last_text()
        await u.tap("Tomorrow at 07:00")
        assert "I'll remind you" in u.last_text()
        assert "resched" in scheduler.jobs_for(user.id)

        await notify("nudge", user.id)
        await u.tap("Switch to 3 days/week")
        assert "Switched to 3 days" in u.last_text()
        async with env["session_factory"]() as s:
            user = await users.get_user(s, u.user_id)
            assert user.profile.training_days == 3
            assert len((await plans.get_plan(s, user)).days) == 3

        # Weigh-in reminder offers the 1-tap weight logger; skipped once weighed in.
        await notify("weighin", user.id)
        assert "Weigh-in time" in u.last_text()
        await u.tap("Log 80 kg")
        calls_before = len(u.session.calls)
        await notify("weighin", user.id)
        assert len(u.session.calls) == calls_before

        # Training today silences workout reminders and nudges.
        await u.send("/workout")
        await u.tap("Start workout")
        calls_before = len(u.session.calls)
        await notify("workout", user.id)
        await notify("nudge", user.id)
        assert len(u.session.calls) == calls_before

        await u.send("/deleteme")
        await u.tap("Yes, delete")
        assert scheduler.jobs_for(user.id) == {}
    finally:
        set_scheduler(None)
        scheduler.shutdown()


# ---------- Phase 5: nutrition ----------

async def test_food_logging_flow(env):
    u = FakeUser(env, 11111)
    await onboard_intermediate(u)               # lean bulk, 80 kg

    await u.send("/food")
    text = u.last_text()
    assert "Calories: <b>0</b>" in text and "Nothing logged yet" in text
    assert "Easy protein" in text               # 0 g of ~160 g protein so far

    await u.tap("Protein")                      # 3 taps: /food -> category -> food
    assert "Chicken breast (150 g cooked): 250 kcal, 46 g" in u.last_text()
    await u.tap("Chicken breast")
    text = u.last_text()
    assert "Chicken breast</b> (150 g cooked): 250 kcal, 46 g protein" in text
    assert "Calories: <b>250</b>" in text
    await u.tap("×2")
    assert "×2: 500 kcal, 92 g" in u.last_text() and "Calories: <b>500</b>" in u.last_text()

    await u.tap("Food")
    assert "🔁 Chicken breast" in str(u.last_markup().inline_keyboard)   # recent: 2 taps
    await u.tap("🔁 Chicken breast")
    assert "Calories: <b>750</b>" in u.last_text()
    await u.tap("Undo")
    assert "Calories: <b>500</b>" in u.last_text()

    await u.tap("Manual")
    await u.send("way too much 100 80")
    assert "more protein than the calories allow" in u.last_text()
    await u.send("Burrito bowl 850 45")
    assert "Burrito bowl</b>: 850 kcal" in u.last_text() and "Calories: <b>1,350</b>" in u.last_text()
    await u.send("/food 300 25")                # command shortcut
    assert "Manual entry</b>: 300 kcal" in u.last_text()

    await u.send("/food")
    await u.tap("Edit")
    await u.tap("Manual entry")
    assert "Removed: Manual entry" in u.last_call("AnswerCallbackQuery").text
    await u.tap("Food")
    text = u.last_text()
    assert "Calories: <b>1,350</b>" in text and "Burrito bowl" in text

    await u.tap("Previous day")
    assert "Yesterday" in u.last_text() and "Nothing logged that day" in u.last_text()
    await u.tap("Next day")
    assert "Today" in u.last_text()

    # Typing "650 40" outside manual mode is not treated as food (it's a workout set format).
    await u.send("650 40")
    assert "No workout in progress" in u.last_text()


async def test_vegan_sees_only_vegan_foods_and_evening_summary(env):
    from handlers.food import send_daily_summary
    u = FakeUser(env, 11222)
    await u.send("/start")
    await u.tap("I understand")
    await u.tap("Recomposition")
    for text, taps in (("30", ["Female"]), ("165", []), ("60", ["Beginner", "3", "Home + dumbbells",
                                                               "None", "Vegan"])):
        await u.send(text)
        for label in taps:
            await u.tap(label)

    await u.send("/food")
    await u.tap("Protein")
    names = {b.text for row in u.last_markup().inline_keyboard for b in row}
    assert "Firm tofu" in names and "Chicken breast" not in names and "Whey protein" not in names

    async with env["session_factory"]() as s:
        user = await users.get_user(s, u.user_id)
        assert await send_daily_summary(env["bot"], s, user) is False   # nothing logged: no message
    await u.tap("Firm tofu")
    async with env["session_factory"]() as s:
        user = await users.get_user(s, u.user_id)
        assert await send_daily_summary(env["bot"], s, user) is True
    text = u.last_text()
    assert "Daily summary" in text and "kcal short" in text and "Easy protein" in text
