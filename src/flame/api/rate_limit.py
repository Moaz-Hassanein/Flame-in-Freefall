"""In-process thread-safe sliding window rate limiter."""

from __future__ import annotations

import threading
import time
from collections import defaultdict


class InMemoryRateLimiter:
    """Sliding-window rate limiter per client key (e.g. IP address)."""

    def __init__(self, requests_per_minute: int = 60) -> None:
        self.rate_limit = requests_per_minute
        self.window_seconds = 60.0
        self._history: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, client_key: str) -> tuple[bool, int]:
        """Check whether a client request is allowed.

        Returns (is_allowed, remaining_requests).
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            # Clean old timestamps
            timestamps = [t for t in self._history[client_key] if t > cutoff]
            if len(timestamps) >= self.rate_limit:
                self._history[client_key] = timestamps
                return False, 0

            timestamps.append(now)
            self._history[client_key] = timestamps
            remaining = max(0, self.rate_limit - len(timestamps))
            return True, remaining


__all__ = ["InMemoryRateLimiter"]
