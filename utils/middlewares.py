"""
Middlewares run before every handler.

- DbSessionMiddleware: opens a database session and passes it to handlers
  as the `session` argument, closing it afterwards.
- RateLimitMiddleware: stops a single user from flooding the bot.
"""
import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from database.models import Profile, User
from keyboards.menu import menu_key
from keyboards.profile import first_language_prompt, language_keyboard

from utils.rate_limit import SlidingWindowLimiter
from utils.texts import set_language, t

logger = logging.getLogger(__name__)

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        async with self.session_factory() as session:
            data["session"] = session
            return await handler(event, data)


class LanguageMiddleware(BaseMiddleware):
    """
    Pick the language for this update: the user's saved choice, otherwise
    their Telegram app language (not stored). Must run after DbSessionMiddleware.
    Also tells later middlewares whether the user exists and has chosen a language.
    """

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        tg_user = data.get("event_from_user")
        code = None
        data["known_user"] = False
        data["saved_language"] = None
        if tg_user is not None:
            row = (await data["session"].execute(
                select(User.id, User.language).where(User.telegram_id == tg_user.id))).first()
            if row is not None:
                data["known_user"] = True
                data["saved_language"] = row.language
            code = (row.language if row is not None else None) or tg_user.language_code
        set_language(code)
        return await handler(event, data)


class MenuButtonMiddleware(BaseMiddleware):
    """
    A reply-menu tap leaves any half-finished text form (weight, food, time zone,
    profile edit), so the menu handler gets it instead of the form. Onboarding is kept.
    """

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        state = data.get("state")
        if isinstance(event, Message) and state is not None and menu_key(event.text):
            if await state.get_state() and (await state.get_data()).get("mode") != "onboarding":
                await state.clear()
        return await handler(event, data)


class LanguagePromptMiddleware(BaseMiddleware):
    """
    Users who finished setup before the language picker existed have no saved
    language. After their next message, ask them once (once per bot run until they choose).
    """

    def __init__(self):
        self._asked: set[int] = set()

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        result = await handler(event, data)
        tg_user = data.get("event_from_user")
        if (not isinstance(event, Message) or tg_user is None or not data.get("known_user")
                or data.get("saved_language") or tg_user.id in self._asked
                or (event.text or "").startswith("/start")
                or (event.text or "").startswith("/language")
                or menu_key(event.text) == "menu_language"):
            return result
        # Re-read: the handler may have set the language or deleted the user.
        row = (await data["session"].execute(
            select(User.language, Profile.id)
            .join(Profile, Profile.user_id == User.id)
            .where(User.telegram_id == tg_user.id))).first()
        if row is not None and row.language is None:
            self._asked.add(tg_user.id)
            await event.answer(first_language_prompt(), reply_markup=language_keyboard(first=True))
        return result


class RateLimitMiddleware(BaseMiddleware):
    """
    At most `max_events` per `window` seconds per user (utils/rate_limit.py).
    Extra events are dropped; the user is warned once per window.
    """

    def __init__(self, max_events: int, window: float):
        self.window = window
        self.limiter = SlidingWindowLimiter(max_events, window)
        self._warned_at: dict[int, float] = {}

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)

        now = time.monotonic()
        if self.limiter.hit(user.id, now):
            return await handler(event, data)

        logger.warning("Rate limit hit (user %s)", user.id)
        if isinstance(event, CallbackQuery):
            await event.answer(t("rate_limited"))  # small popup, always fine to send
        elif now - self._warned_at.get(user.id, 0) > self.window:
            self._warned_at[user.id] = now
            if isinstance(event, Message):
                await event.answer(t("rate_limited"))
        return None
