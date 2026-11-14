import json

import pytest
from design_patterns.behavioural.template_method import (
    CsvCustomerImporter,
    JsonCustomerImporter,
    Pipeline,
    check_email,
    normalise,
    parse_csv,
    require,
)

CSV = """email,name
 Ada@Example.com ,Ada
not-an-email,Bob
,Nameless
grace@example.org,  Grace
"""

EXPECTED_ROWS = [
    {"email": "ada@example.com", "name": "Ada"},
    {"email": "grace@example.org", "name": "Grace"},
]
EXPECTED_ERRORS = [(2, "invalid email 'not-an-email'"), (3, "missing email")]


def test_template_method_importer_reports_per_row():
    store: list = []
    report = CsvCustomerImporter(store).run(CSV)
    assert report.imported == EXPECTED_ROWS
    assert report.errors == EXPECTED_ERRORS
    assert store == EXPECTED_ROWS


def test_json_importer_only_overrides_parsing():
    store: list = []
    raw = json.dumps([{"email": "a@b.co", "name": "A"}, {"email": "a@b.co"}])
    report = JsonCustomerImporter(store).run(raw)
    assert [r["email"] for r in report.imported] == ["a@b.co"]
    assert report.errors == [(2, "missing name")]


def test_pipeline_gives_the_same_result_by_composition():
    store: list = []
    pipeline = Pipeline(
        parse=parse_csv,
        steps=[require("email", "name"), check_email, normalise],
        save=store.append,
    )
    report = pipeline.run(CSV)
    assert report.imported == EXPECTED_ROWS
    assert report.errors == EXPECTED_ERRORS


def test_pipeline_steps_are_reusable_and_testable_alone():
    assert normalise({"email": " X@Y.COM ", "name": " n "}) == {"email": "x@y.com", "name": "n"}
    with pytest.raises(Exception, match="missing phone"):
        require("phone")({"phone": "  "})
