import pytest
from design_patterns.behavioural.state import InvalidTransition, Order


def test_happy_path_and_history():
    order = Order("ORD-1")
    order.pay("PAY-1")
    order.ship("TRK-1")
    order.deliver()

    assert order.status == "delivered"
    assert order.tracking_number == "TRK-1"
    assert [(t.from_state, t.to_state) for t in order.history] == [
        ("pending", "paid"), ("paid", "shipped"), ("shipped", "delivered"),
    ]


def test_cancelling_a_pending_order_needs_no_refund():
    order = Order("ORD-1")
    order.cancel("changed mind")
    assert order.status == "cancelled"
    assert not order.refund_due


def test_cancelling_a_paid_order_flags_a_refund():
    order = Order("ORD-1")
    order.pay("PAY-1")
    order.cancel("out of stock")
    assert order.refund_due


@pytest.mark.parametrize(
    ("setup", "action"),
    [
        ([], lambda o: o.ship("TRK")),  # can't ship before paying
        ([], lambda o: o.deliver()),
        (["pay"], lambda o: o.pay("again")),  # can't pay twice
        (["pay", "ship"], lambda o: o.cancel("too late")),  # can't cancel once shipped
        (["cancel"], lambda o: o.pay("PAY")),  # terminal state
    ],
)
def test_invalid_transitions_are_rejected_and_change_nothing(setup, action):
    order = Order("ORD-1")
    steps = {"pay": lambda: order.pay("P"), "ship": lambda: order.ship("T"),
             "cancel": lambda: order.cancel("r")}
    for name in setup:
        steps[name]()
    status_before, history_before = order.status, len(order.history)

    with pytest.raises(InvalidTransition):
        action(order)
    assert order.status == status_before
    assert len(order.history) == history_before
