from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class InMemoryRateLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.hits = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        bucket = self.hits[key]
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.limit:
            raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
        bucket.append(now)


ai_rate_limiter = InMemoryRateLimiter(limit=20, window_seconds=60)


def rate_limit_ai(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    ai_rate_limiter.check(client)
