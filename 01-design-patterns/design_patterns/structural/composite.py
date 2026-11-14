"""Composite (as the Specification pattern): build complex rules from simple ones.

A Composite treats single objects and groups of objects through the same interface. Here
each business rule is a ``Spec``. A ``Rule`` is a leaf, and ``AllOf``, ``AnyOf`` and ``Not``
are composites holding other specs. Because they all share one interface, rules nest freely
and read almost like the business requirement:

    eligible = (is_vip | min_spend(500)) & in_countries("GB", "IE") & ~has_overdue_invoice

``why_not()`` walks the same tree to explain *which* rules failed. That's useful for support
staff, for error messages, and for testing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal


class Spec[T](ABC):
    @abstractmethod
    def is_satisfied_by(self, candidate: T) -> bool: ...

    @abstractmethod
    def why_not(self, candidate: T) -> list[str]:
        """Human-readable reasons the candidate fails; an empty list means it passes."""

    def __and__(self, other: Spec[T]) -> Spec[T]:
        return AllOf(self, other)

    def __or__(self, other: Spec[T]) -> Spec[T]:
        return AnyOf(self, other)

    def __invert__(self) -> Spec[T]:
        return Not(self)


class Rule[T](Spec[T]):
    """Leaf: a named predicate."""

    def __init__(self, name: str, predicate: Callable[[T], bool]) -> None:
        self.name = name
        self._predicate = predicate

    def is_satisfied_by(self, candidate: T) -> bool:
        return self._predicate(candidate)

    def why_not(self, candidate: T) -> list[str]:
        return [] if self.is_satisfied_by(candidate) else [self.name]

    def __repr__(self) -> str:
        return self.name


class AllOf[T](Spec[T]):
    def __init__(self, *specs: Spec[T]) -> None:
        # Flatten (a & b) & c into AllOf(a, b, c), so explanations and reprs stay readable.
        flat: list[Spec[T]] = []
        for spec in specs:
            flat.extend(spec.specs if isinstance(spec, AllOf) else [spec])
        self.specs = tuple(flat)

    def is_satisfied_by(self, candidate: T) -> bool:
        return all(spec.is_satisfied_by(candidate) for spec in self.specs)

    def why_not(self, candidate: T) -> list[str]:
        return [reason for spec in self.specs for reason in spec.why_not(candidate)]

    def __repr__(self) -> str:
        return "(" + " AND ".join(map(repr, self.specs)) + ")"


class AnyOf[T](Spec[T]):
    def __init__(self, *specs: Spec[T]) -> None:
        flat: list[Spec[T]] = []
        for spec in specs:
            flat.extend(spec.specs if isinstance(spec, AnyOf) else [spec])
        self.specs = tuple(flat)

    def is_satisfied_by(self, candidate: T) -> bool:
        return any(spec.is_satisfied_by(candidate) for spec in self.specs)

    def why_not(self, candidate: T) -> list[str]:
        if self.is_satisfied_by(candidate):
            return []
        return [f"needs one of: {' / '.join(map(repr, self.specs))}"]

    def __repr__(self) -> str:
        return "(" + " OR ".join(map(repr, self.specs)) + ")"


class Not[T](Spec[T]):
    def __init__(self, spec: Spec[T]) -> None:
        self.spec = spec

    def is_satisfied_by(self, candidate: T) -> bool:
        return not self.spec.is_satisfied_by(candidate)

    def why_not(self, candidate: T) -> list[str]:
        return [] if self.is_satisfied_by(candidate) else [f"must not be: {self.spec!r}"]

    def __repr__(self) -> str:
        return f"NOT {self.spec!r}"


# --- A worked example: promotion eligibility ---------------------------------------------


@dataclass(frozen=True)
class Customer:
    country: str
    total_spend: Decimal
    is_vip: bool = False
    has_overdue_invoice: bool = False


def min_spend(amount: int | Decimal) -> Spec[Customer]:
    return Rule(f"spent at least {amount}", lambda c: c.total_spend >= Decimal(amount))


def in_countries(*codes: str) -> Spec[Customer]:
    return Rule(f"based in {'/'.join(codes)}", lambda c: c.country in codes)


is_vip: Spec[Customer] = Rule("VIP", lambda c: c.is_vip)
has_overdue_invoice: Spec[Customer] = Rule(
    "has an overdue invoice", lambda c: c.has_overdue_invoice
)

loyalty_promotion: Spec[Customer] = (
    (is_vip | min_spend(500)) & in_countries("GB", "IE") & ~has_overdue_invoice
)
