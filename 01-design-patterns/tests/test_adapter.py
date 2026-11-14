from decimal import Decimal

import pytest
from design_patterns.structural.adapter import (
    AcmeCardError,
    AcmeNetworkError,
    AcmePayAdapter,
    LegacyBankAdapter,
    Money,
    PaymentDeclined,
    PaymentError,
    PaymentGateway,
    PaymentUnavailable,
)

TEN_POUNDS = Money(Decimal("10.50"), "GBP")


class FakeAcme:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls = []

    def create_payment(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"id": "acme_123", "status": "succeeded"}


class FakeBank:
    def __init__(self, status: str):
        self.status = status
        self.calls = []

    def authorise(self, amount, currency, token, ref):
        self.calls.append((amount, currency, token, ref))
        return self.status, "BANK-9"


def test_acme_adapter_translates_amounts_into_minor_units():
    client = FakeAcme()
    result = AcmePayAdapter(client).charge(TEN_POUNDS, "tok_1", "order-1")
    assert result.reference == "acme_123"
    assert client.calls[0] == {
        "amount_minor": 1050, "currency": "gbp", "source": "tok_1", "idempotency_key": "order-1",
    }


@pytest.mark.parametrize(
    ("vendor_error", "expected"),
    [
        (AcmeCardError("card_declined"), PaymentDeclined),
        (AcmeCardError("something_new"), PaymentError),
        (AcmeNetworkError(), PaymentUnavailable),
    ],
)
def test_acme_errors_become_our_errors(vendor_error, expected):
    with pytest.raises(expected):
        AcmePayAdapter(FakeAcme(vendor_error)).charge(TEN_POUNDS, "tok", "k")


def test_bank_adapter_sends_decimal_strings():
    api = FakeBank("00")
    result = LegacyBankAdapter(api).charge(TEN_POUNDS, "tok", "order-2")
    assert result.reference == "BANK-9"
    assert api.calls[0] == ("10.50", "GBP", "tok", "order-2")


@pytest.mark.parametrize(
    ("status", "expected"),
    [("05", PaymentDeclined), ("91", PaymentUnavailable), ("XX", PaymentError)],
)
def test_bank_status_codes_become_our_errors(status, expected):
    with pytest.raises(expected):
        LegacyBankAdapter(FakeBank(status)).charge(TEN_POUNDS, "tok", "k")


def test_both_adapters_are_interchangeable_to_the_caller():
    def checkout(gateway: PaymentGateway) -> str:
        return gateway.charge(TEN_POUNDS, "tok", "order-3").reference

    assert checkout(AcmePayAdapter(FakeAcme())) == "acme_123"
    assert checkout(LegacyBankAdapter(FakeBank("00"))) == "BANK-9"


@pytest.mark.parametrize("amount", ["0", "-1", "1.005"])
def test_money_rejects_invalid_amounts(amount):
    with pytest.raises(ValueError):
        Money(Decimal(amount), "GBP")
