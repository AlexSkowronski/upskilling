# Upskilling repo: conventions

This repo is Alex's learning space for software design and architecture.
Alex sets a topic; Claude builds it for Alex to review later, often on a phone.
Optimise for **readability and learning**, not production completeness.

## Workflow

- One topic per branch, named `topic/NN-short-name`, and one pull request per topic.
- Never commit topic work straight to `main`.
- The PR description says what the topic shows, which files to read first, and two or three
  questions to think about while reviewing.
- Add the topic to the table in the root `README.md` in the same PR.

## Folder layout

Each topic is a numbered folder at the repo root, numbered in the order topics are added:

```
NN-topic-name/
├── README.md          # the concept, when to use it, when NOT to, and how the code maps to it
├── <package_name>/    # a Python package with a unique, valid name (e.g. outbox/)
│   └── ...
└── tests/
    └── test_*.py
```

- The root `conftest.py` puts every topic folder on the import path, so tests import the
  package directly (`from outbox.service import ...`). Package names must be unique across topics.
- Where a topic compares approaches, show them side by side (e.g. `before.py` / `after.py`,
  or `layered/` and `hexagonal/`).

## Code style

- Python 3.12+, type hints everywhere, `dataclass` and `typing.Protocol` over heavy class trees.
- Standard library only, unless the topic is about a specific library; add any dependency to
  `pyproject.toml` with a comment saying which topic needs it.
- Generic, easy-to-follow domains (orders, library loans, bookings, payments).
- Small files; short comments only where they teach something non-obvious.
- Use in-memory fakes rather than real databases, queues or networks, so every test runs offline in seconds.

## Topic README template

1. **The idea**: two or three sentences.
2. **The problem it solves**: a concrete example of the pain.
3. **How the code shows it**: which file to read first, and what to notice.
4. **Trade-offs**: what it costs, and when not to use it.
5. **Further reading**: one or two links at most.

## Before opening a PR

- `uv run pytest` passes.
- `uv run ruff check .` is clean.
