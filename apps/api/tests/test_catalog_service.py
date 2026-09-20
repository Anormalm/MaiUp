from decimal import Decimal

from app.catalog.schemas import Sheet
from app.catalog.service import (
    DXRATING_SOURCE_ID,
    LOCAL_OVERRIDE_SOURCE_ID,
    MAITOOLS_SOURCE_ID,
    _build_version_constant_index,
    _catalog_content_hash,
    _load_intl_overrides,
    _resolve_intl_constant,
)


def test_international_overrides_are_version_scoped(tmp_path) -> None:
    overrides_path = tmp_path / "international_chart_constants.json"
    overrides_path.write_text(
        """
        {
          "schemaVersion": 1,
          "overrides": [
            {
              "chartId": "chart-1",
              "gameVersion": "CiRCLE PLUS",
              "constant": 14.1
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    assert _load_intl_overrides(overrides_path) == {("chart-1", "CiRCLE PLUS"): Decimal("14.1")}


def test_catalog_hash_changes_when_international_overrides_change() -> None:
    raw_bytes = b'{"schemaVersion":1}'
    version_payload = [{"name": "Song", "dx": 1, "lv": [3, 7, 10, 13.2]}]
    original = _catalog_content_hash(raw_bytes, {}, version_payload, "CiRCLE PLUS")
    corrected = _catalog_content_hash(
        raw_bytes,
        {("chart-1", "CiRCLE PLUS"): Decimal("14.1")},
        version_payload,
        "CiRCLE PLUS",
    )

    assert corrected != original


def test_catalog_hash_changes_when_version_snapshot_changes() -> None:
    raw_bytes = b'{"schemaVersion":1}'
    original = _catalog_content_hash(
        raw_bytes,
        {},
        [{"name": "Song", "dx": 1, "lv": [3, 7, 10, 13.2]}],
        "CiRCLE PLUS",
    )
    corrected = _catalog_content_hash(
        raw_bytes,
        {},
        [{"name": "Song", "dx": 1, "lv": [3, 7, 10, 13.3]}],
        "CiRCLE PLUS",
    )

    assert corrected != original


def test_sheet_exposes_international_display_level_override() -> None:
    sheet = Sheet.model_validate(
        {
            "id": "chart-1",
            "type": "dx",
            "difficulty": "master",
            "level": "14+",
            "internalLevelValue": 14.6,
            "serverIds": ["jp", "intl"],
            "serverOverrides": {"intl": {"level": "14", "levelValue": 14.0}},
            "version": "CiRCLE",
        }
    )

    assert sheet.level_for("intl") == "14"


def test_version_snapshot_uses_positive_intl_values_and_ignores_estimates() -> None:
    index, debut_index, ambiguous = _build_version_constant_index(
        [
            {
                "name": "奇々解体",
                "debut": 26,
                "dx": 1,
                "lv": [-3, -6, -9.7, 13.4],
                "regionOverrides": {"intl": {"lv": [3, 6.5, 9.7, 13.2, 0]}},
            },
            {
                "name": "No regional override",
                "debut": 21,
                "dx": 1,
                "lv": [3, 7, 10, 13.4],
                "regionOverrides": {"intl": {"lv": [0, 0, 0, 0, 0]}},
            },
            {"name": "Estimate only", "debut": 1, "dx": 0, "lv": [-3, -7, -10, -13]},
        ]
    )

    assert index[("奇々解体", "dx", "master")] == Decimal("13.2")
    assert ("奇々解体", "dx", "remaster") not in index
    assert index[("no regional override", "dx", "master")] == Decimal("13.4")
    assert debut_index[("奇々解体", "dx", "master", 26)] == Decimal("13.2")
    assert not any(key[0] == "estimate only" for key in index)
    assert ambiguous == set()


def test_version_snapshot_skips_conflicting_duplicate_keys() -> None:
    index, debut_index, ambiguous = _build_version_constant_index(
        [
            {"name": "Same", "debut": 1, "dx": 1, "lv": [3, 7, 10, 13.2]},
            {"name": "Same", "debut": 1, "dx": 1, "lv": [3, 7, 10, 13.3]},
        ]
    )

    assert ("same", "dx", "master") not in index
    assert ("same", "dx", "master", 1) not in debut_index
    assert ("same", "dx", "master") in ambiguous


def test_version_snapshot_separates_same_title_by_debut_version() -> None:
    index, debut_index, ambiguous = _build_version_constant_index(
        [
            {"name": "Link", "debut": 1, "dx": 0, "lv": [6, 7.8, 12.6, 12.5]},
            {"name": "Link", "debut": 4, "dx": 0, "lv": [6, 8.2, 10.7, 12.5]},
        ]
    )

    assert ("link", "std", "expert") not in index
    assert debut_index[("link", "std", "expert", 1)] == Decimal("12.6")
    assert debut_index[("link", "std", "expert", 4)] == Decimal("10.7")
    assert ambiguous == {("link", "std", "advanced"), ("link", "std", "expert")}


def test_manual_constant_precedes_version_snapshot_then_base_fallback() -> None:
    sheet = Sheet.model_validate(
        {
            "id": "chart-1",
            "type": "dx",
            "difficulty": "master",
            "level": "14+",
            "internalLevelValue": 14.6,
            "serverIds": ["jp", "intl"],
            "serverOverrides": {"intl": {"level": "14", "levelValue": 14.0}},
            "version": "CiRCLE",
        }
    )

    assert _resolve_intl_constant(sheet, "CiRCLE", {}, Decimal("14.2")) == (
        Decimal("14.2"),
        "intl",
        Decimal("0.950"),
        "maitools_version_snapshot",
        MAITOOLS_SOURCE_ID,
    )
    assert _resolve_intl_constant(
        sheet,
        "CiRCLE",
        {("chart-1", "CiRCLE"): Decimal("14.1")},
        Decimal("14.2"),
    ) == (
        Decimal("14.1"),
        "intl",
        Decimal("1.000"),
        "validated_intl_override",
        LOCAL_OVERRIDE_SOURCE_ID,
    )
    assert _resolve_intl_constant(sheet, "CiRCLE", {}, None) == (
        Decimal("14.6"),
        "generic",
        Decimal("0.750"),
        "community_base_fallback",
        DXRATING_SOURCE_ID,
    )
