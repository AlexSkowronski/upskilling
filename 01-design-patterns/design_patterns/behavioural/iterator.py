"""Iterator: walk through a collection without knowing how it's stored or fetched.

In Python, generators *are* the Iterator pattern. ``paginate`` turns a cursor-paginated API
into one flat stream of items. The caller just writes ``for order in paginate(...)`` and
never sees pages, cursors or limits.

It's also **lazy**: pages are fetched only when the loop needs them. Taking the first 3
items from a million-row API costs one request, not ten thousand. ``batched`` goes the
other way, grouping a stream into chunks, e.g. for bulk database inserts.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from itertools import islice


@dataclass(frozen=True)
class Page[T]:
    items: list[T]
    next_cursor: str | None  # None means this was the last page


type FetchPage[T] = Callable[[str | None, int], Page[T]]


def paginate[T](fetch_page: FetchPage[T], page_size: int = 100) -> Iterator[T]:
    """Yield every item across all pages, fetching each page only when it's needed."""
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    cursor: str | None = None
    seen_cursors: set[str] = set()
    while True:
        page = fetch_page(cursor, page_size)
        yield from page.items
        if page.next_cursor is None:
            return
        if page.next_cursor in seen_cursors:
            # A buggy API returning the same cursor again would otherwise loop forever.
            raise RuntimeError(f"Pagination loop detected at cursor {page.next_cursor!r}")
        seen_cursors.add(page.next_cursor)
        cursor = page.next_cursor


def batched[T](items: Iterable[T], size: int) -> Iterator[list[T]]:
    """Group a (possibly endless) stream into lists of ``size``; the last may be shorter.

    (Python 3.12 has ``itertools.batched``, which yields tuples. This shows how it works.)
    """
    if size <= 0:
        raise ValueError("size must be positive")
    iterator = iter(items)
    while batch := list(islice(iterator, size)):
        yield batch
