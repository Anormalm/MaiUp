from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.catalog.versioning import VersionPolicy
from app.rating.calculator import calculate_chart_rating


@dataclass(frozen=True)
class ScoreRecord:
    chart_id: str
    chart_version: str
    chart_constant: Decimal
    achievement: Decimal
    full_combo: str | None = None
    rating_eligible: bool = True

    @property
    def rating(self) -> int:
        return calculate_chart_rating(
            self.chart_constant,
            self.achievement,
            full_combo=self.full_combo,
        )


@dataclass(frozen=True)
class RankedScore:
    score: ScoreRecord
    rating: int


@dataclass(frozen=True)
class Best50Result:
    b35: tuple[RankedScore, ...]
    b15: tuple[RankedScore, ...]

    @property
    def total(self) -> int:
        return sum(item.rating for item in (*self.b35, *self.b15))


def build_best50(scores: list[ScoreRecord], policy: VersionPolicy) -> Best50Result:
    """Build B35/B15 while keeping only the best attempt for each stable chart id."""
    deduplicated: dict[str, ScoreRecord] = {}
    for score in scores:
        current = deduplicated.get(score.chart_id)
        if current is None or score.rating > current.rating:
            deduplicated[score.chart_id] = score

    buckets: dict[str, list[RankedScore]] = {"b35": [], "b15": []}
    for score in deduplicated.values():
        bucket = policy.bucket_for(
            score.chart_version,
            rating_eligible=score.rating_eligible,
        )
        if bucket is not None:
            buckets[bucket].append(RankedScore(score=score, rating=score.rating))

    for values in buckets.values():
        values.sort(key=lambda item: (-item.rating, item.score.chart_id))

    return Best50Result(
        b35=tuple(buckets["b35"][:35]),
        b15=tuple(buckets["b15"][:15]),
    )
