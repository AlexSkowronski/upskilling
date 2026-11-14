import json

import pytest
from design_patterns.creational.factory import (
    ExporterRegistry,
    UnknownFormatError,
    registry,
)

ROWS = [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Grace", "team": "Navy"}]


def test_creates_exporters_by_name():
    assert json.loads(registry.create("json").export(ROWS)) == ROWS
    assert registry.create("csv").content_type == "text/csv"


def test_csv_includes_every_column_even_when_rows_differ():
    out = registry.create("csv").export(ROWS)
    assert out.splitlines() == ["id,name,team", "1,Ada,", "2,Grace,Navy"]


def test_options_are_passed_to_the_constructor():
    out = registry.create("csv", delimiter=";").export(ROWS)
    assert out.startswith("id;name;team")


def test_markdown_escapes_pipes():
    out = registry.create("markdown").export([{"note": "a|b"}])
    assert r"a\|b" in out


def test_unknown_format_lists_what_is_available():
    with pytest.raises(UnknownFormatError, match="csv, json, markdown"):
        registry.create("xml")


def test_new_formats_plug_in_without_editing_existing_code():
    fresh = ExporterRegistry()

    @fresh.register("count")
    class CountExporter:
        content_type = "text/plain"

        def export(self, records):
            return str(len(list(records)))

    assert fresh.create("count").export(ROWS) == "2"
    with pytest.raises(ValueError, match="already registered"):
        fresh.register("count")(CountExporter)
