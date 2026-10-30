"""Small in-memory rate limiter for the endpoints that cost Gemma or GitHub calls.

Sliding window per client. It lives in one process, so it resets on restart and is not shared between
several server copies. That is fine for a single-instance deploy; use a shared store if you scale out.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from . import config


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int = 60, clock=time.monotonic):
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> int:
        """Records a hit. Returns 0 if allowed, otherwise the seconds to wait before retrying."""
        if self.limit <= 0:  # 0 turns the limiter off
            return 0
        now = self._clock()
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return max(1, int(self.window - (now - hits[0])) + 1)
        hits.append(now)
        if len(self._hits) > 10000:  # keep memory bounded: drop idle clients
            for k in [k for k, v in self._hits.items() if not v or now - v[-1] >= self.window]:
                del self._hits[k]
        return 0


def client_key(request: Request) -> str:
    # Behind a host's proxy the real client is the first X-Forwarded-For entry.
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


triage_limiter = RateLimiter(config.RATE_LIMIT_PER_MINUTE)


def limit_triage(request: Request) -> None:
    wait = triage_limiter.check(client_key(request))
    if wait:
        raise HTTPException(
            status_code=429,
            detail=f"Too many reviews in a short time. Try again in {wait} seconds.",
            headers={"Retry-After": str(wait)},
        )
