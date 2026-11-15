"""
A small in-memory rate limiter shared by the bot and the API.

Sliding window: at most `max_events` per `window` seconds per key (a user ID
or an IP address). Fine for one process per entry point; switch to Redis if
you ever run several copies of the bot or the API.
"""
import time
from collections import deque


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window: float):
        self.max_events = max_events
        self.window = window
        self._events: dict[object, deque[float]] = {}

    def hit(self, key: object, now: float | None = None) -> bool:
        """Record one event. Returns False if the key is over the limit (event not counted)."""
        now = time.monotonic() if now is None else now
        events = self._events.setdefault(key, deque())
        while events and now - events[0] > self.window:
            events.popleft()
        if len(events) >= self.max_events:
            return False
        events.append(now)
        if len(self._events) > 10_000:
            self._cleanup(now)
        return True

    def retry_after(self, key: object, now: float | None = None) -> int:
        """Seconds until the oldest event leaves the window."""
        now = time.monotonic() if now is None else now
        events = self._events.get(key)
        if not events:
            return 0
        return max(1, int(self.window - (now - events[0])) + 1)

    def _cleanup(self, now: float) -> None:
        """Forget idle keys so memory doesn't grow forever."""
        idle = [k for k, ev in self._events.items() if not ev or now - ev[-1] > self.window]
        for key in idle:
            self._events.pop(key, None)
