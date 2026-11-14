from itertools import islice

import pytest
from design_patterns.behavioural.iterator import Page, batched, paginate


class FakeApi:
    """Serves ``total`` items in pages, using the next start index as the cursor."""

    def __init__(self, total: int) -> None:
        self.total = total
        self.requests: list[str | None] = []

    def fetch(self, cursor: str | None, limit: int) -> Page[int]:
        self.requests.append(cursor)
        start = int(cursor or 0)
        end = min(start + limit, self.total)
        next_cursor = str(end) if end < self.total else None
        return Page(list(range(start, end)), next_cursor)


def test_flattens_every_page():
    api = FakeApi(total=25)
    assert list(paginate(api.fetch, page_size=10)) == list(range(25))
    assert api.requests == [None, "10", "20"]


def test_is_lazy_and_only_fetches_what_is_consumed():
    api = FakeApi(total=1_000_000)
    first_three = list(islice(paginate(api.fetch, page_size=100), 3))
    assert first_three == [0, 1, 2]
    assert len(api.requests) == 1


def test_empty_result():
    assert list(paginate(FakeApi(total=0).fetch)) == []


def test_detects_an_api_that_repeats_a_cursor():
    def stuck(cursor, limit):
        return Page([1], "same")

    with pytest.raises(RuntimeError, match="loop"):
        list(paginate(stuck))


def test_batched_groups_a_stream():
    assert list(batched(range(7), 3)) == [[0, 1, 2], [3, 4, 5], [6]]


def test_paginate_and_batched_compose_for_bulk_work():
    api = FakeApi(total=250)
    batches = list(batched(paginate(api.fetch, page_size=100), 120))
    assert [len(b) for b in batches] == [120, 120, 10]
