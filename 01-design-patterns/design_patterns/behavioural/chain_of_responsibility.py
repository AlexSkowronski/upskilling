"""Chain of Responsibility, as middleware: each link handles the request, or passes it on.

This is how web frameworks (WSGI/ASGI middleware, Django, Starlette) process requests.
Each middleware receives the request and ``call_next``, and can:

* **short-circuit** by returning a response itself (``authenticate`` returns 401 with no token),
* **pass the request on** by calling ``call_next(request)``,
* or **do work on both sides**, e.g. timing, adding headers, or catching errors from further in.

``build_chain`` wires the middlewares around the final endpoint. The first middleware in the
list is the *outermost* layer, so its order matters: the error handler goes first so it can
catch failures from every later link.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Request:
    path: str
    headers: Mapping[str, str] = field(default_factory=dict)
    user: str | None = None  # filled in by authenticate()


@dataclass(frozen=True)
class Response:
    status: int
    body: str = ""
    headers: Mapping[str, str] = field(default_factory=dict)


type Handler = Callable[[Request], Response]
type Middleware = Callable[[Request, Handler], Response]


def build_chain(middlewares: Sequence[Middleware], endpoint: Handler) -> Handler:
    handler = endpoint
    for middleware in reversed(middlewares):
        # Bind the current values now. A plain closure would see only the last ones.
        def link(request: Request, mw: Middleware = middleware, nxt: Handler = handler) -> Response:
            return mw(request, nxt)

        handler = link
    return handler


# --- Middlewares ------------------------------------------------------------------------


def error_handler(request: Request, call_next: Handler) -> Response:
    try:
        return call_next(request)
    except Exception:
        logger.exception("Unhandled error for %s", request.path)
        return Response(500, "Internal server error")


def request_id(request: Request, call_next: Handler) -> Response:
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    response = call_next(replace(request, headers={**request.headers, "X-Request-ID": rid}))
    return replace(response, headers={**response.headers, "X-Request-ID": rid})


def make_authenticate(tokens: Mapping[str, str]) -> Middleware:
    """``tokens`` maps API token -> username. Real systems would verify a JWT or session."""

    def authenticate(request: Request, call_next: Handler) -> Response:
        auth = request.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip()
        user = tokens.get(token)
        if user is None:
            return Response(401, "Unauthorised")
        return call_next(replace(request, user=user))

    return authenticate


def make_rate_limit(
    limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic
) -> Middleware:
    """Fixed-window limiter per user. Must come *after* authenticate in the chain."""
    counts: dict[tuple[str, int], int] = defaultdict(int)

    def rate_limit(request: Request, call_next: Handler) -> Response:
        window = int(clock() // window_seconds)
        key = (request.user or "anonymous", window)
        counts[key] += 1
        if counts[key] > limit:
            return Response(429, "Too many requests", {"Retry-After": str(int(window_seconds))})
        return call_next(request)

    return rate_limit
