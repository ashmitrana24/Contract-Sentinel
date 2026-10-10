"""Unit tests for number-words and figure parsing."""

from decimal import Decimal

import pytest

from clauseguard.consistency.numbers import parse_figure, words_to_decimal

pytestmark = pytest.mark.unit


def test_words_units_and_teens():
    assert words_to_decimal("zero").value == Decimal(0)
    assert words_to_decimal("one").value == Decimal(1)
    assert words_to_decimal("nine").value == Decimal(9)
    assert words_to_decimal("eleven").value == Decimal(11)
    assert words_to_decimal("nineteen").value == Decimal(19)


def test_words_tens_and_hyphenated():
    assert words_to_decimal("twenty").value == Decimal(20)
    assert words_to_decimal("twenty-five").value == Decimal(25)
    assert words_to_decimal("forty-two").value == Decimal(42)
    assert words_to_decimal("ninety-nine").value == Decimal(99)


def test_words_hundreds_and_thousands():
    assert words_to_decimal("one hundred").value == Decimal(100)
    assert words_to_decimal("one hundred and fifty").value == Decimal(150)
    assert words_to_decimal("five thousand").value == Decimal(5_000)
    assert words_to_decimal("two thousand five hundred").value == Decimal(2_500)


def test_words_indian_scales():
    assert words_to_decimal("ten lakh").value == Decimal(1_000_000)
    assert words_to_decimal("Rupees Ten Lakh Only").value == Decimal(1_000_000)
    assert words_to_decimal("Rupees One Crore Twenty Five Lakh").value == Decimal(12_500_000)
    assert words_to_decimal("Rupees One Crore Twenty-Five Lakh Only").value == Decimal(12_500_000)
    assert words_to_decimal("five lac").value == Decimal(500_000)


def test_words_western_scales():
    assert words_to_decimal("one million").value == Decimal(1_000_000)
    assert words_to_decimal("five million two hundred thousand").value == Decimal(5_200_000)
    assert words_to_decimal("two billion").value == Decimal(2_000_000_000)


def test_words_with_currency_and_percent():
    w_curr = words_to_decimal("Rupees Fifty Thousand Only")
    assert w_curr.value == Decimal(50_000)
    assert w_curr.currency == "INR"
    assert w_curr.is_currency is True

    w_pct = words_to_decimal("five percent")
    assert w_pct.value == Decimal(5)
    assert w_pct.is_percentage is True


def test_words_garbage_input_returns_none():
    assert words_to_decimal("") is None
    assert words_to_decimal("hello world") is None
    assert words_to_decimal("some random clause text") is None
    assert words_to_decimal("12345") is None
    assert words_to_decimal(None) is None


def test_figures_indian_and_western_groupings():
    f_ind = parse_figure("Rs. 10,00,000")
    assert f_ind.value == Decimal(1_000_000)
    assert f_ind.currency == "INR"

    f_ind2 = parse_figure("1,99,00,000")
    assert f_ind2.value == Decimal(19_900_000)

    f_west = parse_figure("$1,000,000")
    assert f_west.value == Decimal(1_000_000)
    assert f_west.currency == "USD"


def test_figures_unit_forms():
    f_lakh = parse_figure("Rs. 10.5 lakh")
    assert f_lakh.value == Decimal(1_050_000)
    assert f_lakh.currency == "INR"

    f_mil = parse_figure("$1.5 million")
    assert f_mil.value == Decimal(1_500_000)
    assert f_mil.currency == "USD"

    f_cr = parse_figure("2.5 crore")
    assert f_cr.value == Decimal(25_000_000)


def test_figures_percentages_and_quantities():
    f_pct = parse_figure("5%")
    assert f_pct.value == Decimal(5)
    assert f_pct.is_percentage is True

    f_pct2 = parse_figure("12.5 percent")
    assert f_pct2.value == Decimal("12.5")
    assert f_pct2.is_percentage is True

    f_bare = parse_figure("30")
    assert f_bare.value == Decimal(30)
    assert f_bare.currency is None
    assert f_bare.is_percentage is False


def test_figures_garbage_input_returns_none():
    assert parse_figure("") is None
    assert parse_figure("ABC") is None
    assert parse_figure("12.34.56") is None
    assert parse_figure("three days") is None
    assert parse_figure(None) is None
