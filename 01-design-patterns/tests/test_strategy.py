from decimal import Decimal as D

import pytest
from design_patterns.behavioural.strategy import (
    FreeOver,
    NoShippingAvailable,
    Parcel,
    Quote,
    ShippingCalculator,
    WeightBands,
    flat_rate,
)

UK = {"GB"}
calculator = ShippingCalculator({
    "standard": FreeOver(D("50"), WeightBands([(D("2"), D("3.99")), (D("10"), D("7.99"))], UK)),
    "express": flat_rate(D("9.99"), UK),
    "international": flat_rate(D("19.99"), {"FR", "DE", "IE"}),
})


def parcel(kg: str, country: str = "GB", total: str = "20") -> Parcel:
    return Parcel(D(kg), country, D(total))


def test_lists_eligible_methods_cheapest_first():
    assert calculator.quotes(parcel("1.5")) == [
        Quote("standard", D("3.99")), Quote("express", D("9.99")),
    ]


def test_weight_bands_pick_the_first_band_that_fits():
    assert calculator.cheapest(parcel("5")).price == D("7.99")


def test_too_heavy_for_standard_falls_back_to_other_methods():
    assert calculator.cheapest(parcel("25")) == Quote("express", D("9.99"))


def test_free_over_wraps_another_strategy():
    assert calculator.cheapest(parcel("1", total="50")) == Quote("standard", D("0.00"))
    # ...but it can't make an ineligible parcel eligible.
    assert [q.method for q in calculator.quotes(parcel("25", total="500"))] == ["express"]


def test_international_only_offers_matching_methods():
    assert calculator.quotes(parcel("1", "FR")) == [Quote("international", D("19.99"))]


def test_no_method_available_raises():
    with pytest.raises(NoShippingAvailable):
        calculator.cheapest(parcel("1", "JP"))


def test_any_function_is_a_valid_strategy():
    calc = ShippingCalculator({"collect": lambda p: D("0") if p.country == "GB" else None})
    assert calc.cheapest(parcel("100")) == Quote("collect", D("0"))


def test_bands_must_be_sorted():
    with pytest.raises(ValueError):
        WeightBands([(D("10"), D("5")), (D("2"), D("3"))], UK)
