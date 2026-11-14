"""
Middlewares run before every handler.

- DbSessionMiddleware: opens a database session and passes it to handlers
  as the `session` argument, closing it afterwards.
- RateLimitMiddleware: stops a single user from flooding the bot.
"""
import logging
import time
from collections import deque
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker

from utils.texts import t

logger = logging.getLogger(__name__)

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        async with self.session_factory() as session:
            data["session"] = session
            return await handler(event, data)


class RateLimitMiddleware(BaseMiddleware):
    """
    Sliding window: at most `max_events` per `window` seconds per user.
    Extra events are dropped; the user is warned once per window.
    In-memory, which is fine for a single bot process (use Redis if you scale out).
    """

    def __init__(self, max_events: int, window: float):
        self.max_events = max_events
        self.window = window
        self._events: dict[int, deque[float]] = {}
        self._warned_at: dict[int, float] = {}

    def _is_limited(self, user_id: int, now: float) -> bool:
        events = self._events.setdefault(user_id, deque())
        while events and now - events[0] > self.window:
            events.popleft()
        if len(events) >= self.max_events:
            return True
        events.append(now)
        return False

    def _cleanup(self, now: float) -> None:
        """Forget idle users so memory doesn't grow forever."""
        if len(self._events) < 10_000:
            return
        idle = [uid for uid, ev in self._events.items() if not ev or now - ev[-1] > self.window]
        for uid in idle:
            self._events.pop(uid, None)
            self._warned_at.pop(uid, None)

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)

        now = time.monotonic()
        self._cleanup(now)
        if not self._is_limited(user.id, now):
            return await handler(event, data)

        logger.warning("Rate limit hit (user %s)", user.id)
        if isinstance(event, CallbackQuery):
            await event.answer(t("rate_limited"))  # small popup, always fine to send
        elif now - self._warned_at.get(user.id, 0) > self.window:
            self._warned_at[user.id] = now
            if isinstance(event, Message):
                await event.answer(t("rate_limited"))
        return None
