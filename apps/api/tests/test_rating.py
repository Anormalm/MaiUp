from decimal import Decimal

import pytest

from app.rating.calculator import calculate_chart_rating, coefficient_for


@pytest.mark.parametrize(
    ("achievement", "expected"),
    [
        ("79.9998", "12.0"),
        ("79.9999", "12.8"),
        ("80", "13.6"),
        ("96.9998", "16.8"),
        ("96.9999", "17.6"),
        ("97", "20.0"),
        ("98.9999", "20.6"),
        ("99", "20.8"),
        ("99.9999", "21.4"),
        ("100", "21.6"),
        ("100.4999", "22.2"),
        ("100.5", "22.4"),
        ("101", "22.4"),
    ],
)
def test_coefficient_boundaries(achievement: str, expected: str) -> None:
    assert coefficient_for(achievement) == Decimal(expected)


@pytest.mark.parametrize(
    ("constant", "achievement", "expected"),
    [
        ("14.0", "97", 271),
        ("14.0", "99.5", 293),
        ("14.0", "100.5", 315),
        ("15.0", "100.5", 337),
        ("13.0", "100.5", 292),
        ("14.0", "101", 315),
    ],
)
def test_known_rating_examples(constant: str, achievement: str, expected: int) -> None:
    assert calculate_chart_rating(constant, achievement) == expected


def test_soteria_international_constant_correction_is_two_rating() -> None:
    achievement = "100.5283"

    assert calculate_chart_rating("14.0", achievement) == 315
    assert calculate_chart_rating("14.1", achievement) == 317


def test_ap_and_ap_plus_add_one() -> None:
    base = calculate_chart_rating("14.0", "100.5")
    assert calculate_chart_rating("14.0", "100.5", full_combo="AP") == base + 1
    assert calculate_chart_rating("14.0", "100.5", full_combo="AP+") == base + 1


@pytest.mark.parametrize("achievement", ["-0.0001", "101.0001"])
def test_achievement_outside_range_is_rejected(achievement: str) -> None:
    with pytest.raises(ValueError, match="between 0 and 101"):
        coefficient_for(achievement)
