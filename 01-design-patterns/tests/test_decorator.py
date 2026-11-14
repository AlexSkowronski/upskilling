import logging
from decimal import Decimal

import pytest
from design_patterns.structural.decorator import (
    CachingCatalog,
    LoggingCatalog,
    retry,
    timed,
    ttl_cache,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


# --- retry ------------------------------------------------------------------------------


def test_retry_succeeds_after_transient_failures_with_growing_delays():
    sleeps: list[float] = []
    calls = {"n": 0}

    @retry(attempts=4, base_delay=1, max_delay=10, retry_on=(ConnectionError,),
           sleep=sleeps.append, rand=lambda: 1.0)
    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 4:
            raise ConnectionError("blip")
        return "ok"

    assert flaky() == "ok"
    assert sleeps == [1, 2, 4]  # exponential backoff


def test_retry_caps_the_delay_and_reraises_after_the_last_attempt():
    sleeps: list[float] = []

    @retry(attempts=5, base_delay=1, max_delay=3, sleep=sleeps.append, rand=lambda: 1.0)
    def always_fails() -> None:
        raise TimeoutError

    with pytest.raises(TimeoutError):
        always_fails()
    assert sleeps == [1, 2, 3, 3]


def test_retry_does_not_retry_unlisted_errors():
    calls = {"n": 0}

    @retry(attempts=3, retry_on=(ConnectionError,), sleep=lambda _: None)
    def bad_input() -> None:
        calls["n"] += 1
        raise ValueError("bug, not a blip")

    with pytest.raises(ValueError):
        bad_input()
    assert calls["n"] == 1


def test_retry_keeps_the_function_name():
    @retry(attempts=2)
    def fetch_orders() -> None: ...

    assert fetch_orders.__name__ == "fetch_orders"


# --- ttl_cache ----------------------------------------------------------------------------


def test_ttl_cache_expires_entries():
    clock = FakeClock()
    calls: list[str] = []

    @ttl_cache(ttl=60, clock=clock)
    def rate(currency: str) -> str:
        calls.append(currency)
        return f"rate-{currency}-{clock.now}"

    assert rate("EUR") == rate("EUR")
    clock.now = 59
    rate("EUR")
    assert calls == ["EUR"]
    clock.now = 60
    assert rate("EUR") == "rate-EUR-60"
    assert calls == ["EUR", "EUR"]


def test_ttl_cache_evicts_least_recently_used():
    calls: list[int] = []

    @ttl_cache(ttl=100, maxsize=2, clock=FakeClock())
    def square(n: int) -> int:
        calls.append(n)
        return n * n

    square(1)
    square(2)
    square(1)  # 1 is now most recently used
    square(3)  # evicts 2
    square(1)
    square(2)
    assert calls == [1, 2, 3, 2]


# --- timed ------------------------------------------------------------------------------


def test_timed_logs_even_when_the_call_fails(caplog):
    clock = iter([0.0, 0.25])

    @timed(clock=lambda: next(clock))
    def boom() -> None:
        raise RuntimeError

    with caplog.at_level(logging.INFO), pytest.raises(RuntimeError):
        boom()
    assert "boom took 250.0 ms" in caplog.text


# --- object decorators --------------------------------------------------------------------


class CountingCatalog:
    def __init__(self) -> None:
        self.calls = 0

    def price_of(self, sku: str) -> Decimal:
        self.calls += 1
        return Decimal("9.99")


def test_object_decorators_stack_and_keep_the_same_interface(caplog):
    real = CountingCatalog()
    catalog = CachingCatalog(LoggingCatalog(real))

    with caplog.at_level(logging.INFO):
        assert catalog.price_of("SKU-1") == Decimal("9.99")
        catalog.price_of("SKU-1")
    assert real.calls == 1
    assert caplog.text.count("price_of(SKU-1)") == 1  # second call never reached the logger

    catalog.invalidate("SKU-1")
    catalog.price_of("SKU-1")
    assert real.calls == 2
