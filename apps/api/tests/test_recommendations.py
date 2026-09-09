from decimal import Decimal

from app.recommendations.service import (
    ObservedScore,
    TagFact,
    _community_difficulty,
    _first_beating_target,
    _outside_candidate_sort_key,
    _select_diverse_candidates,
    _similar_evidence,
    _strength_profile,
    _target_evidence,
)


def test_first_beating_target_uses_the_lower_sufficient_achievement() -> None:
    assert _first_beating_target(Decimal("14.0"), 300) == (Decimal("100.0000"), 302)
    assert _first_beating_target(Decimal("13.4"), 300) == (Decimal("100.5000"), 301)
    assert _first_beating_target(Decimal("13.0"), 300) is None


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


def test_outside_candidates_prioritize_rating_gain_before_tag_fit() -> None:
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

    assert ordered[0]["title"] == "13.6 bird plus"


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
        observations, Decimal("13.9"), Decimal("100.5"), [style_tag]
    ) is None

    exception = _target_evidence(
        observations,
        Decimal("13.9"),
        Decimal("100.5"),
        [style_tag, water_tag],
    )
    assert exception is not None
    assert exception["comfortTier"] == 1
    assert exception["basis"] == "community_water_exception"


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
