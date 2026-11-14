from decimal import Decimal

from design_patterns.structural.composite import (
    AllOf,
    Customer,
    in_countries,
    is_vip,
    loyalty_promotion,
    min_spend,
)


def customer(**overrides) -> Customer:
    fields = {"country": "GB", "total_spend": Decimal("0"), "is_vip": False,
              "has_overdue_invoice": False}
    return Customer(**(fields | overrides))


def test_vip_or_big_spender_in_the_right_country_qualifies():
    assert loyalty_promotion.is_satisfied_by(customer(is_vip=True))
    assert loyalty_promotion.is_satisfied_by(customer(total_spend=Decimal("500")))
    assert loyalty_promotion.is_satisfied_by(customer(country="IE", is_vip=True))


def test_explains_every_reason_for_failing():
    reasons = loyalty_promotion.why_not(
        customer(country="FR", total_spend=Decimal("10"), has_overdue_invoice=True)
    )
    assert reasons == [
        "needs one of: VIP / spent at least 500",
        "based in GB/IE",
        "must not be: has an overdue invoice",
    ]


def test_passing_customer_has_no_reasons():
    assert loyalty_promotion.why_not(customer(is_vip=True)) == []


def test_nested_ands_are_flattened_for_readability():
    spec = (is_vip & min_spend(10)) & in_countries("GB")
    assert isinstance(spec, AllOf)
    assert len(spec.specs) == 3
    assert repr(spec) == "(VIP AND spent at least 10 AND based in GB)"


def test_full_rule_reads_like_the_requirement():
    assert repr(loyalty_promotion) == (
        "((VIP OR spent at least 500) AND based in GB/IE AND NOT has an overdue invoice)"
    )
