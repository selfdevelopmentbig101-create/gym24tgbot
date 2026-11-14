"""
Rest timers: run a callback after N seconds, one timer per user.

In-memory asyncio tasks: perfect for rest periods of a few minutes. If the
bot restarts mid-rest, that one notification is lost, which is acceptable.
(Long-term reminders in Phase 4 use APScheduler with a persistent job store.)
"""
import asyncio
import logging
import time
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


class RestTimers:
    def __init__(self, time_scale: float = 1.0):
        # Tests set time_scale=0 so timers fire immediately.
        self.time_scale = time_scale
        self._tasks: dict[int, asyncio.Task] = {}
        self._ends: dict[int, float] = {}

    def start(self, key: int, seconds: int, callback: Callable[[], Awaitable[None]]) -> None:
        """Start (or restart) the timer for `key`."""
        self.cancel(key)
        self._ends[key] = time.monotonic() + seconds
        self._tasks[key] = asyncio.create_task(self._run(key, seconds, callback))

    async def _run(self, key: int, seconds: int, callback) -> None:
        try:
            await asyncio.sleep(seconds * self.time_scale)
            await callback()
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001 - a failed notification must not crash anything
            logger.exception("Rest timer callback failed")
        finally:
            if self._tasks.get(key) is asyncio.current_task():
                self._tasks.pop(key, None)
                self._ends.pop(key, None)

    def cancel(self, key: int) -> bool:
        task = self._tasks.pop(key, None)
        self._ends.pop(key, None)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def remaining(self, key: int) -> int | None:
        """Seconds left, or None if no timer is running."""
        end = self._ends.get(key)
        return None if end is None else max(0, round(end - time.monotonic()))

    async def wait(self, key: int) -> None:
        """Wait for a timer to finish (used by tests)."""
        task = self._tasks.get(key)
        if task:
            await asyncio.gather(task, return_exceptions=True)

    def cancel_all(self) -> None:
        """Stop every timer (on shutdown and in tests)."""
        for key in list(self._tasks):
            self.cancel(key)


rest_timers = RestTimers()
