from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog.versioning import VersionPolicy
from app.config import get_settings
from app.db.models import (
    CatalogSnapshot,
    Chart,
    ChartConstant,
    ChartRevision,
    ChartTag,
    GameVersion,
    ImportEntry,
    PlayerImport,
    Song,
    Tag,
)
from app.rating.calculator import calculate_chart_rating

ALGORITHM_VERSION = "b50-personal-fit-v0.6"
TARGET_ACHIEVEMENTS = (Decimal("100.0000"), Decimal("100.5000"))
COVER_BASE_URL = "https://dp4p6x0xfi5o9.cloudfront.net/maimai/img/cover"
COVER_NAME_PATTERN = re.compile(r"^[0-9a-f]{64}(?:\.png)?$")


class RecommendationError(ValueError):
    pass


@dataclass(frozen=True)
class ObservedScore:
    bucket: str
    constant: Decimal
    achievement: Decimal


@dataclass(frozen=True)
class TagFact:
    tag_id: int
    group_id: int
    name_en: str
    name_zh_hans: str


STYLE_TAG_GROUPS = {1, 3}
MIN_STRENGTH_SAMPLES = 3


def _first_beating_target(constant: Decimal, threshold: int) -> tuple[Decimal, int] | None:
    for achievement in TARGET_ACHIEVEMENTS:
        rating = calculate_chart_rating(constant, achievement)
        if rating > threshold:
            return achievement, rating
    return None


def _similar_evidence(
    observations: list[ObservedScore],
    bucket: str,
    constant: Decimal,
    target: Decimal,
) -> dict[str, object]:
    nearby = [
        item
        for item in observations
        if item.bucket == bucket and abs(item.constant - constant) <= Decimal("0.3")
    ]
    hits = sum(item.achievement >= target for item in nearby)
    rate = Decimal(hits) / Decimal(len(nearby)) if nearby else Decimal("0")
    if len(nearby) >= 5 and rate >= Decimal("0.6"):
        strength = "strong"
    elif len(nearby) >= 3 and rate >= Decimal("0.33"):
        strength = "limited"
    else:
        strength = "insufficient"
    return {
        "sampleCount": len(nearby),
        "hitCount": hits,
        "hitRate": rate.quantize(Decimal("0.001")),
        "strength": strength,
        "isSuccessProbability": False,
    }


def _version_policy(session: Session, snapshot: CatalogSnapshot) -> VersionPolicy:
    versions = tuple(session.scalars(select(GameVersion.name).order_by(GameVersion.ordinal)).all())
    current_version = str(json.loads(snapshot.validation_report)["current_version"])
    return VersionPolicy(versions, current_version, b15_version_count=2)


def _profile(entries: list[ImportEntry], bucket: str) -> dict[str, object]:
    selected = [entry for entry in entries if entry.bucket == bucket]
    constants = [entry.chart_constant for entry in selected if entry.chart_constant is not None]
    achievements = [entry.achievement for entry in selected if entry.achievement is not None]
    return {
        "entryCount": len(selected),
        "constantMin": min(constants) if constants else None,
        "constantMax": max(constants) if constants else None,
        "medianAchievement": median(achievements) if achievements else None,
        "atOrAbove100_5": sum(value >= Decimal("100.5") for value in achievements),
    }


def _performance_residuals(entries: list[ImportEntry]) -> dict[str, Decimal]:
    usable = [
        entry
        for entry in entries
        if entry.chart_id and entry.chart_constant is not None and entry.achievement is not None
    ]
    result: dict[str, Decimal] = {}
    for entry in usable:
        peers = [
            peer.achievement
            for peer in usable
            if peer.bucket == entry.bucket
            and peer.achievement is not None
            and peer.chart_constant is not None
            and abs(peer.chart_constant - entry.chart_constant) <= Decimal("0.2")
        ]
        if len(peers) < 3 or entry.achievement is None or entry.chart_id is None:
            continue
        result[entry.chart_id] = entry.achievement - Decimal(str(median(peers)))
    return result


def _strength_profile(
    residuals: dict[str, Decimal],
    tags_by_chart: dict[str, list[TagFact]],
) -> list[dict[str, object]]:
    grouped: dict[int, tuple[TagFact, list[Decimal]]] = {}
    for chart_id, residual in residuals.items():
        for tag in tags_by_chart.get(chart_id, []):
            if tag.group_id not in STYLE_TAG_GROUPS:
                continue
            _fact, values = grouped.setdefault(tag.tag_id, (tag, []))
            values.append(residual)

    strengths: list[dict[str, object]] = []
    for tag, values in grouped.values():
        if len(values) < MIN_STRENGTH_SAMPLES:
            continue
        raw_mean = sum(values, Decimal("0")) / Decimal(len(values))
        shrunk_score = raw_mean * Decimal(len(values)) / Decimal(len(values) + 5)
        if shrunk_score <= Decimal("0.005"):
            continue
        if len(values) >= 8 and shrunk_score >= Decimal("0.050"):
            confidence = "strong"
        elif len(values) >= 5:
            confidence = "limited"
        else:
            confidence = "exploratory"
        strengths.append(
            {
                "tagId": tag.tag_id,
                "nameEn": tag.name_en,
                "nameZhHans": tag.name_zh_hans,
                "sampleCount": len(values),
                "meanResidual": raw_mean.quantize(Decimal("0.0001")),
                "score": shrunk_score.quantize(Decimal("0.0001")),
                "confidence": confidence,
            }
        )
    strengths.sort(
        key=lambda item: (
            -Decimal(str(item["score"])),
            -int(item["sampleCount"]),
            str(item["nameEn"]),
        )
    )
    return strengths[:5]


def _outside_candidate_sort_key(candidate: dict[str, object]) -> tuple[object, ...]:
    evidence = candidate["targetEvidence"]
    assert isinstance(evidence, dict)
    return (
        int(evidence["comfortTier"]),
        0 if candidate["recommendationBasis"] == "personalized" else 1,
        -int(candidate["conditionalGain"]),
        0 if candidate["communityDifficulty"] == "water" else 1,
        -Decimal(str(evidence["hitRate"])),
        -Decimal(str(candidate["personalFitScore"])),
        Decimal(str(candidate["targetAchievement"])),
        Decimal(str(candidate["constant"])),
        str(candidate["title"]),
    )


def _community_difficulty(candidate_tags: list[TagFact]) -> str:
    names = {tag.name_en for tag in candidate_tags}
    if "Underrated" in names:
        return "mine"
    if "Overrated" in names:
        return "water"
    return "neutral"


def _target_evidence(
    observations: list[ObservedScore],
    constant: Decimal,
    target: Decimal,
    candidate_tags: list[TagFact],
) -> dict[str, object] | None:
    exact = [item for item in observations if item.constant == constant]
    comparable = exact or [
        item for item in observations if abs(item.constant - constant) <= Decimal("0.1")
    ]
    hits = sum(item.achievement >= target for item in comparable)
    is_water = _community_difficulty(candidate_tags) == "water"
    if hits:
        comfort_tier = 0
        basis = "player_exact" if exact else "player_nearby"
    elif is_water:
        comfort_tier = 1
        basis = "community_water_exception"
    else:
        return None
    hit_rate = Decimal(hits) / Decimal(len(comparable)) if comparable else Decimal("0")
    return {
        "sampleCount": len(comparable),
        "hitCount": hits,
        "hitRate": hit_rate.quantize(Decimal("0.001")),
        "basis": basis,
        "comfortTier": comfort_tier,
        "isSuccessProbability": False,
    }


def _select_diverse_candidates(
    candidates: list[dict[str, object]],
    limit: int,
) -> list[dict[str, object]]:
    ordered = sorted(candidates, key=_outside_candidate_sort_key)
    selected: list[dict[str, object]] = []
    deferred: list[dict[str, object]] = []
    selected_songs: set[str] = set()
    constant_counts: dict[Decimal, int] = {}

    for candidate in ordered:
        title = str(candidate["title"])
        if title in selected_songs:
            continue
        constant = Decimal(str(candidate["constant"]))
        if constant_counts.get(constant, 0) >= 2:
            deferred.append(candidate)
            continue
        selected.append(candidate)
        selected_songs.add(title)
        constant_counts[constant] = constant_counts.get(constant, 0) + 1
        if len(selected) >= limit:
            return selected

    for candidate in deferred:
        title = str(candidate["title"])
        if title in selected_songs:
            continue
        selected.append(candidate)
        selected_songs.add(title)
        if len(selected) >= limit:
            break
    return selected


def _cover_urls(snapshot: CatalogSnapshot) -> dict[str, str]:
    raw_path = get_settings().raw_catalog_dir / f"{snapshot.content_hash}.json"
    if not raw_path.exists():
        return {}
    try:
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    result: dict[str, str] = {}
    for song in payload.get("songs", []):
        song_id = str(song.get("id", ""))
        image_name = str(song.get("imageName", ""))
        if not song_id or not COVER_NAME_PATTERN.fullmatch(image_name):
            continue
        filename = image_name if image_name.endswith(".png") else f"{image_name}.png"
        result[song_id] = f"{COVER_BASE_URL}/{filename}"
    return result


def build_recommendations(
    session: Session,
    import_id: str,
    *,
    limit_per_bucket: int = 10,
) -> dict[str, object]:
    player_import = session.get(PlayerImport, import_id)
    if player_import is None:
        raise RecommendationError("Import not found")
    if player_import.status != "confirmed":
        raise RecommendationError("Confirm all 50 entries before generating recommendations")
    snapshot = session.get(CatalogSnapshot, player_import.catalog_snapshot_id)
    if snapshot is None:
        raise RecommendationError("Catalog snapshot is unavailable")

    entries = list(
        session.scalars(
            select(ImportEntry)
            .where(ImportEntry.import_id == import_id)
            .order_by(ImportEntry.slot)
        ).all()
    )
    if len(entries) != 50 or any(entry.calculated_rating is None for entry in entries):
        raise RecommendationError("Confirmed import does not contain 50 calculated ratings")

    thresholds = {
        bucket: min(
            entry.calculated_rating
            for entry in entries
            if entry.bucket == bucket and entry.calculated_rating is not None
        )
        for bucket in ("b35", "b15")
    }
    observations = [
        ObservedScore(entry.bucket, entry.chart_constant, entry.achievement)
        for entry in entries
        if entry.chart_constant is not None and entry.achievement is not None
    ]
    cover_urls = _cover_urls(snapshot)
    current_chart_ids = {entry.chart_id for entry in entries if entry.chart_id}
    chart_song_ids = dict(
        session.execute(
            select(Chart.id, Chart.song_id).where(Chart.id.in_(current_chart_ids))
        ).all()
    )
    tag_rows = session.execute(
        select(
            ChartTag.chart_id,
            Tag.id,
            Tag.group_id,
            Tag.name_en,
            Tag.name_zh_hans,
        )
        .join(Tag, Tag.id == ChartTag.tag_id)
        .where(ChartTag.snapshot_id == snapshot.id)
    ).all()
    tags_by_chart: dict[str, list[TagFact]] = {}
    for chart_id, tag_id, group_id, name_en, name_zh_hans in tag_rows:
        tags_by_chart.setdefault(chart_id, []).append(
            TagFact(tag_id, group_id, name_en, name_zh_hans)
        )
    residuals = _performance_residuals(entries)
    strengths = _strength_profile(residuals, tags_by_chart)
    strengths_by_id = {int(item["tagId"]): item for item in strengths}

    in_list: list[dict[str, object]] = []
    for entry in entries:
        if (
            entry.chart_constant is None
            or entry.achievement is None
            or entry.calculated_rating is None
        ):
            continue
        target = Decimal("100.5000")
        target_rating = calculate_chart_rating(entry.chart_constant, target)
        gain = target_rating - entry.calculated_rating
        if gain <= 0:
            continue
        evidence = _similar_evidence(observations, entry.bucket, entry.chart_constant, target)
        in_list.append(
            {
                "kind": "in_list",
                "slot": entry.slot,
                "chartId": entry.chart_id,
                "title": entry.title,
                "coverUrl": cover_urls.get(chart_song_ids.get(entry.chart_id, "")),
                "chartType": entry.chart_type,
                "difficulty": entry.difficulty,
                "bucket": entry.bucket,
                "constant": entry.chart_constant,
                "currentAchievement": entry.achievement,
                "currentRating": entry.calculated_rating,
                "targetAchievement": target,
                "targetRating": target_rating,
                "conditionalGain": gain,
                "achievementGap": target - entry.achievement,
                "evidence": evidence,
                "fact": (
                    f"达到 {target}% 时，按当前图片定数可从 {entry.calculated_rating} "
                    f"升至 {target_rating} Rating"
                ),
            }
        )
    in_list.sort(
        key=lambda item: (
            Decimal(str(item["targetAchievement"]))
            - Decimal(str(item["currentAchievement"])),
            -int(item["conditionalGain"]),
            int(item["slot"]),
        )
    )

    policy = _version_policy(session, snapshot)
    catalog_rows = session.execute(
        select(Chart, Song, ChartRevision, ChartConstant)
        .join(Song, Song.id == Chart.song_id)
        .join(
            ChartRevision,
            (ChartRevision.chart_id == Chart.id)
            & (ChartRevision.snapshot_id == snapshot.id),
        )
        .join(
            ChartConstant,
            (ChartConstant.chart_id == Chart.id)
            & (ChartConstant.snapshot_id == snapshot.id),
        )
        .where(ChartRevision.is_special.is_(False))
        .order_by(ChartConstant.confidence.desc())
    ).all()
    seen_charts: set[str] = set()
    outside_by_bucket: dict[str, list[dict[str, object]]] = {"b35": [], "b15": []}
    profile_by_bucket = {bucket: _profile(entries, bucket) for bucket in ("b35", "b15")}
    for chart, song, revision, constant in catalog_rows:
        if chart.id in seen_charts:
            continue
        seen_charts.add(chart.id)
        if chart.id in current_chart_ids:
            continue
        bucket = policy.bucket_for(revision.intl_version)
        if bucket is None:
            continue
        maximum = profile_by_bucket[bucket]["constantMax"]
        if maximum is None or constant.constant_value > Decimal(str(maximum)):
            continue
        candidate_tags = tags_by_chart.get(chart.id, [])
        community_difficulty = _community_difficulty(candidate_tags)
        if community_difficulty == "mine":
            continue
        fit_reasons = [
            strengths_by_id[tag.tag_id]
            for tag in candidate_tags
            if tag.tag_id in strengths_by_id
        ]
        fit_reasons.sort(key=lambda item: -Decimal(str(item["score"])))
        personal_fit_score = sum(
            (Decimal(str(item["score"])) for item in fit_reasons),
            Decimal("0"),
        )
        target = _first_beating_target(constant.constant_value, thresholds[bucket])
        if target is None:
            continue
        target_achievement, target_rating = target
        target_evidence = _target_evidence(
            observations,
            constant.constant_value,
            target_achievement,
            candidate_tags,
        )
        if target_evidence is None:
            continue
        evidence = _similar_evidence(
            observations,
            bucket,
            constant.constant_value,
            target_achievement,
        )
        outside_by_bucket[bucket].append(
            {
                "kind": "outside_b50",
                "strategy": "steady" if target_achievement == Decimal("100.0000") else "sprint",
                "chartId": chart.id,
                "title": song.title,
                "coverUrl": cover_urls.get(song.id),
                "artist": song.artist,
                "chartType": chart.chart_type,
                "difficulty": chart.difficulty,
                "bucket": bucket,
                "version": revision.intl_version,
                "constant": constant.constant_value,
                "constantConfidence": constant.confidence,
                "constantDerivation": constant.derivation,
                "targetAchievement": target_achievement,
                "targetRating": target_rating,
                "replacementThreshold": thresholds[bucket],
                "conditionalGain": target_rating - thresholds[bucket],
                "personalFitScore": personal_fit_score.quantize(Decimal("0.0001")),
                "recommendationBasis": (
                    "personalized" if fit_reasons else "comfort_fallback"
                ),
                "communityDifficulty": community_difficulty,
                "fitReasons": [
                    {
                        "nameEn": item["nameEn"],
                        "nameZhHans": item["nameZhHans"],
                        "sampleCount": item["sampleCount"],
                        "confidence": item["confidence"],
                    }
                    for item in fit_reasons[:3]
                ],
                "targetEvidence": target_evidence,
                "evidence": evidence,
                "fact": (
                    f"未进入当前 B50；若达到 {target_achievement}% 并替换 "
                    f"{bucket.upper()} 最低项，可条件增加 "
                    f"{target_rating - thresholds[bucket]} Rating"
                ),
            }
        )

    outside: list[dict[str, object]] = []
    for _bucket, candidates in outside_by_bucket.items():
        outside.extend(_select_diverse_candidates(candidates, limit_per_bucket))

    return {
        "importId": import_id,
        "status": "experimental",
        "algorithmVersion": ALGORITHM_VERSION,
        "coverage": "best50_only",
        "totalRating": sum(entry.calculated_rating or 0 for entry in entries),
        "thresholds": thresholds,
        "profile": profile_by_bucket,
        "personalProfile": {
            "method": "same-bucket nearby-constant residual with sample shrinkage",
            "strengths": strengths,
            "isCausal": False,
        },
        "inList": in_list[:12],
        "outside": outside,
        "provenance": {
            "catalogSnapshotId": snapshot.id,
            "catalogSource": "DXRating public community catalog",
            "constantsAreOfficial": False,
            "coverSource": "arcade-songs public cover CDN (remote, not stored locally)",
        },
        "caveats": [
            "相近定数证据来自已筛选的 B50，不是真实成功率。",
            "未进入当前 B50 不代表未游玩。",
            "榜外候选定数来自 DXRating 社区目录，需与 International 实机核对。",
            "优势标签来自被筛选后的 B50，只表示已证明的相对表现，不代表因果能力。",
            "谱面通常包含多种元素；匹配某个标签不代表它是该谱面的唯一类型。",
            "DXRating 社区“水”标签会作为正向信号；“诈称谱”默认从上分推荐排除。",
            "超出本人已证明目标的谱面默认不推荐；社区标记为“水”时才作为低优先级例外。",
            "榜外增益是假设达到目标成绩并替换当前最低项后的条件增益。",
        ],
    }
