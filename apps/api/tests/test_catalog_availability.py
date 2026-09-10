from copy import deepcopy

import pytest

from app.catalog.availability import apply_availability_overrides
from app.catalog.service import canonical_json_bytes


@pytest.fixture
def source_and_manifest():
    payload = {
        "songs": [
            {
                "title": "example",
                "sheets": [
                    {
                        "id": "chart",
                        "type": "dx",
                        "difficulty": "master",
                        "level": "13+",
                        "internalLevelValue": 13.6,
                        "serverIds": ["jp"],
                        "version": "CURRENT",
                    }
                ],
            }
        ]
    }
    manifest = {
        "schemaVersion": 1,
        "overrides": [
            {
                "chartId": "chart",
                "title": "example",
                "chartType": "dx",
                "difficulty": "master",
                "level": "13+",
                "intlVersion": "CURRENT",
                "sourceUrl": "https://example.invalid/music.json",
                "verifiedAt": "2026-09-10",
            }
        ],
    }
    return payload, manifest


def test_correction_is_traceable_preserves_constants_and_leaves_source_untouched(
    source_and_manifest,
):
    source, manifest = source_and_manifest
    original = deepcopy(source)
    corrected = apply_availability_overrides(source, manifest)
    assert source == original
    sheet = corrected["songs"][0]["sheets"][0]
    assert sheet["serverIds"] == ["jp", "intl"]
    assert sheet["internalLevelValue"] == 13.6
    assert sheet["serverOverrides"]["intl"]["version"] == "CURRENT"
    assert corrected["maiupAvailabilityOverrides"] == manifest["overrides"]
    assert canonical_json_bytes(corrected) != canonical_json_bytes(source)
    assert apply_availability_overrides(source, manifest) == corrected
    assert apply_availability_overrides(corrected, manifest) == corrected


def test_upstream_regional_data_takes_precedence(source_and_manifest):
    source, manifest = source_and_manifest
    sheet = source["songs"][0]["sheets"][0]
    sheet["serverIds"].append("intl")
    sheet["serverOverrides"] = {"intl": {"version": "NEXT"}}
    assert apply_availability_overrides(source, manifest) == source


@pytest.mark.parametrize("field", ["title", "chartType", "difficulty", "level", "chartId"])
def test_changed_chart_identity_requires_review(source_and_manifest, field):
    source, manifest = source_and_manifest
    manifest["overrides"][0][field] = "changed"
    with pytest.raises(ValueError, match="override"):
        apply_availability_overrides(source, manifest)


def test_correction_requires_evidence(source_and_manifest):
    source, manifest = source_and_manifest
    manifest["overrides"][0].pop("sourceUrl")
    with pytest.raises(ValueError, match="evidence"):
        apply_availability_overrides(source, manifest)
