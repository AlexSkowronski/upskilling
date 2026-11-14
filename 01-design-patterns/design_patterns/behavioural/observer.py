"""Observer (in-process pub/sub): announce that something happened; whoever cares reacts.

Three details make this closer to real event buses than the textbook version:

* **Typed events.** Handlers subscribe to an event *class*. Subscribing to a base class
  (``OrderEvent``) also receives every subclass (``OrderPlaced``, ``OrderShipped``), by
  walking the event's MRO (method resolution order).
* **Error isolation.** One failing handler doesn't stop the others. Failures are collected
  and returned, so the publisher decides what to do (log, alert, retry).
* **Unsubscribing.** ``subscribe()`` returns a function that removes the handler again.

The publisher never imports the handlers. New reactions (analytics, emails, warehouse) are
added without touching the code that publishes the event.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


# --- Events: immutable facts, named in the past tense ------------------------------------


@dataclass(frozen=True)
class Event:
    pass


@dataclass(frozen=True)
class OrderEvent(Event):
    order_id: str


@dataclass(frozen=True)
class OrderPlaced(OrderEvent):
    customer_email: str
    total: Decimal


@dataclass(frozen=True)
class OrderShipped(OrderEvent):
    tracking_number: str


# --- The bus -----------------------------------------------------------------------------

type Handler = Callable[[Any], None]


@dataclass
class HandlerFailure:
    handler: Handler
    error: Exception


@dataclass
class PublishResult:
    delivered: int = 0
    failures: list[HandlerFailure] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[Handler]] = defaultdict(list)

    def subscribe[E: Event](
        self, event_type: type[E], handler: Callable[[E], None]
    ) -> Callable[[], None]:
        self._handlers[event_type].append(handler)

        def unsubscribe() -> None:
            if handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)

        return unsubscribe

    def publish(self, event: Event) -> PublishResult:
        result = PublishResult()
        for handler in self._handlers_for(type(event)):
            try:
                handler(event)
                result.delivered += 1
            except Exception as exc:
                logger.exception("Handler %r failed for %r", handler, event)
                result.failures.append(HandlerFailure(handler, exc))
        return result

    def _handlers_for(self, event_type: type) -> list[Handler]:
        # Most specific class first, then its base classes. Each handler runs at most once.
        seen: list[Handler] = []
        for cls in event_type.__mro__:
            for handler in self._handlers.get(cls, []):
                if handler not in seen:
                    seen.append(handler)
        return seen
