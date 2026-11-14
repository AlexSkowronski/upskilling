"""Factory via a registry: pick which class to build at runtime, by name.

Adding a new export format means adding one class with ``@registry.register("name")``.
Nothing else is edited, so there is no if/elif chain to grow (Open/Closed principle).
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Protocol

type Record = Mapping[str, Any]


class Exporter(Protocol):
    content_type: str

    def export(self, records: Iterable[Record]) -> str: ...


class UnknownFormatError(LookupError):
    pass


class ExporterRegistry:
    """Maps a format name to a factory (here, the class itself) that builds an Exporter."""

    def __init__(self) -> None:
        self._factories: dict[str, Callable[..., Exporter]] = {}

    def register[T](self, name: str) -> Callable[[type[T]], type[T]]:
        def decorator(cls: type[T]) -> type[T]:
            if name in self._factories:
                raise ValueError(f"Exporter {name!r} is already registered")
            self._factories[name] = cls  # type: ignore[assignment]
            return cls

        return decorator

    def create(self, name: str, **options: Any) -> Exporter:
        try:
            factory = self._factories[name]
        except KeyError:
            available = ", ".join(self.available()) or "none"
            raise UnknownFormatError(f"No exporter for {name!r}. Available: {available}") from None
        return factory(**options)

    def available(self) -> list[str]:
        return sorted(self._factories)


# The application's shared registry. Tests can build their own ExporterRegistry instead.
registry = ExporterRegistry()


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    """Union of keys across all rows, in first-seen order (rows may have different keys)."""
    return list(dict.fromkeys(key for row in rows for key in row))


@registry.register("json")
class JsonExporter:
    content_type = "application/json"

    def __init__(self, indent: int | None = None) -> None:
        self.indent = indent

    def export(self, records: Iterable[Record]) -> str:
        return json.dumps([dict(r) for r in records], indent=self.indent, default=str)


@registry.register("csv")
class CsvExporter:
    content_type = "text/csv"

    def __init__(self, delimiter: str = ",") -> None:
        self.delimiter = delimiter

    def export(self, records: Iterable[Record]) -> str:
        rows = [dict(r) for r in records]
        if not rows:
            return ""
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer, fieldnames=_columns(rows), delimiter=self.delimiter, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
        return buffer.getvalue()


@registry.register("markdown")
class MarkdownTableExporter:
    content_type = "text/markdown"

    def export(self, records: Iterable[Record]) -> str:
        rows = [dict(r) for r in records]
        if not rows:
            return ""
        columns = _columns(rows)
        lines = [
            "| " + " | ".join(columns) + " |",
            "| " + " | ".join("---" for _ in columns) + " |",
        ]
        for row in rows:
            cells = (str(row.get(col, "")).replace("|", r"\|") for col in columns)
            lines.append("| " + " | ".join(cells) + " |")
        return "\n".join(lines)
