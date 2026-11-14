"""Command: turn an action into an object, so it can be stored, undone, replayed or queued.

A shopping-cart editor with full undo/redo. Each edit is a command object with
``execute`` and ``undo``. Commands **remember what they need to undo themselves**: removing
an item records the quantity that was there, and changing a quantity records the old value.

* ``CommandHistory`` keeps two stacks. Running a new command clears the redo stack, as
  every editor does.
* ``Macro`` is a command made of commands (a Composite). It undoes in reverse order, and if
  one step fails part-way it rolls back the steps that already ran, so the cart is never
  left half-edited.

The same idea powers job queues and message handlers: ``AddItem("SKU-1", 2)`` is just
data until something executes it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class Cart:
    def __init__(self) -> None:
        self._lines: dict[str, int] = {}

    def quantity(self, sku: str) -> int:
        return self._lines.get(sku, 0)

    def set_quantity(self, sku: str, quantity: int) -> None:
        if quantity < 0:
            raise ValueError("Quantity cannot be negative")
        if quantity == 0:
            self._lines.pop(sku, None)
        else:
            self._lines[sku] = quantity

    def snapshot(self) -> dict[str, int]:
        return dict(self._lines)


class Command(Protocol):
    def execute(self, cart: Cart) -> None: ...

    def undo(self, cart: Cart) -> None: ...


@dataclass
class AddItem:
    sku: str
    quantity: int

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("Add a positive quantity")

    def execute(self, cart: Cart) -> None:
        cart.set_quantity(self.sku, cart.quantity(self.sku) + self.quantity)

    def undo(self, cart: Cart) -> None:
        cart.set_quantity(self.sku, cart.quantity(self.sku) - self.quantity)


@dataclass
class RemoveItem:
    sku: str
    _removed: int = field(default=0, init=False)

    def execute(self, cart: Cart) -> None:
        self._removed = cart.quantity(self.sku)
        if self._removed == 0:
            raise KeyError(f"{self.sku} is not in the cart")
        cart.set_quantity(self.sku, 0)

    def undo(self, cart: Cart) -> None:
        cart.set_quantity(self.sku, self._removed)


@dataclass
class ChangeQuantity:
    sku: str
    new_quantity: int
    _previous: int = field(default=0, init=False)

    def execute(self, cart: Cart) -> None:
        self._previous = cart.quantity(self.sku)
        cart.set_quantity(self.sku, self.new_quantity)

    def undo(self, cart: Cart) -> None:
        cart.set_quantity(self.sku, self._previous)


@dataclass
class Macro:
    """Several commands that succeed or fail together, undone as one step."""

    commands: list[Command]

    def execute(self, cart: Cart) -> None:
        done: list[Command] = []
        try:
            for command in self.commands:
                command.execute(cart)
                done.append(command)
        except Exception:
            for command in reversed(done):
                command.undo(cart)
            raise

    def undo(self, cart: Cart) -> None:
        for command in reversed(self.commands):
            command.undo(cart)


class NothingToUndo(Exception):
    pass


class CommandHistory:
    def __init__(self, cart: Cart) -> None:
        self._cart = cart
        self._undo: list[Command] = []
        self._redo: list[Command] = []

    def run(self, command: Command) -> None:
        command.execute(self._cart)  # if this raises, history is unchanged
        self._undo.append(command)
        self._redo.clear()

    def undo(self) -> None:
        if not self._undo:
            raise NothingToUndo("Nothing to undo")
        command = self._undo.pop()
        command.undo(self._cart)
        self._redo.append(command)

    def redo(self) -> None:
        if not self._redo:
            raise NothingToUndo("Nothing to redo")
        command = self._redo.pop()
        command.execute(self._cart)
        self._undo.append(command)

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)
