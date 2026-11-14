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
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from bot import create_dispatcher
from database.base import create_tables, make_engine, make_session_factory
from services import users
from tests.test_texts import assert_valid_telegram_html


class FakeSession(BaseSession):
    """Records requests and returns plausible responses."""

    def __init__(self):
        super().__init__()
        self.calls = []
        self._next_id = 1000

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        # Every message the bot sends must be valid Telegram HTML.
        if isinstance(getattr(method, "text", None), str) and type(method).__name__ != "AnswerCallbackQuery":
            assert_valid_telegram_html(method.text)
        if method.__returning__ is Message or "Message" in str(method.__returning__):
            self._next_id += 1
            chat_id = getattr(method, "chat_id", None) or 1
            return Message(message_id=self._next_id, date=datetime.now(),
                           chat=Chat(id=chat_id, type="private"),
                           text=getattr(method, "text", None) or "")
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
        for call in reversed(self.session.calls):
            if getattr(call, "text", None):
                return call.text
        return ""

    async def tap(self, label):
        """Tap a button whose label contains `label`."""
        buttons = [b for row in self.last_markup().inline_keyboard for b in row]
        matches = [b for b in buttons if label in b.text]
        assert matches, f"No button '{label}' in {[b.text for b in buttons]}"
        self._next_update_id()
        cq = CallbackQuery(
            id=str(self.update_id), from_user=self.tg_user, chat_instance="ci",
            data=matches[0].callback_data,
            message=Message(message_id=1, date=datetime.now(), chat=self.chat, text="q"),
        )
        await self.dp.feed_update(self.bot, Update(update_id=self.update_id, callback_query=cq))


@pytest_asyncio.fixture(scope="module")
async def env():
    # One dispatcher per module: aiogram routers can attach to only one dispatcher.
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    session_factory = make_session_factory(engine)
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
