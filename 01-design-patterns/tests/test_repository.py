from decimal import Decimal as D

import pytest
from design_patterns.data.repository import (
    Account,
    AccountNotFound,
    InMemoryAccountRepository,
    InMemoryUnitOfWork,
    InsufficientFunds,
    transfer,
)


@pytest.fixture
def uow() -> InMemoryUnitOfWork:
    repo = InMemoryAccountRepository([
        Account("alice", D("100")),
        Account("bob", D("20")),
        Account("frozen", D("0"), frozen=True),
    ])
    return InMemoryUnitOfWork(repo)


def balances(uow: InMemoryUnitOfWork) -> dict[str, D]:
    return {i: uow.accounts.get(i).balance for i in ("alice", "bob", "frozen")}


def test_successful_transfer_commits_both_sides(uow):
    transfer(uow, "alice", "bob", D("30"))
    assert uow.committed
    assert balances(uow) == {"alice": D("70"), "bob": D("50"), "frozen": D("0")}


def test_failed_withdrawal_changes_nothing(uow):
    with pytest.raises(InsufficientFunds):
        transfer(uow, "bob", "alice", D("500"))
    assert balances(uow) == {"alice": D("100"), "bob": D("20"), "frozen": D("0")}


def test_failed_deposit_rolls_back_the_withdrawal(uow):
    # The withdrawal from alice succeeds, then the deposit into a frozen account fails.
    with pytest.raises(PermissionError):
        transfer(uow, "alice", "frozen", D("10"))
    assert balances(uow)["alice"] == D("100")


def test_forgetting_to_commit_rolls_back(uow):
    with uow:
        uow.accounts.get("alice").withdraw(D("50"))
    assert uow.accounts.get("alice").balance == D("100")


def test_unknown_account(uow):
    with pytest.raises(AccountNotFound):
        transfer(uow, "alice", "nobody", D("1"))


def test_repository_rejects_duplicates():
    repo = InMemoryAccountRepository([Account("a", D("1"))])
    with pytest.raises(ValueError):
        repo.add(Account("a", D("2")))
