#!/usr/bin/env python3
"""Retry, backoff, and circuit-breaker logic for health_check HTTP probes."""
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

log = logging.getLogger("health_check.retry")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    threshold: int = 3
    cooldown: float = 30.0
    _failures: int = field(default=0, init=False)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _opened_at: float = field(default=0.0, init=False)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._opened_at >= self.cooldown:
                self._state = CircuitState.HALF_OPEN
        return self._state

    def record_success(self) -> None:
        self._failures = 0
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            log.warning("Circuit opened after %d failures", self._failures)

    def allow_request(self) -> bool:
        s = self.state
        if s in (CircuitState.CLOSED, CircuitState.HALF_OPEN):
            return True
        log.debug("Circuit OPEN - fast-failing")
        return False


def probe_with_retry(
    fn: Callable[[], bool],
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    base_delay: float = 0.5,
    circuit: Optional[CircuitBreaker] = None,
) -> bool:
    """Run fn with exponential backoff retries and optional circuit breaker.

    Args:
        fn: Callable that returns True on success or raises on failure.
        max_retries: Number of additional attempts after first failure.
        backoff_factor: Multiplier applied to base_delay each attempt.
        base_delay: Initial delay in seconds between retries.
        circuit: Optional CircuitBreaker instance to gate requests.
    Returns:
        True if probe succeeded, False otherwise.
    """
    if circuit and not circuit.allow_request():
        return False
    for attempt in range(max_retries + 1):
        try:
            result = fn()
            if circuit:
                circuit.record_success()
            return result
        except Exception as exc:
            if attempt < max_retries:
                delay = base_delay * (backoff_factor ** attempt)
                log.warning("Probe attempt %d failed (%s), retrying in %.1fs",
                            attempt + 1, exc, delay)
                time.sleep(delay)
            else:
                log.error("Probe failed after %d attempts: %s", max_retries + 1, exc)
    if circuit:
        circuit.record_failure()
    return False
