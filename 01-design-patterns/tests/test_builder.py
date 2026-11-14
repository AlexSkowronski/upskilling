import pytest
from design_patterns.creational.builder import Query, SelectBuilder


def test_builds_a_full_parameterised_query():
    query = (
        SelectBuilder()
        .from_("orders")
        .select("id", "total")
        .where("status = ?", "paid")
        .where("total > ?", 100)
        .order_by("created_at", "desc")
        .limit(20)
        .offset(40)
        .build()
    )
    assert query == Query(
        "SELECT id, total FROM orders WHERE (status = ?) AND (total > ?) "
        "ORDER BY created_at DESC LIMIT ? OFFSET ?",
        ("paid", 100, 20, 40),
    )


def test_builder_is_immutable_so_base_queries_can_be_shared():
    paid = SelectBuilder().from_("orders").where("status = ?", "paid")
    big = paid.where("total > ?", 1000)
    assert paid.build().params == ("paid",)
    assert big.build().params == ("paid", 1000)


def test_where_in_expands_placeholders():
    query = SelectBuilder().from_("orders").where_in("id", [1, 2, 3]).build()
    assert query.sql == "SELECT * FROM orders WHERE (id IN (?, ?, ?))"
    assert query.params == (1, 2, 3)


@pytest.mark.parametrize(
    "make",
    [
        lambda: SelectBuilder().build(),  # no table
        lambda: SelectBuilder().from_("orders").offset(10).build(),  # offset without limit
        lambda: SelectBuilder().from_("orders").where("a = ? AND b = ?", 1),  # wrong arg count
        lambda: SelectBuilder().from_("orders").where_in("id", []),
        lambda: SelectBuilder().from_("orders; DROP TABLE users"),  # injection via identifier
        lambda: SelectBuilder().from_("orders").order_by("id", "sideways"),
        lambda: SelectBuilder().from_("orders").limit(0),
    ],
)
def test_rejects_invalid_queries(make):
    with pytest.raises(ValueError):
        make()
