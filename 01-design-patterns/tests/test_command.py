import pytest
from design_patterns.behavioural.command import (
    AddItem,
    Cart,
    ChangeQuantity,
    CommandHistory,
    Macro,
    NothingToUndo,
    RemoveItem,
)


@pytest.fixture
def cart() -> Cart:
    return Cart()


def test_undo_and_redo_walk_back_and_forth(cart):
    history = CommandHistory(cart)
    history.run(AddItem("A", 2))
    history.run(ChangeQuantity("A", 5))
    history.run(AddItem("B", 1))

    history.undo()
    assert cart.snapshot() == {"A": 5}
    history.undo()
    assert cart.snapshot() == {"A": 2}
    history.redo()
    assert cart.snapshot() == {"A": 5}


def test_remove_remembers_the_quantity_it_removed(cart):
    history = CommandHistory(cart)
    history.run(AddItem("A", 3))
    history.run(RemoveItem("A"))
    assert cart.snapshot() == {}
    history.undo()
    assert cart.snapshot() == {"A": 3}


def test_a_new_command_clears_the_redo_stack(cart):
    history = CommandHistory(cart)
    history.run(AddItem("A", 1))
    history.undo()
    assert history.can_redo
    history.run(AddItem("B", 1))
    assert not history.can_redo
    with pytest.raises(NothingToUndo):
        history.redo()


def test_a_failed_command_leaves_history_untouched(cart):
    history = CommandHistory(cart)
    with pytest.raises(KeyError):
        history.run(RemoveItem("missing"))
    assert not history.can_undo


def test_macro_undoes_as_a_single_step(cart):
    history = CommandHistory(cart)
    history.run(AddItem("A", 1))
    history.run(Macro([AddItem("B", 2), ChangeQuantity("A", 4), RemoveItem("B")]))
    assert cart.snapshot() == {"A": 4}
    history.undo()
    assert cart.snapshot() == {"A": 1}


def test_macro_rolls_back_completed_steps_if_one_fails(cart):
    cart.set_quantity("A", 1)
    macro = Macro([AddItem("B", 2), ChangeQuantity("A", 9), RemoveItem("missing")])
    with pytest.raises(KeyError):
        CommandHistory(cart).run(macro)
    assert cart.snapshot() == {"A": 1}


def test_nothing_to_undo(cart):
    with pytest.raises(NothingToUndo):
        CommandHistory(cart).undo()
