"""Strategy: swappable algorithms behind one interface, chosen at runtime.

Each shipping method prices a parcel differently. Rather than one function full of branches,
each method is a **strategy**: any callable ``(Parcel) -> Decimal | None``, where ``None``
means "this method can't ship this parcel".

The Pythonic part: a strategy can be a plain function (``flat_rate``, built by a closure)
or a class with ``__call__`` (``WeightBands``, which has configuration worth naming).
``FreeOver`` takes *another strategy* and wraps it, showing that strategies compose.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Parcel:
    weight_kg: Decimal
    country: str
    order_total: Decimal


type ShippingStrategy = Callable[[Parcel], Decimal | None]


def flat_rate(price: Decimal, countries: set[str]) -> ShippingStrategy:
    def quote(parcel: Parcel) -> Decimal | None:
        return price if parcel.country in countries else None

    return quote


class WeightBands:
    """Tiered pricing: the first band whose max weight fits the parcel sets the price."""

    def __init__(self, bands: Sequence[tuple[Decimal, Decimal]], countries: set[str]) -> None:
        if list(bands) != sorted(bands):
            raise ValueError("Bands must be sorted by max weight")
        self._bands = tuple(bands)
        self._countries = countries

    def __call__(self, parcel: Parcel) -> Decimal | None:
        if parcel.country not in self._countries:
            return None
        for max_kg, price in self._bands:
            if parcel.weight_kg <= max_kg:
                return price
        return None  # too heavy for this service


class FreeOver:
    """Wraps another strategy: free if the order is big enough, otherwise defer to it."""

    def __init__(self, threshold: Decimal, inner: ShippingStrategy) -> None:
        self._threshold = threshold
        self._inner = inner

    def __call__(self, parcel: Parcel) -> Decimal | None:
        price = self._inner(parcel)
        if price is not None and parcel.order_total >= self._threshold:
            return Decimal("0.00")
        return price


@dataclass(frozen=True)
class Quote:
    method: str
    price: Decimal


class NoShippingAvailable(Exception):
    pass


class ShippingCalculator:
    """The 'context': it knows nothing about how any method calculates its price."""

    def __init__(self, methods: Mapping[str, ShippingStrategy]) -> None:
        self._methods = dict(methods)

    def quotes(self, parcel: Parcel) -> list[Quote]:
        available = [
            Quote(name, price)
            for name, strategy in self._methods.items()
            if (price := strategy(parcel)) is not None
        ]
        return sorted(available, key=lambda q: (q.price, q.method))

    def cheapest(self, parcel: Parcel) -> Quote:
        options = self.quotes(parcel)
        if not options:
            raise NoShippingAvailable(f"No shipping method for {parcel}")
        return options[0]
