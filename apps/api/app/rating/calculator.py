from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal

MIN_ACHIEVEMENT = Decimal("0")
MAX_ACHIEVEMENT = Decimal("101")
RATING_ACHIEVEMENT_CAP = Decimal("100.5")

# Each value becomes active at its lower-bound Achievement percentage.
# Decimal strings are intentional: float rounding at 99.5/100.0/100.5 changes Rating.
COEFFICIENT_THRESHOLDS: tuple[tuple[Decimal, Decimal], ...] = (
    (Decimal("0"), Decimal("0")),
    (Decimal("10"), Decimal("1.6")),
    (Decimal("20"), Decimal("3.2")),
    (Decimal("30"), Decimal("4.8")),
    (Decimal("40"), Decimal("6.4")),
    (Decimal("50"), Decimal("8.0")),
    (Decimal("60"), Decimal("9.6")),
    (Decimal("70"), Decimal("11.2")),
    (Decimal("75"), Decimal("12.0")),
    (Decimal("79.9999"), Decimal("12.8")),
    (Decimal("80"), Decimal("13.6")),
    (Decimal("90"), Decimal("15.2")),
    (Decimal("94"), Decimal("16.8")),
    (Decimal("96.9999"), Decimal("17.6")),
    (Decimal("97"), Decimal("20.0")),
    (Decimal("98"), Decimal("20.3")),
    (Decimal("98.9999"), Decimal("20.6")),
    (Decimal("99"), Decimal("20.8")),
    (Decimal("99.5"), Decimal("21.1")),
    (Decimal("99.9999"), Decimal("21.4")),
    (Decimal("100"), Decimal("21.6")),
    (Decimal("100.4999"), Decimal("22.2")),
    (Decimal("100.5"), Decimal("22.4")),
)


def _decimal(value: Decimal | str | int | float) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def coefficient_for(achievement: Decimal | str | int | float) -> Decimal:
    achievement_value = _decimal(achievement)
    if not MIN_ACHIEVEMENT <= achievement_value <= MAX_ACHIEVEMENT:
        raise ValueError("Achievement must be between 0 and 101")
    coefficient = Decimal("0")
    for threshold, candidate in COEFFICIENT_THRESHOLDS:
        if achievement_value < threshold:
            break
        coefficient = candidate
    return coefficient


def calculate_chart_rating(
    chart_constant: Decimal | str | int | float,
    achievement: Decimal | str | int | float,
    *,
    full_combo: str | None = None,
) -> int:
    constant_value = _decimal(chart_constant)
    achievement_value = _decimal(achievement)
    if constant_value <= 0:
        raise ValueError("Chart constant must be positive")

    coefficient = coefficient_for(achievement_value)
    capped_achievement = min(achievement_value, RATING_ACHIEVEMENT_CAP)
    raw = constant_value * capped_achievement / Decimal("100") * coefficient
    rating = int(raw.quantize(Decimal("1"), rounding=ROUND_FLOOR))

    combo = (full_combo or "").strip().lower().replace(" ", "")
    if combo in {"ap", "allperfect", "ap+", "applus", "allperfect+"}:
        rating += 1
    return rating
