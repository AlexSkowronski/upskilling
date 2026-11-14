"""State: an object whose behaviour changes with its state, without if/elif on a status field.

An order moves through Pending → Paid → Shipped → Delivered, and can be Cancelled on the way.
Without this pattern, every method starts with ``if self.status == "paid": ... elif ...``,
and the rules for one state are scattered across every method.

With it, each state is a class that answers "what can happen from here?". The base class
rejects everything, and each state overrides only the transitions it allows, so the rules for
one state live in one place. ``Order`` (the "context") just delegates to its current state
and records history.

For a handful of states with no per-state behaviour, a transition table such as
``{("paid", "ship"): "shipped"}`` is simpler. Reach for this pattern once states carry
real behaviour, like the refund on cancelling a paid order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


class InvalidTransition(Exception):
    pass


class OrderState:
    name = "base"

    def pay(self, order: Order, payment_ref: str) -> OrderState:
        raise InvalidTransition(f"Cannot pay an order that is {self.name}")

    def ship(self, order: Order, tracking_number: str) -> OrderState:
        raise InvalidTransition(f"Cannot ship an order that is {self.name}")

    def deliver(self, order: Order) -> OrderState:
        raise InvalidTransition(f"Cannot deliver an order that is {self.name}")

    def cancel(self, order: Order, reason: str) -> OrderState:
        raise InvalidTransition(f"Cannot cancel an order that is {self.name}")


class Pending(OrderState):
    name = "pending"

    def pay(self, order: Order, payment_ref: str) -> OrderState:
        order.payment_ref = payment_ref
        return Paid()

    def cancel(self, order: Order, reason: str) -> OrderState:
        order.cancel_reason = reason
        return Cancelled()


class Paid(OrderState):
    name = "paid"

    def ship(self, order: Order, tracking_number: str) -> OrderState:
        order.tracking_number = tracking_number
        return Shipped()

    def cancel(self, order: Order, reason: str) -> OrderState:
        # Behaviour that only exists in this state: money was taken, so a refund is due.
        order.cancel_reason = reason
        order.refund_due = True
        return Cancelled()


class Shipped(OrderState):
    name = "shipped"

    def deliver(self, order: Order) -> OrderState:
        return Delivered()


class Delivered(OrderState):
    name = "delivered"  # terminal: everything is rejected by the base class


class Cancelled(OrderState):
    name = "cancelled"  # terminal


@dataclass
class Transition:
    from_state: str
    to_state: str
    at: datetime


@dataclass
class Order:
    order_id: str
    state: OrderState = field(default_factory=Pending)
    payment_ref: str | None = None
    tracking_number: str | None = None
    cancel_reason: str | None = None
    refund_due: bool = False
    history: list[Transition] = field(default_factory=list)

    @property
    def status(self) -> str:
        return self.state.name

    def pay(self, payment_ref: str) -> None:
        self._move_to(self.state.pay(self, payment_ref))

    def ship(self, tracking_number: str) -> None:
        self._move_to(self.state.ship(self, tracking_number))

    def deliver(self) -> None:
        self._move_to(self.state.deliver(self))

    def cancel(self, reason: str) -> None:
        self._move_to(self.state.cancel(self, reason))

    def _move_to(self, new_state: OrderState) -> None:
        self.history.append(Transition(self.state.name, new_state.name, datetime.now(UTC)))
        self.state = new_state
