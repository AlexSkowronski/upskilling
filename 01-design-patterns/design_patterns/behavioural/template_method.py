"""Template Method vs pipeline: two ways to fix the steps of a process but vary the details.

Both versions import customer records and report what succeeded and what failed, row by row.

**Template Method (inheritance).** ``BaseImporter.run`` is the template: parse → validate →
transform → save, in a fixed order, and it handles errors per row. Subclasses fill in the
gaps (``parse``, ``validate``, ...). You get a clear structure, but every variation needs a
subclass, and subclasses are tightly tied to the base class (see Module 2: composition over
inheritance).

**Pipeline (composition).** ``Pipeline`` is a list of plain functions run in order. Steps
can be reused, reordered and tested on their own, and a new import is a new list rather
than a new class.

In Python, the pipeline is usually the better default; Template Method suits frameworks that
must guarantee a fixed lifecycle.
"""

from __future__ import annotations

import csv
import io
import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

type Row = dict[str, Any]


class RowError(Exception):
    """A problem with one row. Recorded in the report; the import carries on."""


@dataclass
class ImportReport:
    imported: list[Row] = field(default_factory=list)
    errors: list[tuple[int, str]] = field(default_factory=list)  # (row number, message)

    @property
    def ok(self) -> bool:
        return not self.errors


# --- Version 1: Template Method -----------------------------------------------------------


class BaseImporter(ABC):
    def run(self, raw: str) -> ImportReport:
        """The template. Subclasses must not override this; they fill in the steps below."""
        report = ImportReport()
        for number, row in enumerate(self.parse(raw), start=1):
            try:
                self.validate(row)
                record = self.transform(row)
                self.save(record)
                report.imported.append(record)
            except RowError as exc:
                report.errors.append((number, str(exc)))
        return report

    @abstractmethod
    def parse(self, raw: str) -> Iterable[Row]: ...

    @abstractmethod
    def validate(self, row: Row) -> None: ...

    def transform(self, row: Row) -> Row:  # a "hook": optional to override
        return row

    @abstractmethod
    def save(self, record: Row) -> None: ...


class CsvCustomerImporter(BaseImporter):
    def __init__(self, store: list[Row]) -> None:
        self.store = store

    def parse(self, raw: str) -> Iterable[Row]:
        return csv.DictReader(io.StringIO(raw))

    def validate(self, row: Row) -> None:
        _require(row, "email", "name")
        _check_email(row)

    def transform(self, row: Row) -> Row:
        return _normalise(row)

    def save(self, record: Row) -> None:
        self.store.append(record)


class JsonCustomerImporter(CsvCustomerImporter):
    """Only the parsing differs. Note it inherits from the CSV importer just to reuse
    validate/transform: a sign that inheritance is being stretched."""

    def parse(self, raw: str) -> Iterable[Row]:
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("Expected a JSON list of customers")
        return data


# --- Version 2: Pipeline (composition) ----------------------------------------------------

type Step = Callable[[Row], Row]


class Pipeline:
    def __init__(self, parse: Callable[[str], Iterable[Row]], steps: Sequence[Step],
                 save: Callable[[Row], None]) -> None:
        self._parse = parse
        self._steps = tuple(steps)
        self._save = save

    def run(self, raw: str) -> ImportReport:
        report = ImportReport()
        for number, row in enumerate(self._parse(raw), start=1):
            try:
                for step in self._steps:
                    row = step(row)
                self._save(row)
                report.imported.append(row)
            except RowError as exc:
                report.errors.append((number, str(exc)))
        return report


def parse_csv(raw: str) -> Iterable[Row]:
    return csv.DictReader(io.StringIO(raw))


def require(*fields: str) -> Step:
    def step(row: Row) -> Row:
        _require(row, *fields)
        return row

    return step


def check_email(row: Row) -> Row:
    _check_email(row)
    return row


def normalise(row: Row) -> Row:
    return _normalise(row)


# --- Shared rules (used by both versions) -------------------------------------------------


def _require(row: Row, *fields: str) -> None:
    missing = [f for f in fields if not str(row.get(f) or "").strip()]
    if missing:
        raise RowError(f"missing {', '.join(missing)}")


def _check_email(row: Row) -> None:
    email = str(row["email"]).strip()
    local, _, domain = email.partition("@")
    if not local or "." not in domain:
        raise RowError(f"invalid email {email!r}")


def _normalise(row: Row) -> Row:
    return {**row, "email": str(row["email"]).strip().lower(), "name": str(row["name"]).strip()}
