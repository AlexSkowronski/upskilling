# Upskilling

Small, focused Python projects for learning software design and architecture.
Each topic lives in its own numbered folder with a short explanation, working code and tests.

## How it works

1. Alex picks a topic.
2. Claude builds it on its own branch and opens a pull request.
3. Alex reviews the pull request later, reading the topic README first, then the code and tests.

## Topics

| # | Topic | Folder |
| --- | --- | --- |
| 01 | Design patterns: 15 patterns in realistic Python | [`01-design-patterns`](01-design-patterns/) |

## Running the code

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync                    # install dev tools
uv run pytest              # run every topic's tests
uv run pytest 01-example   # run one topic
uv run ruff check .        # lint
```
