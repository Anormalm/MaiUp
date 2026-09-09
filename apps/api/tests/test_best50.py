from decimal import Decimal

from app.catalog.versioning import VersionPolicy
from app.rating.best50 import ScoreRecord, build_best50


def score(chart_id: str, version: str, constant: str = "14.0") -> ScoreRecord:
    return ScoreRecord(
        chart_id=chart_id,
        chart_version=version,
        chart_constant=Decimal(constant),
        achievement=Decimal("100.5"),
    )


def test_latest_two_versions_roll_forward_without_hardcoded_names() -> None:
    policy = VersionPolicy(
        ordered_versions=("old", "CiRCLE", "CiRCLE PLUS", "NEXT"),
        current_version="NEXT",
    )
    assert policy.b15_versions == ("CiRCLE PLUS", "NEXT")
    assert policy.bucket_for("CiRCLE") == "b35"
    assert policy.bucket_for("CiRCLE PLUS") == "b15"
    assert policy.bucket_for("NEXT") == "b15"


def test_best50_caps_buckets_and_excludes_future_or_ineligible() -> None:
    versions = ("old", "current-1", "current", "future")
    policy = VersionPolicy(ordered_versions=versions, current_version="current")
    records = [score(f"old-{index}", "old") for index in range(40)]
    records += [score(f"new-{index}", "current") for index in range(20)]
    records += [score("future", "future"), score("unknown", "missing")]
    records.append(
        ScoreRecord(
            chart_id="special",
            chart_version="current",
            chart_constant=Decimal("15.0"),
            achievement=Decimal("101"),
            rating_eligible=False,
        )
    )

    result = build_best50(records, policy)

    assert len(result.b35) == 35
    assert len(result.b15) == 15
    assert all(item.score.chart_id != "special" for item in (*result.b35, *result.b15))


def test_duplicate_chart_attempt_keeps_higher_rating() -> None:
    policy = VersionPolicy(("old", "current-1", "current"), "current")
    records = [
        ScoreRecord("same", "current", Decimal("14"), Decimal("97")),
        ScoreRecord("same", "current", Decimal("14"), Decimal("100.5")),
    ]
    result = build_best50(records, policy)
    assert len(result.b15) == 1
    assert result.b15[0].rating == 315
