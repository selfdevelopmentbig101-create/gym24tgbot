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

from database.models import User

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
    """

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        tg_user = data.get("event_from_user")
        code = None
        if tg_user is not None:
            code = await data["session"].scalar(
                select(User.language).where(User.telegram_id == tg_user.id))
            code = code or tg_user.language_code
        set_language(code)
        return await handler(event, data)


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
