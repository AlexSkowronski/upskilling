from decimal import Decimal

from design_patterns.behavioural.observer import (
    EventBus,
    OrderEvent,
    OrderPlaced,
    OrderShipped,
)

PLACED = OrderPlaced("ORD-1", "ada@example.com", Decimal("25.00"))


def test_handlers_receive_events_of_their_type_only():
    bus = EventBus()
    emails, tracking = [], []
    bus.subscribe(OrderPlaced, lambda e: emails.append(e.customer_email))
    bus.subscribe(OrderShipped, lambda e: tracking.append(e.tracking_number))

    bus.publish(PLACED)
    assert emails == ["ada@example.com"]
    assert tracking == []


def test_subscribing_to_a_base_class_receives_all_subclasses():
    bus = EventBus()
    audit: list[str] = []
    bus.subscribe(OrderEvent, lambda e: audit.append(type(e).__name__))

    bus.publish(PLACED)
    bus.publish(OrderShipped("ORD-1", "TRK-1"))
    assert audit == ["OrderPlaced", "OrderShipped"]


def test_a_failing_handler_does_not_stop_the_others():
    bus = EventBus()
    received: list[str] = []

    def broken(event):
        raise RuntimeError("analytics is down")

    bus.subscribe(OrderPlaced, broken)
    bus.subscribe(OrderPlaced, lambda e: received.append(e.order_id))

    result = bus.publish(PLACED)
    assert received == ["ORD-1"]
    assert result.delivered == 1
    assert not result.ok
    assert isinstance(result.failures[0].error, RuntimeError)


def test_unsubscribe_stops_delivery():
    bus = EventBus()
    received: list[str] = []
    unsubscribe = bus.subscribe(OrderPlaced, lambda e: received.append(e.order_id))
    unsubscribe()
    unsubscribe()  # safe to call twice
    assert bus.publish(PLACED).delivered == 0


def test_a_handler_subscribed_to_both_a_class_and_its_base_runs_once():
    bus = EventBus()
    calls: list[str] = []

    def handler(e):
        calls.append(e.order_id)

    bus.subscribe(OrderPlaced, handler)
    bus.subscribe(OrderEvent, handler)
    bus.publish(PLACED)
    assert calls == ["ORD-1"]
