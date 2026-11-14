"""Decorator: add behaviour around something without changing it.

Python has two flavours, and both are shown here:

1. **Function decorators** (``@retry``, ``@ttl_cache``, ``@timed``): wrap a call.
2. **Object decorators** (the classic Gang of Four (GoF) version): a class that implements
   the same interface as the object it wraps, so wrappers can be stacked in any order,
   e.g. ``CachingCatalog(LoggingCatalog(real_catalog))``.

Time, sleeping and randomness are injected so the tests are fast and repeatable.
"""

from __future__ import annotations

import functools
import logging
import random
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from decimal import Decimal
from typing import Protocol

logger = logging.getLogger(__name__)


# --- 1. Function decorators ---------------------------------------------------------------


def retry[**P, R](
    *,
    attempts: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    sleep: Callable[[float], None] = time.sleep,
    rand: Callable[[], float] = random.random,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Retry with exponential backoff and "full jitter".

    The delay before attempt n+1 is a random value between 0 and min(max_delay, base * 2^(n-1)).
    The randomness stops many clients that failed together from all retrying in sync.
    Only exceptions in ``retry_on`` are retried; anything else fails immediately.
    """
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retry_on as exc:
                    if attempt == attempts:
                        raise
                    delay = min(max_delay, base_delay * 2 ** (attempt - 1)) * rand()
                    logger.warning(
                        "%s failed (%s), retry %d/%d in %.2fs",
                        func.__name__, exc, attempt, attempts - 1, delay,
                    )
                    sleep(delay)
            raise AssertionError("unreachable")

        return wrapper

    return decorator


def ttl_cache[**P, R](
    ttl: float, *, maxsize: int = 128, clock: Callable[[], float] = time.monotonic
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Cache results for ``ttl`` seconds, evicting the least recently used entry past ``maxsize``.

    ``functools.lru_cache`` never expires entries, which is wrong for data that goes stale
    (prices, exchange rates). This adds expiry on top of the LRU idea.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        cache: OrderedDict[Hashable, tuple[float, R]] = OrderedDict()

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            key = (args, tuple(sorted(kwargs.items())))
            now = clock()
            if key in cache:
                stored_at, value = cache[key]
                if now - stored_at < ttl:
                    cache.move_to_end(key)
                    return value
            value = func(*args, **kwargs)
            cache[key] = (now, value)
            cache.move_to_end(key)
            while len(cache) > maxsize:
                cache.popitem(last=False)
            return value

        wrapper.cache_clear = cache.clear  # type: ignore[attr-defined]
        return wrapper

    return decorator


def timed[**P, R](
    log: logging.Logger = logger, clock: Callable[[], float] = time.perf_counter
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Log how long each call took, even when it raises."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start = clock()
            try:
                return func(*args, **kwargs)
            finally:
                log.info("%s took %.1f ms", func.__qualname__, (clock() - start) * 1000)

        return wrapper

    return decorator


# --- 2. Object decorators (same interface, wraps another instance) ------------------------


class ProductCatalog(Protocol):
    def price_of(self, sku: str) -> Decimal: ...


class LoggingCatalog:
    def __init__(self, inner: ProductCatalog, log: logging.Logger = logger) -> None:
        self._inner = inner
        self._log = log

    def price_of(self, sku: str) -> Decimal:
        price = self._inner.price_of(sku)
        self._log.info("price_of(%s) -> %s", sku, price)
        return price


class CachingCatalog:
    """Caches prices until told otherwise, e.g. when a 'price changed' event arrives."""

    def __init__(self, inner: ProductCatalog) -> None:
        self._inner = inner
        self._cache: dict[str, Decimal] = {}

    def price_of(self, sku: str) -> Decimal:
        if sku not in self._cache:
            self._cache[sku] = self._inner.price_of(sku)
        return self._cache[sku]

    def invalidate(self, sku: str | None = None) -> None:
        if sku is None:
            self._cache.clear()
        else:
            self._cache.pop(sku, None)
