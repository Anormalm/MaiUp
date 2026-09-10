import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_import_service import session as session

from app.api.schemas import ImportEntryUpdate, ScoreExportResponse
from app.db.models import (
    CatalogSnapshot,
    Chart,
    ChartConstant,
    ChartRevision,
    PlayerImport,
    ScoreExport,
    Song,
    SongAlias,
)
from app.db.session import get_db
from app.imports.mai_tools import create_score_export, get_score_export, parse_export
from app.imports.service import PlayerImportError, confirm_import, update_entry
from app.main import app
from app.rating.calculator import calculate_chart_rating
from app.recommendations.service import RecommendationError, build_recommendations

HEADER = "Song\tChart\tDifficulty\tAchv\tFC/AP"
TABLE = HEADER + "\nold-chart\tDX\tMASTER\t100.5000%\tAP+"


@pytest.mark.parametrize(
    "header",
    [
        HEADER,
        "歌曲\t譜面\t難度\t達成率\tFC/AP",
        "노래\t유형\t난이도\t정확도\tFC/AP",
    ],
)
def test_localized_headers_bom_and_crlf(header):
    records = parse_export("\ufeff" + header + "\r\nold-chart\tDX\tRe:MASTER\t99.9999%\tFC+\r\n")
    assert records[0]["achievement"] == "99.9999"
    assert records[0]["difficulty"] == "remaster"
    assert records[0]["fullCombo"] == "FC+"


def test_reordered_optional_columns_are_preserved():
    table = (
        "DX Score\tFC/AP\tAchv\tDifficulty\tChart\tSong\tSync\tDX %\tDX ✦\n"
        '1234/1500\t-\t99.5000%\tBASIC\tSTD\tQuoted "song"\tFS+\t82.3%\t0'
    )
    record = parse_export(table)[0]
    assert record["title"] == 'Quoted "song"'
    assert record["dxScore"] == "1234/1500"
    assert record["sync"] == "FS+"
    assert record["chartType"] == "std"
    assert record["fullCombo"] is None


@pytest.mark.parametrize(
    "text",
    [
        "",
        HEADER,
        TABLE.replace("100.5000%", "NaN%"),
        TABLE.replace("100.5000%", "Infinity%"),
        TABLE.replace("100.5000%", "101.0001%"),
        TABLE.replace("100.5000%", "-1%"),
        TABLE.replace("100.5000%", "99.99999%"),
        TABLE.replace("100.5000%", "100.5"),
        TABLE.replace("AP+", "unknown"),
        TABLE.replace("DX", "UTAGE"),
        TABLE.replace("MASTER", "MASTR"),
        TABLE + "\tunexpected",
        TABLE + "\nold-chart\tDX\tMASTER\t99.0000%\t-",
        "Song\tChart\tDifficulty\tAchv\nold-chart\tDX\tMASTER\t100.5%",
        "Cookie\t" + TABLE,
        "Song\t" + HEADER + "\nx\told-chart\tDX\tMASTER\t100%\t-",
    ],
)
def test_malformed_exports_are_rejected(text):
    with pytest.raises(PlayerImportError):
        parse_export(text)


def test_export_size_and_row_limits():
    with pytest.raises(PlayerImportError, match="2 MB"):
        parse_export("あ" * 700_000)
    with pytest.raises(PlayerImportError, match="10,000"):
        parse_export(HEADER + "\n" + "x\n" * 10_001)


@pytest.mark.parametrize("title", ["", "\u3000", " "])
def test_blank_song_names_match_the_catalog_and_preserve_export(session, title):
    session.get(Song, "song-old-chart").title = "\u3000"
    session.commit()
    result = create_score_export(session, TABLE.replace("old-chart", title))
    assert result["issues"] == []
    assert result["scores"][0]["title"] == title
    assert result["scores"][0]["chartId"] == "old-chart"
    assert result["totalCount"] == 1
    assert confirm_import(session, result["id"])["status"] == "confirmed"


def test_blank_song_without_catalog_match_is_retained_for_review(session):
    result = create_score_export(session, TABLE.replace("old-chart", ""))
    assert result["scores"][0]["title"] == ""
    assert result["issues"] == [{"row": 2, "title": "", "code": "chart_not_found"}]
    with pytest.raises(PlayerImportError, match="unmatched"):
        confirm_import(session, result["id"])


@pytest.mark.parametrize(
    ("original", "replacement", "message"),
    [("DX", "UTAGE", "invalid Chart 'UTAGE'"), ("MASTER", "MASTR", "invalid Difficulty 'MASTR'")],
)
def test_invalid_chart_fields_identify_the_field_and_value(original, replacement, message):
    with pytest.raises(PlayerImportError, match=f"Row 2: {message}"):
        parse_export(TABLE.replace(original, replacement))


def test_snapshot_preserves_scores_uses_catalog_and_requires_confirmation(session):
    text = TABLE.replace("FC/AP", "FC/AP\tChart Constant\tVersion") + "\t1.0\tFAKE"
    result = create_score_export(session, text)
    assert result["status"] == "needs_review"
    assert result["coverage"] == "exported_scores"
    assert result["totalCount"] == 1
    assert result["totalRating"] == calculate_chart_rating("14", "100.5", full_combo="AP+")
    assert result["entries"][0].displayed_rating is None
    assert result["scores"][0]["exportedConstant"] == "1.0"
    assert result["scores"][0]["catalogConstant"] == "14.0"
    assert result["scores"][0]["catalogVersion"] == "OLD"
    assert result["sourceImageStored"] is False
    ScoreExportResponse.model_validate(result)
    confirmed = confirm_import(session, result["id"])
    assert confirmed["status"] == "confirmed"
    with pytest.raises(RecommendationError, match="50 calculated ratings"):
        build_recommendations(session, result["id"])
    with pytest.raises(PlayerImportError, match="immutable"):
        update_entry(
            session,
            result["id"],
            1,
            ImportEntryUpdate(
                chartId="old-chart",
                achievement=Decimal("99"),
            ),
        )
    assert get_score_export(session, result["id"])["scores"] == result["scores"]


def test_unmatched_rows_are_kept_and_block_confirmation(session):
    result = create_score_export(session, TABLE + "\nmissing\tDX\tMASTER\t99.0000%\t-")
    assert len(result["scores"]) == 2
    assert result["issues"] == [{"row": 3, "title": "missing", "code": "chart_not_found"}]
    with pytest.raises(PlayerImportError, match="unmatched"):
        confirm_import(session, result["id"])
    with pytest.raises(PlayerImportError, match="Reimport"):
        update_entry(
            session,
            result["id"],
            1,
            ImportEntryUpdate(
                chartId="old-chart",
                achievement=Decimal("99"),
            ),
        )


def test_alias_matching_is_exact_and_duplicate_aliases_reject_atomically(session):
    session.add(SongAlias(song_id="song-old-chart", name="別名", source_id="source"))
    session.commit()
    result = create_score_export(session, TABLE.replace("old-chart", "別名"))
    assert result["scores"][0]["chartId"] == "old-chart"
    before = len(session.scalars(select(PlayerImport)).all())
    with pytest.raises(PlayerImportError, match="duplicate chart after alias"):
        create_score_export(session, TABLE + "\n別名\tDX\tMASTER\t100.5000%\t-")
    assert len(session.scalars(select(PlayerImport)).all()) == before
    assert create_score_export(session, TABLE.replace("old-chart", "old-char"))["issues"]


def test_ambiguous_titles_do_not_choose_first_match(session):
    session.get(Song, "song-new-chart").title = "old-chart"
    session.commit()
    result = create_score_export(session, TABLE)
    assert result["issues"][0]["code"] == "ambiguous_chart"
    assert result["entries"] == []


def test_catalog_required_and_special_charts_block_confirmation(session):
    session.get(ChartRevision, ("snapshot", "old-chart")).is_special = True
    session.commit()
    result = create_score_export(session, TABLE)
    assert result["issues"][0]["code"] == "chart_not_rating_eligible"
    session.get(CatalogSnapshot, "snapshot").status = "rejected"
    session.commit()
    with pytest.raises(PlayerImportError, match="validated International catalog"):
        create_score_export(session, TABLE)


def test_more_than_fifty_scores_are_preserved_and_buckets_rank_independently(session):
    lines = [HEADER]
    for bucket, version, count in (("old", "OLD", 37), ("new", "CURRENT", 17)):
        for index in range(count):
            name = f"{bucket}-{index:02d}"
            session.add(
                Song(
                    id=name,
                    title=name,
                    artist="artist",
                    category="category",
                    source_version=version,
                )
            )
            session.add(Chart(id=name, song_id=name, chart_type="dx", difficulty="master"))
            session.add(
                ChartRevision(
                    snapshot_id="snapshot",
                    chart_id=name,
                    level="14",
                    base_internal_level=Decimal("14"),
                    base_version=version,
                    intl_version=version,
                )
            )
            session.add(
                ChartConstant(
                    snapshot_id="snapshot",
                    chart_id=name,
                    region="generic",
                    source_id="source",
                    game_version=version,
                    constant_value=Decimal("14"),
                    confidence=Decimal(".75"),
                    derivation="community_base_fallback",
                )
            )
            achievement = "50.0000" if index == 0 else "100.5000"
            lines.append(f"{name}\tDX\tMASTER\t{achievement}%\t-")
    session.commit()
    result = create_score_export(session, "\n".join(lines))
    assert len(result["scores"]) == 54
    assert len(json.loads(session.get(ScoreExport, result["id"]).records_json)) == 54
    assert result["totalCount"] == 50
    entries = result["entries"]
    assert sum(entry.bucket == "b35" for entry in entries) == 35
    assert sum(entry.bucket == "b15" for entry in entries) == 15
    assert {entry.chart_id for entry in entries}.isdisjoint({"old-00", "new-00"})
    assert result["totalRating"] == 50 * calculate_chart_rating("14", "100.5")
    assert confirm_import(session, result["id"])["status"] == "confirmed"
    recommendations = build_recommendations(session, result["id"])
    assert recommendations["totalRating"] == result["totalRating"]
    assert recommendations["coverage"] == "best50_only"
    assert recommendations["reviewUrl"] == f"/scores/{result['id']}"


def test_api_contract_and_region_guard(session):
    # Override with a per-request session: the fixture connection belongs to this thread.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    from app.db.base import Base

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            rows = session.execute(select(table)).mappings().all()
            if rows:
                connection.execute(table.insert(), [dict(row) for row in rows])

    def database():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    try:
        with TestClient(app) as client:
            for origin in ("https://maimaidx.jp", "https://example.com", None):
                response = client.post(
                    "/v1/imports/mai-tools",
                    json={
                        "sourceOrigin": origin,
                        "scoreText": TABLE,
                    },
                )
                assert response.status_code == 422
            response = client.post(
                "/v1/imports/mai-tools",
                json={
                    "sourceOrigin": "https://maimaidx-eng.com",
                    "scoreText": TABLE,
                },
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["scores"][0]["achievement"] == "100.5000"
            assert payload["entries"][0]["displayedRating"] is None
            path = f"/v1/imports/{payload['id']}"
            assert client.get(path + "/scores").json() == payload
            assert client.post(path + "/confirm").json()["status"] == "confirmed"
            assert client.get("/v1/imports/missing/scores").status_code == 404
            assert (
                client.post(
                    "/v1/imports/mai-tools",
                    json={
                        "sourceOrigin": "https://maimaidx-eng.com",
                        "scoreText": "bad",
                    },
                ).status_code
                == 400
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
