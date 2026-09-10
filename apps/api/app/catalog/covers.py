from __future__ import annotations

import json
import re

from app.config import get_settings
from app.db.models import CatalogSnapshot

COVER_BASE_URL = "https://dp4p6x0xfi5o9.cloudfront.net/maimai/img/cover"
COVER_NAME_PATTERN = re.compile(r"^[0-9a-f]{64}(?:\.png)?$")


def cover_urls_for_snapshot(snapshot: CatalogSnapshot) -> dict[str, str]:
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
