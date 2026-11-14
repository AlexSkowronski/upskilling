"""Facade: one simple entry point in front of a subsystem that's fiddly to use correctly.

Placing an order touches inventory, payments and notifications, in a specific order and with
clean-up when something fails part-way through. Callers (an API endpoint, a CLI, a test)
shouldn't each have to get that right. ``CheckoutFacade.place_order`` does it once:

1. Reserve stock. Fails fast if anything is out of stock.
2. Charge the card. On failure, **release the reservation** so stock isn't lost.
3. Commit the reservation.
4. Send the confirmation email. A failure here is logged, not raised: the customer has
   paid and the order stands.

The facade adds no new business rules. It coordinates, and the subsystems stay usable directly.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CartLine:
    sku: str
    quantity: int
    unit_price: Decimal


@dataclass(frozen=True)
class OrderConfirmation:
    order_id: str
    total: Decimal
    payment_reference: str
    email_sent: bool


class CheckoutError(Exception):
    pass


class OutOfStock(CheckoutError):
    pass


class PaymentFailed(CheckoutError):
    pass


class Inventory(Protocol):
    def reserve(self, lines: Sequence[CartLine]) -> str:
        """Hold stock and return a reservation id. Raises OutOfStock."""
        ...

    def commit(self, reservation_id: str) -> None: ...

    def release(self, reservation_id: str) -> None: ...


class Payments(Protocol):
    def charge(self, amount: Decimal, card_token: str, idempotency_key: str) -> str:
        """Return a payment reference. Raises on failure."""
        ...


class Notifier(Protocol):
    def send_confirmation(self, email: str, order_id: str, total: Decimal) -> None: ...


class CheckoutFacade:
    def __init__(
        self,
        inventory: Inventory,
        payments: Payments,
        notifier: Notifier,
        new_id: Callable[[], str] = lambda: uuid.uuid4().hex,
    ) -> None:
        self._inventory = inventory
        self._payments = payments
        self._notifier = notifier
        self._new_id = new_id

    def place_order(
        self, lines: Sequence[CartLine], card_token: str, email: str
    ) -> OrderConfirmation:
        if not lines:
            raise CheckoutError("Cart is empty")
        if any(line.quantity <= 0 for line in lines):
            raise CheckoutError("Quantities must be positive")

        total = sum((line.unit_price * line.quantity for line in lines), Decimal("0"))
        order_id = self._new_id()

        reservation_id = self._inventory.reserve(lines)
        try:
            # The order id doubles as the idempotency key, so a retried request can't
            # charge the customer twice.
            reference = self._payments.charge(total, card_token, idempotency_key=order_id)
        except Exception as exc:
            self._inventory.release(reservation_id)
            raise PaymentFailed(str(exc)) from exc

        self._inventory.commit(reservation_id)

        email_sent = True
        try:
            self._notifier.send_confirmation(email, order_id, total)
        except Exception:
            logger.exception("Order %s placed but confirmation email failed", order_id)
            email_sent = False

        return OrderConfirmation(order_id, total, reference, email_sent)
