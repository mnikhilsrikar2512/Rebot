from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from chatbot_api.config import settings


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self.enabled = settings.rate_limit_enabled
        self.window_seconds = max(1, settings.rate_limit_window_seconds)
        self.global_limit = max(1, settings.rate_limit_requests_per_window)
        self.chat_limit = max(1, settings.rate_limit_chat_requests_per_window)
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def configure(
        self,
        *,
        enabled: bool,
        window_seconds: int,
        global_limit: int,
        chat_limit: int,
    ) -> None:
        self.enabled = enabled
        self.window_seconds = max(1, int(window_seconds))
        self.global_limit = max(1, int(global_limit))
        self.chat_limit = max(1, int(chat_limit))

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

    def _limit_for_path(self, path: str) -> int:
        if path == "/v1/chat":
            return self.chat_limit
        return self.global_limit

    def allow(self, tenant_id: str, user_id: str, path: str) -> tuple[bool, int]:
        if not self.enabled:
            return True, 0

        now = monotonic()
        cutoff = now - self.window_seconds
        key = f"{tenant_id}:{user_id}:{path}"
        limit = self._limit_for_path(path)

        with self._lock:
            dq = self._events[key]
            while dq and dq[0] < cutoff:
                dq.popleft()

            if len(dq) >= limit:
                retry_after_seconds = max(0.001, self.window_seconds - (now - dq[0]))
                return False, int(retry_after_seconds * 1000)

            dq.append(now)
            return True, 0


rate_limiter = InMemoryRateLimiter()
