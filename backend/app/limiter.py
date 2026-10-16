"""Minimal in-process rate limiter.

Suitable for a single Render instance / local dev. For multi-instance
deployments swap this for a Redis-backed limiter; the interface stays the same.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from .config import Config


class RateLimiter:
    def __init__(self, per_minute: int | None = None):
        self.per_minute = per_minute or Config.RATE_LIMIT_PER_MINUTE
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        window = 60.0
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > window:
                bucket.popleft()
            if len(bucket) >= self.per_minute:
                return False
            bucket.append(now)
            return True


_limiter: RateLimiter | None = None


def get_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter()
    return _limiter
