from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.schemas import ImportEntryUpdate
from app.db.base import Base
from app.db.models import (
    CatalogSnapshot,
    Chart,
    ChartConstant,
    ChartRevision,
    DataSource,
    GameVersion,
    Song,
)
from app.imports.image_inspection import InspectedImage
from app.imports.service import (
    PlayerImportError,
    confirm_import,
    create_or_reuse_import,
    get_import,
    update_entry,
)
from app.rating.calculator import calculate_chart_rating


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
        db.add_all(
            [
                GameVersion(
                    name="OLD",
                    abbreviation="OLD",
                    release_date=date(2024, 1, 1),
                    ordinal=0,
                ),
                GameVersion(
                    name="PREV",
                    abbreviation="PREV",
                    release_date=date(2025, 1, 1),
                    ordinal=1,
                ),
                GameVersion(
                    name="CURRENT",
                    abbreviation="CURRENT",
                    release_date=date(2026, 1, 1),
                    ordinal=2,
                ),
            ]
        )
        db.add(
            CatalogSnapshot(
                id="snapshot",
                source_id="source",
                schema_version=1,
                source_updated_at="2026-01-01T00:00:00Z",
                content_hash="a" * 64,
                fetched_at=datetime.now(UTC),
                published_at=datetime.now(UTC),
                status="published",
                song_count=2,
                chart_count=2,
                warning_count=0,
                validation_report=(
                    '{"passed":true,"errors":[],"warnings":[],"total_songs":2,'
                    '"international_songs":2,"international_charts":2,'
                    '"current_version":"CURRENT","b15_versions":["PREV","CURRENT"]}'
                ),
            )
        )
        for chart_id, version in (("old-chart", "OLD"), ("new-chart", "CURRENT")):
            song_id = f"song-{chart_id}"
            db.add(
                Song(
                    id=song_id,
                    title=chart_id,
                    artist="artist",
                    category="category",
                    bpm=Decimal("180"),
                    source_version=version,
                    is_locked=False,
                )
            )
            db.add(
                Chart(
                    id=chart_id,
                    song_id=song_id,
                    chart_type="dx",
                    difficulty="master",
                    internal_id=None,
                )
            )
            db.add(
                ChartRevision(
                    snapshot_id="snapshot",
                    chart_id=chart_id,
                    level="14",
                    base_internal_level=Decimal("14.0"),
                    note_designer=None,
                    tap=500,
                    hold=50,
                    slide=50,
                    touch=0,
                    break_count=10,
                    total=610,
                    is_special=False,
                    base_version=version,
                    intl_version=version,
                    release_date=None,
                )
            )
            db.add(
                ChartConstant(
                    snapshot_id="snapshot",
                    chart_id=chart_id,
                    region="generic",
                    source_id="source",
                    game_version=version,
                    constant_value=Decimal("14.0"),
                    confidence=Decimal("0.750"),
                    derivation="community_base_fallback",
                )
            )
        db.commit()
        yield db


def create_import(session: Session):
    result = create_or_reuse_import(
        session,
        InspectedImage(
            fingerprint="0123456789abcdef",
            format="png",
            width=1280,
            height=1824,
            byte_size=1234,
        ),
    )
    assert result is not None
    return result


def test_import_creates_b35_and_b15_slots_and_reuses_open_image(session: Session) -> None:
    created = create_import(session)
    state = get_import(session, created.id)
    assert state is not None
    assert len(state["entries"]) == 50
    assert [entry.bucket for entry in state["entries"][:35]] == ["b35"] * 35
    assert [entry.bucket for entry in state["entries"][35:]] == ["b15"] * 15
    assert create_import(session).id == created.id


def test_entry_rating_must_match_and_chart_must_match_bucket(session: Session) -> None:
    created = create_import(session)
    rating = calculate_chart_rating("14.0", "100.5")
    state = update_entry(
        session,
        created.id,
        1,
        ImportEntryUpdate(
            chartId="old-chart",
            achievement=Decimal("100.5"),
            displayedRating=rating,
        ),
    )
    assert state["completedCount"] == 1
    assert state["totalRating"] == rating

    mismatch = update_entry(
        session,
        created.id,
        1,
        ImportEntryUpdate(
            chartId="old-chart",
            achievement=Decimal("100.5"),
            displayedRating=rating - 1,
        ),
    )
    assert mismatch["completedCount"] == 0
    assert mismatch["entries"][0].issue_code == "rating_mismatch"

    with pytest.raises(PlayerImportError, match="not b35"):
        update_entry(
            session,
            created.id,
            2,
            ImportEntryUpdate(
                chartId="new-chart",
                achievement=Decimal("100.5"),
                displayedRating=rating,
            ),
        )


def test_entry_can_use_constant_read_from_the_image(session: Session) -> None:
    created = create_import(session)
    image_rating = calculate_chart_rating("13.9", "100.5")
    state = update_entry(
        session,
        created.id,
        1,
        ImportEntryUpdate(
            chartId="old-chart",
            chartConstant=Decimal("13.9"),
            achievement=Decimal("100.5"),
            displayedRating=image_rating,
        ),
    )
    assert state["completedCount"] == 1
    assert state["totalRating"] == image_rating
    assert state["entries"][0].chart_constant == Decimal("13.9")


def test_duplicate_chart_and_incomplete_confirmation_are_rejected(session: Session) -> None:
    created = create_import(session)
    rating = calculate_chart_rating("14.0", "100.5")
    payload = ImportEntryUpdate(
        chartId="old-chart",
        achievement=Decimal("100.5"),
        displayedRating=rating,
    )
    update_entry(session, created.id, 1, payload)
    with pytest.raises(PlayerImportError, match="already used"):
        update_entry(session, created.id, 2, payload)
    with pytest.raises(PlayerImportError, match="49 unresolved"):
        confirm_import(session, created.id)
