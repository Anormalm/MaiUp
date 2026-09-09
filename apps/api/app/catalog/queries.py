from __future__ import annotations

import json

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.catalog.versioning import VersionPolicy
from app.db.models import (
    CatalogSnapshot,
    Chart,
    ChartConstant,
    ChartRevision,
    GameVersion,
    Song,
    SongAlias,
)


def latest_published_snapshot(session: Session) -> CatalogSnapshot | None:
    return session.scalar(
        select(CatalogSnapshot)
        .where(CatalogSnapshot.status == "published")
        .order_by(CatalogSnapshot.published_at.desc())
        .limit(1)
    )


def catalog_status(session: Session) -> dict[str, object]:
    snapshot = latest_published_snapshot(session)
    if snapshot is None:
        return {"ready": False, "message": "No validated International catalog is published"}
    report = snapshot.validation_report
    return {
        "ready": True,
        "snapshotId": snapshot.id,
        "sourceUpdatedAt": snapshot.source_updated_at,
        "publishedAt": snapshot.published_at,
        "songCount": snapshot.song_count,
        "chartCount": snapshot.chart_count,
        "warningCount": snapshot.warning_count,
        "validation": report,
    }


def search_songs(session: Session, query: str, *, limit: int = 20) -> list[dict[str, object]]:
    snapshot = latest_published_snapshot(session)
    if snapshot is None:
        return []
    normalized = query.strip().lower()
    if not normalized:
        return []
    pattern = f"%{normalized}%"
    rows = session.execute(
        select(
            Song.id,
            Song.title,
            Song.artist,
            func.group_concat(func.distinct(SongAlias.name)).label("aliases"),
        )
        .outerjoin(SongAlias, SongAlias.song_id == Song.id)
        .where(
            or_(
                func.lower(Song.title).like(pattern),
                func.lower(SongAlias.name).like(pattern),
            )
        )
        .group_by(Song.id)
        .order_by(Song.title)
        .limit(max(1, min(limit, 50)))
    ).all()
    return [
        {
            "id": row.id,
            "title": row.title,
            "artist": row.artist,
            "aliases": row.aliases.split(",") if row.aliases else [],
        }
        for row in rows
    ]


def chart_constant(session: Session, chart_id: str) -> dict[str, object] | None:
    snapshot = latest_published_snapshot(session)
    if snapshot is None:
        return None
    row = session.execute(
        select(ChartConstant, ChartRevision)
        .join(
            ChartRevision,
            (ChartRevision.snapshot_id == ChartConstant.snapshot_id)
            & (ChartRevision.chart_id == ChartConstant.chart_id),
        )
        .where(
            ChartConstant.snapshot_id == snapshot.id,
            ChartConstant.chart_id == chart_id,
        )
        .order_by(ChartConstant.confidence.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    constant, revision = row
    return {
        "chartId": chart_id,
        "constant": constant.constant_value,
        "confidence": constant.confidence,
        "derivation": constant.derivation,
        "region": constant.region,
        "version": revision.intl_version,
        "snapshotId": snapshot.id,
    }


def search_charts(
    session: Session,
    query: str,
    *,
    bucket: str | None = None,
    limit: int = 20,
) -> list[dict[str, object]]:
    snapshot = latest_published_snapshot(session)
    if snapshot is None:
        return []
    normalized = query.strip().lower()
    if not normalized:
        return []
    current_version = str(json.loads(snapshot.validation_report)["current_version"])
    ordered_versions = tuple(
        session.scalars(select(GameVersion.name).order_by(GameVersion.ordinal)).all()
    )
    policy = VersionPolicy(ordered_versions, current_version, b15_version_count=2)
    pattern = f"%{normalized}%"
    rows = session.execute(
        select(Chart, Song, ChartRevision, ChartConstant)
        .join(Song, Song.id == Chart.song_id)
        .join(
            ChartRevision,
            (ChartRevision.chart_id == Chart.id) & (ChartRevision.snapshot_id == snapshot.id),
        )
        .join(
            ChartConstant,
            (ChartConstant.chart_id == Chart.id) & (ChartConstant.snapshot_id == snapshot.id),
        )
        .outerjoin(SongAlias, SongAlias.song_id == Song.id)
        .where(
            or_(
                func.lower(Song.title).like(pattern),
                func.lower(SongAlias.name).like(pattern),
            ),
            ChartRevision.is_special.is_(False),
        )
        .order_by(Song.title, Chart.difficulty, Chart.chart_type, ChartConstant.confidence.desc())
        .limit(max(50, min(limit * 12, 600)))
    ).all()

    results: list[dict[str, object]] = []
    seen: set[str] = set()
    for chart, song, revision, constant in rows:
        if chart.id in seen:
            continue
        seen.add(chart.id)
        chart_bucket = policy.bucket_for(revision.intl_version)
        if chart_bucket is None or (bucket and chart_bucket != bucket):
            continue
        results.append(
            {
                "chartId": chart.id,
                "title": song.title,
                "artist": song.artist,
                "chartType": chart.chart_type,
                "difficulty": chart.difficulty,
                "level": revision.level,
                "constant": constant.constant_value,
                "constantConfidence": constant.confidence,
                "constantDerivation": constant.derivation,
                "version": revision.intl_version,
                "bucket": chart_bucket,
            }
        )
        if len(results) >= max(1, min(limit, 50)):
            break
    return results
