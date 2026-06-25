"""Rate limiter module for health check probes."""
import time
import threading
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    """Token bucket rate limiter."""
    rate: float  # tokens per second
    capacity: float  # max burst
    tokens: float = field(init=False)
    last_refill: float = field(init=False)
    lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    throttled_count: int = field(default=0, init=False)

    def __post_init__(self):
        self.tokens = self.capacity
        self.last_refill = time.monotonic()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now

    def acquire(self, timeout: float = 0) -> bool:
        """Try to acquire a token. Returns True if acquired."""
        deadline = time.monotonic() + timeout
        while True:
            with self.lock:
                self._refill()
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return True
                self.throttled_count += 1
            if time.monotonic() >= deadline:
                return False
            time.sleep(min(0.05, 1.0 / self.rate))

    def stats(self) -> dict:
        """Return rate limiter stats."""
        with self.lock:
            self._refill()
            return {
                "current_tokens": round(self.tokens, 2),
                "rate_per_sec": self.rate,
                "capacity": self.capacity,
                "throttled_requests": self.throttled_count,
            }


def create_probe_limiter(probe_rate: float = 5.0, half_open: bool = False) -> TokenBucket:
    """Create a rate limiter for health probes.

    Args:
        probe_rate: Max probes per second.
        half_open: If True, reduce rate to 50% (circuit breaker half-open state).
    """
    effective_rate = probe_rate * 0.5 if half_open else probe_rate
    return TokenBucket(rate=effective_rate, capacity=effective_rate * 2)
