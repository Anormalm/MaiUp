"""Apply reviewed availability corrections without changing community constants."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def apply_availability_overrides(
    payload: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    if manifest.get("schemaVersion") != 1:
        raise ValueError("Unsupported availability override schema")
    result = deepcopy(payload)
    sheets = {sheet["id"]: (song, sheet) for song in result["songs"] for sheet in song["sheets"]}
    applied = []
    for override in manifest.get("overrides", []):
        found = sheets.get(override["chartId"])
        if found is None:
            raise ValueError(f"Availability override chart missing: {override['chartId']}")
        song, sheet = found
        if (song["title"], sheet["type"], sheet["difficulty"], sheet["level"]) != (
            override["title"],
            override["chartType"],
            override["difficulty"],
            override["level"],
        ):
            raise ValueError(f"Availability override identity changed: {override['chartId']}")
        if not override.get("sourceUrl") or not override.get("verifiedAt"):
            raise ValueError(
                "Availability overrides require public evidence and a verification date"
            )
        # Once upstream includes the chart, its region/version data takes precedence.
        if "intl" in sheet.get("serverIds", []):
            continue
        sheet.setdefault("serverIds", []).append("intl")
        sheet.setdefault("serverOverrides", {}).setdefault("intl", {})["version"] = override[
            "intlVersion"
        ]
        applied.append(override)
    if applied:
        # Included in the snapshot hash and archived JSON so corrections are traceable.
        result["maiupAvailabilityOverrides"] = applied
    return result
