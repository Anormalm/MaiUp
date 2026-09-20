from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.recommendations.service import (
    ObservedScore,
    PerformanceSample,
    TagFact,
    _activity_window,
    _community_difficulty,
    _first_beating_target,
    _first_improving_target,
    _outside_candidate_sort_key,
    _proven_ceiling,
    _select_candidate_mix,
    _select_diverse_candidates,
    _similar_evidence,
    _strength_profile,
    _target_evidence,
    _target_ladder,
    _weakness_profile,
    _weakness_risk,
)


def test_first_beating_target_uses_the_lower_sufficient_achievement() -> None:
    assert _first_beating_target(Decimal("14.0"), 300) == (Decimal("100.0000"), 302)
    assert _first_beating_target(Decimal("13.4"), 300) == (Decimal("100.5000"), 301)
    assert _first_beating_target(Decimal("13.0"), 300) is None


def test_first_improving_target_never_recommends_a_score_already_achieved() -> None:
    assert _first_improving_target(
        Decimal("13.8"), 290, Decimal("100.1234")
    ) == (Decimal("100.5000"), 310)
    assert _first_improving_target(Decimal("13.8"), 290, Decimal("100.5000")) is None


def test_target_ladder_uses_reachable_rank_steps_before_sss_plus() -> None:
    ladder = _target_ladder(
        Decimal("14.0"),
        280,
        Decimal("98.1000"),
        275,
    )

    assert ladder[0] == {
        "achievement": Decimal("99.0000"),
        "rating": 288,
        "gain": 8,
    }
    assert [item["achievement"] for item in ladder][-2:] == [
        Decimal("100.0000"),
        Decimal("100.5000"),
    ]


def test_similar_evidence_is_not_reported_as_success_probability() -> None:
    observations = [
        ObservedScore("b35", Decimal("13.8"), Decimal("100.6")),
        ObservedScore("b35", Decimal("13.7"), Decimal("100.5")),
        ObservedScore("b35", Decimal("13.6"), Decimal("100.4")),
        ObservedScore("b35", Decimal("13.5"), Decimal("100.7")),
        ObservedScore("b35", Decimal("13.5"), Decimal("100.6")),
    ]
    evidence = _similar_evidence(
        observations,
        "b35",
        Decimal("13.7"),
        Decimal("100.5"),
    )
    assert evidence == {
        "sampleCount": 5,
        "hitCount": 4,
        "hitRate": Decimal("0.800"),
        "strength": "strong",
        "isSuccessProbability": False,
    }


def test_strength_profile_uses_style_tags_and_shrinks_small_samples() -> None:
    style_tag = TagFact(1, 3, "Slide-heavy", "滑键偏重")
    opinion_tag = TagFact(2, 2, "Underrated", "定数虚低")
    tags_by_chart = {
        "a": [style_tag, opinion_tag],
        "b": [style_tag, opinion_tag],
        "c": [style_tag, opinion_tag],
    }

    strengths = _strength_profile(
        {"a": Decimal("0.10"), "b": Decimal("0.08"), "c": Decimal("0.06")},
        tags_by_chart,
    )

    assert len(strengths) == 1
    assert strengths[0]["nameEn"] == "Slide-heavy"
    assert strengths[0]["sampleCount"] == 3
    assert strengths[0]["meanResidual"] == Decimal("0.0800")
    assert strengths[0]["score"] == Decimal("0.0300")
    assert strengths[0]["confidence"] == "exploratory"


def test_outside_candidates_prioritize_empirical_attainability_before_gain() -> None:
    low_gain_high_fit = {
        "title": "14.0 bird",
        "constant": Decimal("14.0"),
        "targetAchievement": Decimal("100.0000"),
        "conditionalGain": 2,
        "personalFitScore": Decimal("0.10"),
        "recommendationBasis": "personalized",
        "communityDifficulty": "neutral",
        "targetEvidence": {"hitRate": Decimal("0.8"), "comfortTier": 0},
    }
    high_gain_lower_fit = {
        "title": "13.6 bird plus",
        "constant": Decimal("13.6"),
        "targetAchievement": Decimal("100.5000"),
        "conditionalGain": 6,
        "personalFitScore": Decimal("0.02"),
        "recommendationBasis": "personalized",
        "communityDifficulty": "neutral",
        "targetEvidence": {"hitRate": Decimal("0.4"), "comfortTier": 0},
    }

    ordered = sorted(
        [low_gain_high_fit, high_gain_lower_fit],
        key=_outside_candidate_sort_key,
    )

    assert ordered[0]["title"] == "14.0 bird"


def test_outside_selection_caps_each_constant_before_filling_deferred_slots() -> None:
    def candidate(title: str, constant: str, gain: int) -> dict[str, object]:
        return {
            "title": title,
            "constant": Decimal(constant),
            "targetAchievement": Decimal("100.5000"),
            "conditionalGain": gain,
            "personalFitScore": Decimal("0.02"),
            "recommendationBasis": "personalized",
            "communityDifficulty": "neutral",
            "targetEvidence": {"hitRate": Decimal("0.5"), "comfortTier": 0},
        }

    selected = _select_diverse_candidates(
        [
            candidate("13.9 A", "13.9", 12),
            candidate("13.9 B", "13.9", 12),
            candidate("13.9 C", "13.9", 12),
            candidate("13.8 A", "13.8", 10),
        ],
        3,
    )

    assert [item["title"] for item in selected] == ["13.9 A", "13.9 B", "13.8 A"]


def test_target_evidence_rejects_unproven_target_unless_chart_is_water() -> None:
    observations = [
        ObservedScore("b35", Decimal("13.9"), Decimal("100.1532")),
        ObservedScore("b35", Decimal("13.9"), Decimal("100.2461")),
        ObservedScore("b35", Decimal("13.9"), Decimal("100.0479")),
    ]
    style_tag = TagFact(1, 3, "Slide-heavy", "星星谱")
    water_tag = TagFact(2, 2, "Overrated", "水")

    assert _target_evidence(
        observations, "b35", Decimal("13.9"), Decimal("100.5"), [style_tag]
    ) is None

    exception = _target_evidence(
        observations,
        "b35",
        Decimal("13.9"),
        Decimal("100.5"),
        [style_tag, water_tag],
    )
    assert exception is not None
    assert exception["comfortTier"] == 1
    assert exception["basis"] == "community_water_exception"


def test_target_evidence_does_not_mix_b35_and_b15_samples() -> None:
    observations = [
        ObservedScore("b15", Decimal("13.7"), Decimal("100.5000")),
        ObservedScore("b35", Decimal("13.7"), Decimal("99.5000")),
    ]

    assert _target_evidence(
        observations,
        "b35",
        Decimal("13.7"),
        Decimal("100.5000"),
        [],
    ) is None


def test_proven_ceiling_uses_only_scores_that_reached_the_target() -> None:
    observations = [
        ObservedScore("b35", Decimal("13.8"), Decimal("100.5000")),
        ObservedScore("b35", Decimal("14.2"), Decimal("99.5000")),
        ObservedScore("b15", Decimal("14.0"), Decimal("100.5000")),
    ]

    assert _proven_ceiling(
        observations, "b35", Decimal("100.5000")
    ) == Decimal("13.8")


def test_dxrating_difficulty_tags_map_to_water_and_mine_correctly() -> None:
    water_tag = TagFact(11, 2, "Overrated", "水")
    mine_tag = TagFact(13, 2, "Underrated", "诈称谱")

    assert _community_difficulty([water_tag]) == "water"
    assert _community_difficulty([mine_tag]) == "mine"
    assert _community_difficulty([]) == "neutral"


def test_personalized_candidate_precedes_comfort_fallback_at_same_tier() -> None:
    def candidate(title: str, basis: str, gain: int) -> dict[str, object]:
        return {
            "title": title,
            "constant": Decimal("13.7"),
            "targetAchievement": Decimal("100.5000"),
            "conditionalGain": gain,
            "personalFitScore": Decimal("0.02") if basis == "personalized" else Decimal("0"),
            "recommendationBasis": basis,
            "communityDifficulty": "neutral",
            "targetEvidence": {"hitRate": Decimal("0.8"), "comfortTier": 0},
        }

    ordered = sorted(
        [candidate("fallback", "comfort_fallback", 12), candidate("fit", "personalized", 8)],
        key=_outside_candidate_sort_key,
    )

    assert ordered[0]["title"] == "fit"


def test_activity_window_pauses_weaknesses_during_long_inactivity() -> None:
    latest = datetime(2026, 5, 1, tzinfo=UTC)
    samples = [
        PerformanceSample(
            f"chart-{index}",
            "b35",
            Decimal("13.5"),
            Decimal("99.5"),
            latest - timedelta(days=index % 10),
        )
        for index in range(30)
    ]

    window = _activity_window(samples, datetime(2026, 9, 1, tzinfo=UTC))

    assert window.status == "inactive"
    assert not window.eligible_chart_ids


def test_activity_window_requires_new_samples_after_a_long_break() -> None:
    before_break = datetime(2026, 4, 1, tzinfo=UTC)
    after_break = datetime(2026, 9, 1, tzinfo=UTC)
    samples = [
        PerformanceSample(
            f"old-{index}",
            "b35",
            Decimal("13.5"),
            Decimal("99.5"),
            before_break - timedelta(days=index % 8),
        )
        for index in range(30)
    ]
    samples.extend(
        PerformanceSample(
            f"new-{index}",
            "b35",
            Decimal("13.5"),
            Decimal("99.5"),
            after_break + timedelta(days=index % 2),
        )
        for index in range(10)
    )

    window = _activity_window(samples, after_break + timedelta(days=2))

    assert window.status == "reentry"
    assert window.post_break_chart_count == 10
    assert not window.eligible_chart_ids


def test_activity_window_uses_post_break_samples_after_reentry_warmup() -> None:
    before_break = datetime(2026, 4, 1, tzinfo=UTC)
    after_break = datetime(2026, 9, 1, tzinfo=UTC)
    samples = [
        PerformanceSample(
            f"old-{index}",
            "b35",
            Decimal("13.5"),
            Decimal("99.5"),
            before_break - timedelta(days=index % 8),
        )
        for index in range(30)
    ]
    samples.extend(
        PerformanceSample(
            f"new-{index}",
            "b35",
            Decimal("13.5"),
            Decimal("99.5"),
            after_break + timedelta(days=index % 3),
        )
        for index in range(24)
    )

    window = _activity_window(samples, after_break + timedelta(days=3))

    assert window.status == "ready"
    assert len(window.eligible_chart_ids) == 24
    assert all(chart_id.startswith("new-") for chart_id in window.eligible_chart_ids)


def test_weakness_profile_needs_repeated_recent_underperformance() -> None:
    tag = TagFact(7, 3, "Slide-heavy", "滑键偏重")
    residuals = {f"chart-{index}": Decimal("-0.12") for index in range(8)}
    weaknesses = _weakness_profile(
        residuals,
        {chart_id: [tag] for chart_id in residuals},
    )

    assert len(weaknesses) == 1
    assert weaknesses[0]["confidence"] == "strong"
    assert weaknesses[0]["score"] < 0
    risk, reasons = _weakness_risk([tag], {7: weaknesses[0]})
    assert risk == "avoid"
    assert reasons[0]["nameEn"] == "Slide-heavy"


def test_candidate_mix_reserves_space_for_played_and_exploration() -> None:
    def candidate(title: str, status: str) -> dict[str, object]:
        return {
            "title": title,
            "constant": Decimal("13.7"),
            "targetAchievement": Decimal("100.0000"),
            "conditionalGain": 2,
            "achievementGap": Decimal("0.5") if status == "played" else None,
            "personalFitScore": Decimal("0.02"),
            "recommendationBasis": "personalized",
            "communityDifficulty": "neutral",
            "weaknessRisk": "none",
            "scoreStatus": status,
            "targetEvidence": {"hitRate": Decimal("0.8"), "comfortTier": 0},
        }

    selected = _select_candidate_mix(
        [
            *[candidate(f"played-{index}", "played") for index in range(6)],
            *[candidate(f"new-{index}", "no_record") for index in range(6)],
        ],
        6,
    )

    assert sum(item["scoreStatus"] == "played" for item in selected) == 3
    assert sum(item["scoreStatus"] == "no_record" for item in selected) == 3


def test_candidate_sort_places_weakness_caution_after_clear_candidate() -> None:
    def candidate(title: str, weakness_risk: str) -> dict[str, object]:
        return {
            "title": title,
            "constant": Decimal("13.7"),
            "targetAchievement": Decimal("99.5000"),
            "conditionalGain": 3,
            "achievementGap": Decimal("0.5"),
            "personalFitScore": Decimal("0.02"),
            "recommendationBasis": "personalized",
            "communityDifficulty": "neutral",
            "weaknessRisk": weakness_risk,
            "targetEvidence": {
                "hitRate": Decimal("0.8"),
                "comfortTier": 0,
            },
        }

    ordered = sorted(
        [candidate("caution", "caution"), candidate("clear", "none")],
        key=_outside_candidate_sort_key,
    )

    assert [item["title"] for item in ordered] == ["clear", "caution"]
