"""Repository + Unit of Work: keep storage out of business logic, and make changes atomic.

* **Repository**: looks like an in-memory collection of domain objects (``get``, ``add``).
  Business code never sees SQL, sessions or rows. The real version would wrap a database;
  ``InMemoryAccountRepository`` is the fake used here and in tests.
* **Unit of Work**: one "business transaction". Changes made inside ``with uow:`` are only
  kept if ``uow.commit()`` is called. Leaving the block any other way (an exception, or
  forgetting to commit) **rolls everything back**.

``transfer`` shows why this matters: a withdrawal followed by a failing deposit must not
leave money vanished. Everything commits together or not at all.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from decimal import Decimal
from types import TracebackType
from typing import Protocol, Self


class InsufficientFunds(Exception):
    pass


class AccountNotFound(Exception):
    pass


@dataclass
class Account:
    """A domain entity: it has an identity (``account_id``) and enforces its own rules."""

    account_id: str
    balance: Decimal
    frozen: bool = False

    def withdraw(self, amount: Decimal) -> None:
        self._check(amount)
        if amount > self.balance:
            raise InsufficientFunds(f"{self.account_id} has {self.balance}, needs {amount}")
        self.balance -= amount

    def deposit(self, amount: Decimal) -> None:
        self._check(amount)
        self.balance += amount

    def _check(self, amount: Decimal) -> None:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if self.frozen:
            raise PermissionError(f"Account {self.account_id} is frozen")


class AccountRepository(Protocol):
    def get(self, account_id: str) -> Account: ...

    def add(self, account: Account) -> None: ...


class InMemoryAccountRepository:
    def __init__(self, accounts: list[Account] | None = None) -> None:
        self._accounts: dict[str, Account] = {a.account_id: a for a in accounts or []}

    def get(self, account_id: str) -> Account:
        try:
            return self._accounts[account_id]
        except KeyError:
            raise AccountNotFound(account_id) from None

    def add(self, account: Account) -> None:
        if account.account_id in self._accounts:
            raise ValueError(f"Account {account.account_id} already exists")
        self._accounts[account.account_id] = account

    # Used by the Unit of Work. A database would use a transaction instead.
    def _snapshot(self) -> dict[str, Account]:
        return copy.deepcopy(self._accounts)

    def _restore(self, snapshot: dict[str, Account]) -> None:
        self._accounts = snapshot


class InMemoryUnitOfWork:
    def __init__(self, accounts: InMemoryAccountRepository) -> None:
        self.accounts = accounts
        self.committed = False
        self._snapshot: dict[str, Account] | None = None

    def __enter__(self) -> Self:
        self.committed = False
        self._snapshot = self.accounts._snapshot()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if not self.committed:
            self.rollback()
        self._snapshot = None

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        if self._snapshot is not None:
            self.accounts._restore(self._snapshot)


# --- A service using them: no storage details in sight ------------------------------------


def transfer(uow: InMemoryUnitOfWork, from_id: str, to_id: str, amount: Decimal) -> None:
    if from_id == to_id:
        raise ValueError("Cannot transfer to the same account")
    with uow:
        source = uow.accounts.get(from_id)
        target = uow.accounts.get(to_id)
        source.withdraw(amount)
        target.deposit(amount)  # if this raises, the withdrawal above is rolled back
        uow.commit()
