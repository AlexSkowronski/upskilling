"""Adapter: make a third-party API fit *your* interface.

The app depends only on ``PaymentGateway`` and its own errors. Two made-up vendor SDKs
have very different shapes:

* ``AcmePayClient`` takes integer minor units (pence), returns a dict, and raises its own
  exception types.
* ``LegacyBankApi`` takes a decimal string, returns a ``(status_code, reference)`` tuple,
  and signals failure through status codes.

Each adapter translates amounts, results **and errors**. Error translation is the part
people forget; without it, vendor exceptions leak into business code and couple you to them.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

# --- Our side: the interface the application owns -------------------------------------


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str  # ISO 4217, e.g. "GBP"

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise ValueError("Charges must be positive")
        if self.amount != self.amount.quantize(Decimal("0.01")):
            raise ValueError("Money is limited to 2 decimal places")


@dataclass(frozen=True)
class ChargeResult:
    reference: str
    amount: Money


class PaymentError(Exception):
    """Base class for every payment failure the app needs to understand."""


class PaymentDeclined(PaymentError):
    """The customer's card was refused. Don't retry; ask for another card."""


class PaymentUnavailable(PaymentError):
    """The provider is down or unreachable. Safe to retry later."""


class PaymentGateway(Protocol):
    def charge(self, amount: Money, card_token: str, idempotency_key: str) -> ChargeResult: ...


# --- Their side: two vendor SDKs we don't control --------------------------------------


class AcmeCardError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class AcmeNetworkError(Exception):
    pass


class AcmePayClient:
    """Stand-in for a vendor SDK. In real life this makes HTTP calls."""

    def create_payment(
        self, *, amount_minor: int, currency: str, source: str, idempotency_key: str
    ) -> dict[str, Any]:
        raise NotImplementedError  # replaced by a fake in tests


class LegacyBankApi:
    """Stand-in for an older bank interface that reports results as status codes."""

    def authorise(self, amount: str, currency: str, token: str, ref: str) -> tuple[str, str]:
        raise NotImplementedError


# --- The adapters ------------------------------------------------------------------------


class AcmePayAdapter:
    _DECLINE_CODES = {"card_declined", "insufficient_funds", "expired_card"}

    def __init__(self, client: AcmePayClient) -> None:
        self._client = client

    def charge(self, amount: Money, card_token: str, idempotency_key: str) -> ChargeResult:
        try:
            response = self._client.create_payment(
                amount_minor=int(amount.amount * 100),
                currency=amount.currency.lower(),
                source=card_token,
                idempotency_key=idempotency_key,
            )
        except AcmeCardError as exc:
            if exc.code in self._DECLINE_CODES:
                raise PaymentDeclined(exc.code) from exc
            raise PaymentError(f"Unexpected AcmePay error: {exc.code}") from exc
        except AcmeNetworkError as exc:
            raise PaymentUnavailable("AcmePay unreachable") from exc
        return ChargeResult(reference=response["id"], amount=amount)


class LegacyBankAdapter:
    _APPROVED = "00"
    _DECLINED = {"05", "51", "54"}  # do not honour, insufficient funds, expired card
    _UNAVAILABLE = {"91", "96"}  # issuer unavailable, system malfunction

    def __init__(self, api: LegacyBankApi) -> None:
        self._api = api

    def charge(self, amount: Money, card_token: str, idempotency_key: str) -> ChargeResult:
        status, reference = self._api.authorise(
            amount=f"{amount.amount:.2f}",
            currency=amount.currency,
            token=card_token,
            ref=idempotency_key,
        )
        if status == self._APPROVED:
            return ChargeResult(reference=reference, amount=amount)
        if status in self._DECLINED:
            raise PaymentDeclined(f"Bank status {status}")
        if status in self._UNAVAILABLE:
            raise PaymentUnavailable(f"Bank status {status}")
        raise PaymentError(f"Unknown bank status {status}")
