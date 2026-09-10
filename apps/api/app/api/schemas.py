from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RatingRequest(BaseModel):
    chart_constant: Decimal = Field(gt=0, le=15, alias="chartConstant")
    achievement: Decimal = Field(ge=0, le=101)
    full_combo: str | None = Field(default=None, alias="fullCombo")


class RatingResponse(BaseModel):
    rating: int
    coefficient: Decimal
    achievement_used: Decimal = Field(alias="achievementUsed")


class B50InspectionResponse(BaseModel):
    status: str
    fingerprint: str
    format: str
    width: int
    height: int
    byte_size: int = Field(alias="byteSize")
    source_image_stored: bool = Field(alias="sourceImageStored")
    next_step: str = Field(alias="nextStep")
    import_id: str | None = Field(default=None, alias="importId")
    review_url: str | None = Field(default=None, alias="reviewUrl")
    recognized_count: int = Field(default=0, alias="recognizedCount")
    auto_matched_count: int = Field(default=0, alias="autoMatchedCount")


class ImportEntryUpdate(BaseModel):
    chart_id: str = Field(alias="chartId")
    chart_constant: Decimal | None = Field(default=None, gt=0, le=15, alias="chartConstant")
    achievement: Decimal = Field(ge=0, le=101)
    full_combo: str | None = Field(default=None, alias="fullCombo")
    displayed_rating: int | None = Field(default=None, ge=0, alias="displayedRating")

    model_config = ConfigDict(populate_by_name=True)


class ImportEntryResponse(BaseModel):
    slot: int
    bucket: str
    chart_id: str | None = Field(alias="chartId")
    title: str | None
    chart_type: str | None = Field(alias="chartType")
    difficulty: str | None
    chart_version: str | None = Field(alias="chartVersion")
    chart_constant: Decimal | None = Field(alias="chartConstant")
    achievement: Decimal | None
    full_combo: str | None = Field(alias="fullCombo")
    displayed_rating: int | None = Field(alias="displayedRating")
    calculated_rating: int | None = Field(alias="calculatedRating")
    needs_review: bool = Field(alias="needsReview")
    issue_code: str | None = Field(alias="issueCode")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PlayerImportResponse(BaseModel):
    id: str
    status: str
    coverage: str
    catalog_snapshot_id: str = Field(alias="catalogSnapshotId")
    source_image_stored: bool = Field(alias="sourceImageStored")
    image_width: int = Field(alias="imageWidth")
    image_height: int = Field(alias="imageHeight")
    completed_count: int = Field(alias="completedCount")
    total_count: int = Field(alias="totalCount")
    total_rating: int | None = Field(alias="totalRating")
    entries: list[ImportEntryResponse]

    model_config = ConfigDict(populate_by_name=True)


class CompleteScoreEntry(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    chart_type: Literal["std", "dx"] = Field(alias="chartType")
    difficulty: Literal["basic", "advanced", "expert", "master", "remaster"]
    achievement: Decimal = Field(ge=0, le=101, decimal_places=4)
    full_combo: Literal["FC", "FC+", "AP", "AP+"] | None = Field(
        default=None, alias="fullCombo"
    )
    sync_status: str | None = Field(default=None, max_length=20, alias="syncStatus")
    dx_score: int | None = Field(default=None, ge=0, alias="dxScore")
    played_at: datetime | None = Field(default=None, alias="playedAt")

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)


class OfficialBest50Entry(CompleteScoreEntry):
    bucket: Literal["b35", "b15"]
    position: int = Field(ge=1, le=35)


class CompleteScoreImportRequest(BaseModel):
    schema_version: Literal[1] = Field(alias="schemaVersion")
    source_region: Literal["international"] = Field(alias="sourceRegion")
    source_name: str = Field(default="maimai DX NET user export", alias="sourceName", max_length=80)
    exported_at: datetime = Field(alias="exportedAt")
    scores: list[CompleteScoreEntry] = Field(min_length=1, max_length=10000)
    official_best50: list[OfficialBest50Entry] | None = Field(
        default=None, alias="officialBest50", max_length=50
    )

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)


class CompleteScoreIssue(BaseModel):
    source_index: int = Field(alias="sourceIndex")
    title: str
    chart_type: str = Field(alias="chartType")
    difficulty: str
    issue_code: str = Field(alias="issueCode")

    model_config = ConfigDict(populate_by_name=True)


class CompleteScorePreview(BaseModel):
    title: str
    chart_type: str = Field(alias="chartType")
    difficulty: str
    achievement: Decimal
    full_combo: str | None = Field(alias="fullCombo")
    match_status: str = Field(alias="matchStatus")

    model_config = ConfigDict(populate_by_name=True)


class CompleteScoreBest50Entry(BaseModel):
    position: int
    bucket: Literal["b35", "b15"]
    title: str
    chart_type: str = Field(alias="chartType")
    difficulty: str
    achievement: Decimal
    rating: int
    constant: Decimal
    full_combo: str | None = Field(alias="fullCombo")
    cover_url: str | None = Field(alias="coverUrl")

    model_config = ConfigDict(populate_by_name=True)


class CompleteScoreImportResponse(BaseModel):
    id: str
    status: str
    supplied_count: int = Field(alias="suppliedCount")
    matched_count: int = Field(alias="matchedCount")
    unmatched_count: int = Field(alias="unmatchedCount")
    duplicate_count: int = Field(alias="duplicateCount")
    coverage_ratio: Decimal = Field(alias="coverageRatio")
    corrected_type_count: int = Field(alias="correctedTypeCount")
    chart_type_counts: dict[str, int] = Field(alias="chartTypeCounts")
    difficulty_counts: dict[str, int] = Field(alias="difficultyCounts")
    sample_scores: list[CompleteScorePreview] = Field(alias="sampleScores")
    b50_generated: bool = Field(alias="b50Generated")
    b35_count: int = Field(alias="b35Count")
    b15_count: int = Field(alias="b15Count")
    b35_rating: int | None = Field(alias="b35Rating")
    b15_rating: int | None = Field(alias="b15Rating")
    total_rating: int | None = Field(alias="totalRating")
    recommendation_url: str | None = Field(alias="recommendationUrl")
    b50_source: str | None = Field(alias="b50Source")
    best50_entries: list[CompleteScoreBest50Entry] = Field(alias="best50Entries")
    issues: list[CompleteScoreIssue]

    model_config = ConfigDict(populate_by_name=True)
