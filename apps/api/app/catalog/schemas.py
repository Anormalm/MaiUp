from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NoteCounts(BaseModel):
    tap: int = 0
    hold: int = 0
    slide: int = 0
    touch: int = 0
    break_count: int = Field(default=0, alias="break")
    total: int = 0

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class Sheet(BaseModel):
    id: str
    type: str
    difficulty: str
    level: str
    internal_level_value: Decimal = Field(alias="internalLevelValue")
    note_designer: str | None = Field(default=None, alias="noteDesigner")
    note_counts: NoteCounts = Field(default_factory=NoteCounts, alias="noteCounts")
    server_ids: list[str] = Field(default_factory=list, alias="serverIds")
    server_overrides: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        alias="serverOverrides",
    )
    is_special: bool = Field(default=False, alias="isSpecial")
    version: str
    internal_id: int | None = Field(default=None, alias="internalId")
    release_date: date | None = Field(default=None, alias="releaseDate")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    def version_for(self, region: str) -> str:
        override = self.server_overrides.get(region, {})
        return str(override.get("version") or self.version)

    def level_for(self, region: str) -> str:
        override = self.server_overrides.get(region, {})
        return str(override.get("level") or self.level)

    def internal_level_value_for(self, region: str) -> Decimal:
        override = self.server_overrides.get(region, {})
        value = override.get("levelValue", override.get("internalLevelValue"))
        return self.internal_level_value if value is None else Decimal(str(value))

    def has_internal_level_override(self, region: str) -> bool:
        override = self.server_overrides.get(region, {})
        return "levelValue" in override or "internalLevelValue" in override


class Song(BaseModel):
    id: str
    category: str
    title: str
    artist: str
    bpm: Decimal | None = None
    version: str
    is_locked: bool = Field(default=False, alias="isLocked")
    sheets: list[Sheet] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class Version(BaseModel):
    version: str
    abbr: str
    release_date: date = Field(alias="releaseDate")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class Alias(BaseModel):
    song_id: str
    name: str


class Tag(BaseModel):
    id: int
    group_id: int
    localized_name: dict[str, str]


class TagSong(BaseModel):
    song_id: str
    sheet_id: str
    tag_id: int


class RawCatalog(BaseModel):
    schema_version: int = Field(alias="schemaVersion")
    updated_at: str = Field(alias="updatedAt")
    songs: list[Song]
    versions: list[Version]
    aliases: list[Alias] = Field(default_factory=list)
    tags: list[Tag] = Field(default_factory=list)
    tag_songs: list[TagSong] = Field(default_factory=list, alias="tagSongs")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class CatalogValidation(BaseModel):
    passed: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    total_songs: int
    international_songs: int
    international_charts: int
    current_version: str
    b15_versions: list[str]


class IngestResult(BaseModel):
    snapshot_id: str
    status: str
    content_hash: str
    song_count: int
    chart_count: int
    validation: CatalogValidation
    reused_existing_snapshot: bool = False
