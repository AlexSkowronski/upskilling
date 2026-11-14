from decimal import Decimal

import pytest
from design_patterns.structural.proxy import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    GuardedRateService,
    RateUnavailable,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class FlakyRates:
    def __init__(self) -> None:
        self.down = False
        self.calls = 0

    def rate(self, base: str, quote: str) -> Decimal:
        self.calls += 1
        if self.down:
            raise TimeoutError("rates API timed out")
        return Decimal("1.17")


def fail():
    raise TimeoutError


def test_breaker_opens_after_threshold_and_fails_fast():
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=2, reset_timeout=30, clock=clock)
    for _ in range(2):
        with pytest.raises(TimeoutError):
            breaker.call(fail)
    assert breaker.state is CircuitState.OPEN

    calls = []
    with pytest.raises(CircuitOpenError):
        breaker.call(lambda: calls.append("should not run"))
    assert calls == []


def test_breaker_half_opens_after_timeout_then_closes_on_success():
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=1, reset_timeout=30, clock=clock)
    with pytest.raises(TimeoutError):
        breaker.call(fail)
    clock.now = 30
    assert breaker.state is CircuitState.HALF_OPEN
    assert breaker.call(lambda: "ok") == "ok"
    assert breaker.state is CircuitState.CLOSED


def test_a_failed_trial_call_reopens_the_circuit():
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=3, reset_timeout=30, clock=clock)
    for _ in range(3):
        with pytest.raises(TimeoutError):
            breaker.call(fail)
    clock.now = 30
    with pytest.raises(TimeoutError):
        breaker.call(fail)  # one trial failure is enough
    assert breaker.state is CircuitState.OPEN


def test_success_resets_the_failure_count():
    breaker = CircuitBreaker(failure_threshold=2, clock=FakeClock())
    with pytest.raises(TimeoutError):
        breaker.call(fail)
    breaker.call(lambda: None)
    with pytest.raises(TimeoutError):
        breaker.call(fail)
    assert breaker.state is CircuitState.CLOSED


def test_proxy_serves_stale_rate_while_the_service_is_down():
    real = FlakyRates()
    proxy = GuardedRateService(real, CircuitBreaker(failure_threshold=2, clock=FakeClock()))
    assert proxy.rate("GBP", "EUR") == Decimal("1.17")

    real.down = True
    for _ in range(5):
        assert proxy.rate("GBP", "EUR") == Decimal("1.17")
    assert real.calls == 3  # 1 good call + 2 failures, then the breaker stops further calls


def test_proxy_raises_when_there_is_no_fallback():
    real = FlakyRates()
    real.down = True
    proxy = GuardedRateService(real, CircuitBreaker(clock=FakeClock()))
    with pytest.raises(RateUnavailable):
        proxy.rate("GBP", "USD")
