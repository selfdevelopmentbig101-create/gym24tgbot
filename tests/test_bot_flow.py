"""
End-to-end test of the Telegram flow without contacting Telegram.

A fake session records every API call the bot makes, and we feed it updates
as if a user were tapping buttons and typing.
"""
from datetime import datetime

import pytest_asyncio
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.types import Animation, CallbackQuery, Chat, Message, PhotoSize, Update, User
from sqlalchemy import select

from bot import create_dispatcher
from database.base import create_tables, make_engine, make_session_factory
from database.models import MediaCache
from services import exercise_media, plans, users
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
        if name == "EditMessageMedia":
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

    await u.tap("Log set")
    assert "coming" in u.last_call("AnswerCallbackQuery").text

    await u.tap("Plan")
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
