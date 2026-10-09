import threading
import time
from collections import defaultdict
from typing import Dict, List
from fastapi import HTTPException, status


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window in-memory rate limiter for sensitive endpoints."""

    def __init__(self):
        self._lock = threading.Lock()
        self._records: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, key: str, max_requests: int = 15, window_seconds: int = 60) -> bool:
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            history = self._records[key]
            # Prune timestamps older than window
            valid_history = [ts for ts in history if ts > cutoff]
            if len(valid_history) >= max_requests:
                self._records[key] = valid_history
                return False
            valid_history.append(now)
            self._records[key] = valid_history
            return True

    def enforce(self, key: str, max_requests: int = 15, window_seconds: int = 60) -> None:
        if not self.is_allowed(key, max_requests, window_seconds):
            from app.api.errors import RateLimitExceededError
            raise RateLimitExceededError("Too many authentication requests. Please try again later.")

    def reset(self) -> None:
        """Reset rate limiter state (used in testing)."""
        with self._lock:
            self._records.clear()


rate_limiter = SlidingWindowRateLimiter()
