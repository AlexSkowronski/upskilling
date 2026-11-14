"""Builder: assemble a complex object step by step, validating as you go.

``SelectBuilder`` builds a parameterised SQL query. Two details make it more than a toy:

* It is **immutable**: every method returns a new builder, so a base query can be shared
  and specialised without one branch leaking into another.
* Values never go into the SQL string. They go into ``params`` (to avoid SQL injection),
  and identifiers (table and column names) are checked against a strict pattern.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


def _check_identifier(name: str) -> str:
    if not _IDENTIFIER.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


@dataclass(frozen=True)
class Query:
    sql: str
    params: tuple[Any, ...]


@dataclass(frozen=True)
class SelectBuilder:
    _table: str | None = None
    _columns: tuple[str, ...] = ()
    _conditions: tuple[tuple[str, tuple[Any, ...]], ...] = ()
    _order_by: tuple[tuple[str, str], ...] = ()
    _limit: int | None = None
    _offset: int | None = None

    def from_(self, table: str) -> SelectBuilder:
        return replace(self, _table=_check_identifier(table))

    def select(self, *columns: str) -> SelectBuilder:
        return replace(self, _columns=self._columns + tuple(map(_check_identifier, columns)))

    def where(self, condition: str, *params: Any) -> SelectBuilder:
        """Add a condition using ``?`` placeholders, e.g. ``where("total > ?", 100)``."""
        expected = condition.count("?")
        if expected != len(params):
            raise ValueError(f"{condition!r} needs {expected} values, got {len(params)}")
        return replace(self, _conditions=self._conditions + ((condition, params),))

    def where_in(self, column: str, values: list[Any] | tuple[Any, ...]) -> SelectBuilder:
        if not values:
            raise ValueError("where_in() needs at least one value; 'IN ()' is invalid SQL")
        placeholders = ", ".join("?" for _ in values)
        return self.where(f"{_check_identifier(column)} IN ({placeholders})", *values)

    def order_by(self, column: str, direction: str = "ASC") -> SelectBuilder:
        direction = direction.upper()
        if direction not in ("ASC", "DESC"):
            raise ValueError(f"direction must be ASC or DESC, not {direction!r}")
        return replace(self, _order_by=self._order_by + ((_check_identifier(column), direction),))

    def limit(self, n: int) -> SelectBuilder:
        if n <= 0:
            raise ValueError("limit must be positive")
        return replace(self, _limit=n)

    def offset(self, n: int) -> SelectBuilder:
        if n < 0:
            raise ValueError("offset cannot be negative")
        return replace(self, _offset=n)

    def build(self) -> Query:
        # Rules that span several steps are checked once, at the end.
        if self._table is None:
            raise ValueError("Call from_() before build()")
        if self._offset is not None and self._limit is None:
            raise ValueError("offset() requires limit()")

        parts = [f"SELECT {', '.join(self._columns) or '*'}", f"FROM {self._table}"]
        params: list[Any] = []

        if self._conditions:
            parts.append("WHERE " + " AND ".join(f"({cond})" for cond, _ in self._conditions))
            for _, values in self._conditions:
                params.extend(values)
        if self._order_by:
            parts.append("ORDER BY " + ", ".join(f"{col} {dir_}" for col, dir_ in self._order_by))
        if self._limit is not None:
            parts.append("LIMIT ?")
            params.append(self._limit)
        if self._offset is not None:
            parts.append("OFFSET ?")
            params.append(self._offset)

        return Query(" ".join(parts), tuple(params))
