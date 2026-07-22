"""In-memory sliding-window rate limiter for auth and cast endpoints."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def hit(self, key: str, *, limit: int, window_seconds: float) -> None:
        now = time.monotonic()
        with self._lock:
            bucket = self._events[key]
            cutoff = now - window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded; try again later",
                )
            bucket.append(now)


rate_limiter = SlidingWindowRateLimiter()


def client_key(request: Request, suffix: str) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        host = forwarded.split(",")[0].strip()
    else:
        host = request.client.host if request.client else "unknown"
    return f"{host}:{suffix}"
