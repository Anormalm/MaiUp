"""Import the clipboard table produced by mai-tools' score-download tool.

This is a data-format adapter, not a copy of the GPL-licensed scraper. No requests
are made to maimai NET, and catalog constants/versions always come from MaiUp.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog.queries import latest_published_snapshot
from app.db.models import (
    Chart,
    ChartConstant,
    ChartRevision,
    ImportEntry,
    PlayerImport,
    ScoreExport,
    Song,
    SongAlias,
)
from app.imports.service import PlayerImportError, _version_policy, get_import
from app.rating.best50 import ScoreRecord, build_best50

MAX_EXPORT_BYTES = 2_000_000
MAX_EXPORT_ROWS = 10_000
HEADERS = {
    "title": ("Song", "歌曲", "노래"),
    "genre": ("Genre", "分類", "장르"),
    "version": ("Version", "版本", "버전"),
    "chartType": ("Chart", "譜面", "유형"),
    "difficulty": ("Difficulty", "難度", "난이도"),
    "level": ("Level", "等級", "레벨"),
    "exportedConstant": ("Chart Constant", "定數", "상수"),
    "achievement": ("Achv", "達成率", "정확도"),
    "rank": ("Rank", "등급"),
    "fullCombo": ("FC/AP",),
    "sync": ("Sync",),
    "dxScore": ("DX Score", "DX 分數", "DX 점수"),
    "dxRatio": ("DX %",),
    "dxStar": ("DX ✦",),
}
HEADER_KEYS = {label: key for key, labels in HEADERS.items() for label in labels}
REQUIRED = {"title", "chartType", "difficulty", "achievement", "fullCombo"}
DIFFICULTIES = {
    "BASIC": "basic",
    "ADVANCED": "advanced",
    "EXPERT": "expert",
    "MASTER": "master",
    "RE:MASTER": "remaster",
}


def normalize_title(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def parse_export(text: str) -> list[dict[str, object]]:
    if len(text.encode("utf-8")) > MAX_EXPORT_BYTES:
        raise PlayerImportError("Score export exceeds the 2 MB limit")
    lines = text.lstrip("\ufeff").strip("\r\n").splitlines()
    if len(lines) < 2:
        raise PlayerImportError("Paste the header and score rows from mai-tools")
    if len(lines) - 1 > MAX_EXPORT_ROWS:
        raise PlayerImportError("Score export exceeds the 10,000 row limit")
    headers = [cell.strip() for cell in lines[0].split("\t")]
    if any(header not in HEADER_KEYS for header in headers):
        raise PlayerImportError("Unrecognized column; paste the original mai-tools table")
    keys = [HEADER_KEYS[header] for header in headers]
    if len(set(keys)) != len(keys) or not REQUIRED.issubset(keys):
        raise PlayerImportError("Include Song, Chart, Difficulty, Achv and FC/AP exactly once")
    records = []
    identities = set()
    for line_number, line in enumerate(lines[1:], 2):
        cells = line.split("\t")
        if len(cells) != len(keys) or any(len(cell) > 300 for cell in cells):
            raise PlayerImportError(f"Row {line_number}: invalid number or length of cells")
        # A real song is titled U+3000; mai-tools can also export its name as empty.
        # Preserve the title and let normalized catalog matching resolve it.
        record: dict[str, object] = {
            key: cell if key == "title" else cell.strip()
            for key, cell in zip(keys, cells, strict=True)
        }
        title = str(record["title"])
        chart_type = {"STD": "std", "DX": "dx"}.get(str(record["chartType"]).upper())
        difficulty = DIFFICULTIES.get(str(record["difficulty"]).upper())
        achievement = str(record["achievement"])
        combo = str(record["fullCombo"]).upper()
        if not chart_type:
            raise PlayerImportError(
                f"Row {line_number}: invalid Chart {record['chartType']!r}; expected STD or DX"
            )
        if not difficulty:
            raise PlayerImportError(
                f"Row {line_number}: invalid Difficulty {record['difficulty']!r}; "
                "expected BASIC, ADVANCED, EXPERT, MASTER or Re:MASTER"
            )
        if not re.fullmatch(r"\d{1,3}(?:\.\d{1,4})?%", achievement):
            raise PlayerImportError(f"Row {line_number}: invalid Achievement percentage")
        value = Decimal(achievement[:-1])
        if not 0 <= value <= 101:
            raise PlayerImportError(f"Row {line_number}: Achievement must be between 0 and 101")
        if combo not in {"-", "FC", "FC+", "AP", "AP+"}:
            raise PlayerImportError(f"Row {line_number}: invalid FC/AP marker")
        identity = (normalize_title(title), chart_type, difficulty)
        if identity in identities:
            raise PlayerImportError(f"Row {line_number}: duplicate chart")
        identities.add(identity)
        record.update(
            row=line_number,
            chartType=chart_type,
            difficulty=difficulty,
            achievement=str(value),
            fullCombo=None if combo == "-" else combo,
        )
        records.append(record)
    return records


def create_score_export(session: Session, text: str) -> dict[str, object]:
    records = parse_export(text)
    snapshot = latest_published_snapshot(session)
    if snapshot is None:
        raise PlayerImportError("Sync a validated International catalog before importing scores")
    policy = _version_policy(session, json.loads(snapshot.validation_report)["current_version"])
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
        .order_by(ChartConstant.confidence.desc(), ChartConstant.source_id)
    ).all()
    aliases: dict[str, set[str]] = {}
    for song_id, name in session.execute(select(SongAlias.song_id, SongAlias.name)):
        aliases.setdefault(song_id, set()).add(normalize_title(name))
    index: dict[tuple[str, str, str], dict[str, tuple]] = {}
    for chart, song, revision, constant in rows:
        for name in {normalize_title(song.title)} | aliases.get(song.id, set()):
            key = (name, chart.chart_type, chart.difficulty)
            index.setdefault(key, {}).setdefault(chart.id, (chart, song, revision, constant))
    scores = []
    matched = {}
    issues = []
    for record in records:
        key = (normalize_title(str(record["title"])), record["chartType"], record["difficulty"])
        candidates = index.get(key, {})
        issue = None
        if len(candidates) != 1:
            issue = "ambiguous_chart" if candidates else "chart_not_found"
        else:
            chart, song, revision, constant = next(iter(candidates.values()))
            bucket = policy.bucket_for(
                revision.intl_version, rating_eligible=not revision.is_special
            )
            if bucket is None:
                issue = "chart_not_rating_eligible"
            elif chart.id in matched:
                raise PlayerImportError(
                    f"Row {record['row']}: duplicate chart after alias matching"
                )
            else:
                score = ScoreRecord(
                    chart_id=chart.id,
                    chart_version=revision.intl_version,
                    chart_constant=constant.constant_value,
                    achievement=Decimal(str(record["achievement"])),
                    full_combo=record["fullCombo"],
                )
                scores.append(score)
                matched[chart.id] = (chart, song)
                record.update(
                    chartId=chart.id,
                    bucket=bucket,
                    catalogConstant=str(constant.constant_value),
                    catalogVersion=revision.intl_version,
                    calculatedRating=score.rating,
                )
        record["issueCode"] = issue
        if issue:
            issues.append({"row": record["row"], "title": record["title"], "code": issue})
    best50 = build_best50(scores, policy)
    now = datetime.now(UTC)
    import_id = str(uuid.uuid4())
    session.add(
        PlayerImport(
            id=import_id,
            source_type="mai_tools",
            status="needs_review",
            coverage="exported_scores",
            catalog_snapshot_id=snapshot.id,
            image_fingerprint=hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
            image_format="tsv",
            image_width=0,
            image_height=0,
            source_image_stored=False,
            created_at=now,
            expires_at=now + timedelta(hours=24),
        )
    )
    session.flush()
    session.add(
        ScoreExport(
            import_id=import_id,
            source_origin="https://maimaidx-eng.com",
            records_json=json.dumps(records, ensure_ascii=False),
            issues_json=json.dumps(issues, ensure_ascii=False),
        )
    )
    for bucket, ranked in (("b35", best50.b35), ("b15", best50.b15)):
        for position, item in enumerate(ranked, 1):
            score = item.score
            chart, song = matched[score.chart_id]
            session.add(
                ImportEntry(
                    import_id=import_id,
                    slot=position if bucket == "b35" else 35 + position,
                    bucket=bucket,
                    chart_id=chart.id,
                    title=song.title,
                    chart_type=chart.chart_type,
                    difficulty=chart.difficulty,
                    chart_version=score.chart_version,
                    chart_constant=score.chart_constant,
                    achievement=score.achievement,
                    full_combo=score.full_combo,
                    displayed_rating=None,
                    calculated_rating=item.rating,
                    needs_review=False,
                    issue_code=None,
                )
            )
    session.commit()
    return get_score_export(session, import_id)


def get_score_export(session: Session, import_id: str) -> dict[str, object]:
    export = session.get(ScoreExport, import_id)
    state = get_import(session, import_id)
    if export is None or state is None:
        raise PlayerImportError("Score export not found")
    return {
        **state,
        "sourceOrigin": export.source_origin,
        "scores": json.loads(export.records_json),
        "issues": json.loads(export.issues_json),
    }
