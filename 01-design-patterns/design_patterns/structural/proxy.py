"""Proxy: a stand-in with the same interface that controls access to the real object.

``GuardedRateService`` looks exactly like an ``ExchangeRateService``, but it puts two
protections in front of the real (remote, unreliable) service:

* A **circuit breaker**: after ``failure_threshold`` failures in a row the circuit "opens"
  and calls fail fast for ``reset_timeout`` seconds, instead of piling up slow timeouts
  against a service that's already struggling. After that wait, one trial call is let
  through (HALF_OPEN). If it succeeds, the circuit closes; if not, it opens again.
* A **stale fallback**: while the circuit is open, return the last good rate, if there is
  one, rather than failing the whole request.

Callers don't know any of this is happening, which is the point of a proxy.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from decimal import Decimal
from enum import Enum, auto
from typing import Protocol


class CircuitState(Enum):
    CLOSED = auto()  # normal: calls go through
    OPEN = auto()  # failing: calls are rejected immediately
    HALF_OPEN = auto()  # testing: one trial call is allowed


class CircuitOpenError(Exception):
    pass


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        reset_timeout: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._clock = clock
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at = 0.0

    @property
    def state(self) -> CircuitState:
        if (
            self._state is CircuitState.OPEN
            and self._clock() - self._opened_at >= self.reset_timeout
        ):
            self._state = CircuitState.HALF_OPEN
        return self._state

    def call[R](self, func: Callable[[], R]) -> R:
        if self.state is CircuitState.OPEN:
            raise CircuitOpenError("Circuit is open; not calling the service")
        try:
            result = func()
        except Exception:
            self._record_failure()
            raise
        self._record_success()
        return result

    def _record_failure(self) -> None:
        self._failures += 1
        if self._state is CircuitState.HALF_OPEN or self._failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = self._clock()

    def _record_success(self) -> None:
        self._failures = 0
        self._state = CircuitState.CLOSED


class ExchangeRateService(Protocol):
    def rate(self, base: str, quote: str) -> Decimal: ...


class RateUnavailable(Exception):
    pass


class GuardedRateService:
    """Proxy: same ``rate()`` method as the real service, plus a breaker and a fallback."""

    def __init__(self, real: ExchangeRateService, breaker: CircuitBreaker) -> None:
        self._real = real
        self._breaker = breaker
        self._last_good: dict[tuple[str, str], Decimal] = {}

    def rate(self, base: str, quote: str) -> Decimal:
        key = (base, quote)
        try:
            value = self._breaker.call(lambda: self._real.rate(base, quote))
        except Exception as exc:
            if key in self._last_good:
                return self._last_good[key]
            raise RateUnavailable(f"No rate for {base}/{quote}") from exc
        self._last_good[key] = value
        return value
