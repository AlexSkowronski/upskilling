from decimal import Decimal

import pytest
from design_patterns.structural.facade import (
    CartLine,
    CheckoutError,
    CheckoutFacade,
    OutOfStock,
    PaymentFailed,
)

LINES = [CartLine("SKU-1", 2, Decimal("10.00")), CartLine("SKU-2", 1, Decimal("5.50"))]


class FakeInventory:
    def __init__(self, stock: dict[str, int]):
        self.stock = stock
        self.reserved: dict[str, list[CartLine]] = {}
        self.events: list[str] = []

    def reserve(self, lines):
        for line in lines:
            if self.stock.get(line.sku, 0) < line.quantity:
                raise OutOfStock(line.sku)
        for line in lines:
            self.stock[line.sku] -= line.quantity
        self.reserved["R1"] = list(lines)
        self.events.append("reserve")
        return "R1"

    def commit(self, reservation_id):
        self.reserved.pop(reservation_id)
        self.events.append("commit")

    def release(self, reservation_id):
        for line in self.reserved.pop(reservation_id):
            self.stock[line.sku] += line.quantity
        self.events.append("release")


class FakePayments:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.charges = []

    def charge(self, amount, card_token, idempotency_key):
        if self.fail:
            raise RuntimeError("card declined")
        self.charges.append((amount, idempotency_key))
        return "PAY-1"


class FakeNotifier:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.sent = []

    def send_confirmation(self, email, order_id, total):
        if self.fail:
            raise ConnectionError("SMTP down")
        self.sent.append((email, order_id, total))


def make(inventory=None, payments=None, notifier=None):
    inventory = inventory or FakeInventory({"SKU-1": 5, "SKU-2": 5})
    payments = payments or FakePayments()
    notifier = notifier or FakeNotifier()
    facade = CheckoutFacade(inventory, payments, notifier, new_id=lambda: "ORD-1")
    return facade, inventory, payments, notifier


def test_happy_path_coordinates_every_subsystem():
    facade, inventory, payments, notifier = make()
    confirmation = facade.place_order(LINES, "tok", "ada@example.com")

    assert confirmation.total == Decimal("25.50")
    assert confirmation.email_sent
    assert inventory.events == ["reserve", "commit"]
    assert payments.charges == [(Decimal("25.50"), "ORD-1")]  # order id is the idempotency key
    assert notifier.sent == [("ada@example.com", "ORD-1", Decimal("25.50"))]


def test_failed_payment_releases_the_stock():
    facade, inventory, _, notifier = make(payments=FakePayments(fail=True))
    with pytest.raises(PaymentFailed):
        facade.place_order(LINES, "tok", "ada@example.com")
    assert inventory.events == ["reserve", "release"]
    assert inventory.stock == {"SKU-1": 5, "SKU-2": 5}
    assert notifier.sent == []


def test_out_of_stock_never_charges():
    facade, _, payments, _ = make(inventory=FakeInventory({"SKU-1": 1}))
    with pytest.raises(OutOfStock):
        facade.place_order(LINES, "tok", "ada@example.com")
    assert payments.charges == []


def test_email_failure_does_not_fail_a_paid_order():
    facade, inventory, _, _ = make(notifier=FakeNotifier(fail=True))
    confirmation = facade.place_order(LINES, "tok", "ada@example.com")
    assert not confirmation.email_sent
    assert inventory.events == ["reserve", "commit"]


@pytest.mark.parametrize("lines", [[], [CartLine("SKU-1", 0, Decimal("1"))]])
def test_rejects_invalid_carts(lines):
    facade, *_ = make()
    with pytest.raises(CheckoutError):
        facade.place_order(lines, "tok", "ada@example.com")
