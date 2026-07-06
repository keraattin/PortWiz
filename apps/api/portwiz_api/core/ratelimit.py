"""A tiny in-process sliding-window rate limiter.

Used to blunt online brute-force against login. It is per-process (each API
worker/replica keeps its own window), so a front proxy should still throttle at
the edge for defence in depth; this is the app-layer safety net.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, max_attempts: int, window_seconds: float) -> None:
        self._max = max_attempts
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, now: float | None = None) -> bool:
        """Record an attempt for ``key``; return True if allowed, False if the
        key has exceeded ``max_attempts`` within the window."""
        now = time.monotonic() if now is None else now
        cutoff = now - self._window
        hits = self._hits[key]
        while hits and hits[0] < cutoff:
            hits.popleft()
        if len(hits) >= self._max:
            return False
        hits.append(now)
        # Keep the map from growing without bound as keys go quiet.
        if len(self._hits) > 10_000:
            self._prune(cutoff)
        return True

    def _prune(self, cutoff: float) -> None:
        for key in [k for k, dq in self._hits.items() if not dq or dq[-1] < cutoff]:
            del self._hits[key]

    def reset(self) -> None:
        self._hits.clear()
