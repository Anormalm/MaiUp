from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.schemas import CompleteScoreImportRequest
from app.db.base import Base
from app.db.models import (
    CatalogSnapshot,
    Chart,
    ChartRevision,
    DataSource,
    PlayerScore,
    Song,
)
from app.imports.complete_scores import get_complete_score_import, import_complete_scores


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        db.add(
            DataSource(
                id="source",
                name="fixture",
                url="https://example.invalid",
                region_scope="intl",
                trust_level="fixture",
                license_note="test fixture",
            )
        )
        db.add(
            CatalogSnapshot(
                id="snapshot",
                source_id="source",
                schema_version=1,
                source_updated_at="2026-01-01T00:00:00Z",
                content_hash="b" * 64,
                fetched_at=datetime.now(UTC),
                published_at=datetime.now(UTC),
                status="published",
                song_count=1,
                chart_count=1,
                warning_count=0,
                validation_report="{}",
            )
        )
        db.add(
            Song(
                id="song",
                title="Test Song",
                artist="artist",
                category="category",
                bpm=Decimal("180"),
                source_version="CURRENT",
                is_locked=False,
            )
        )
        db.add(Chart(id="chart", song_id="song", chart_type="dx", difficulty="master"))
        db.add(
            ChartRevision(
                snapshot_id="snapshot",
                chart_id="chart",
                level="13+",
                base_internal_level=Decimal("13.8"),
                tap=1,
                hold=1,
                slide=1,
                touch=1,
                break_count=1,
                total=5,
                is_special=False,
                base_version="CURRENT",
                intl_version="CURRENT",
                release_date=date(2026, 1, 1),
            )
        )
        db.commit()
        yield db


def payload(scores: list[dict[str, object]]) -> CompleteScoreImportRequest:
    return CompleteScoreImportRequest.model_validate(
        {
            "schemaVersion": 1,
            "sourceRegion": "international",
            "sourceName": "test",
            "exportedAt": "2026-09-10T00:00:00Z",
            "scores": scores,
        }
    )


def test_import_matches_exact_chart_and_reports_coverage(session: Session) -> None:
    result = import_complete_scores(
        session,
        payload(
            [
                {
                    "title": "  TEST   song ",
                    "chartType": "dx",
                    "difficulty": "master",
                    "achievement": "100.1234",
                    "fullCombo": "FC+",
                },
                {
                    "title": "Unknown",
                    "chartType": "std",
                    "difficulty": "expert",
                    "achievement": "99.0000",
                },
            ]
        ),
    )
    assert result["status"] == "needs_review"
    assert result["matchedCount"] == 1
    assert result["unmatchedCount"] == 1
    assert result["coverageRatio"] == Decimal("0.5000")
    assert result["issues"][0]["issueCode"] == "chart_not_found"
    assert get_complete_score_import(session, result["id"]) == result


def test_duplicate_chart_keeps_highest_achievement(session: Session) -> None:
    result = import_complete_scores(
        session,
        payload(
            [
                {
                    "title": "Test Song",
                    "chartType": "dx",
                    "difficulty": "master",
                    "achievement": achievement,
                }
                for achievement in ("99.0000", "100.5000")
            ]
        ),
    )
    assert result["matchedCount"] == 1
    assert result["duplicateCount"] == 1
    scores = session.query(PlayerScore).order_by(PlayerScore.source_index).all()
    assert scores[0].match_status == "duplicate_ignored"
    assert scores[1].match_status == "matched"


def test_import_safely_corrects_wrong_chart_type(session: Session) -> None:
    result = import_complete_scores(
        session,
        payload(
            [
                {
                    "title": "Test Song",
                    "chartType": "std",
                    "difficulty": "master",
                    "achievement": "100.0000",
                }
            ]
        ),
    )
    score = session.scalar(
        select(PlayerScore).where(PlayerScore.snapshot_id == result["id"])
    )
    assert result["matchedCount"] == 1
    assert result["coverageRatio"] == Decimal("1.0000")
    assert score is not None
    assert score.chart_id == "chart"
    assert score.chart_type == "dx"
    assert score.match_status == "matched_type_corrected"


def test_schema_rejects_wrong_region_and_over_precise_achievement() -> None:
    with pytest.raises(ValidationError):
        payload(
            [
                {
                    "title": "Test Song",
                    "chartType": "dx",
                    "difficulty": "master",
                    "achievement": "100.12345",
                }
            ]
        )
