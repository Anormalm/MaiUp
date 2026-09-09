from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RatingRequest(BaseModel):
    chart_constant: Decimal = Field(gt=0, le=15, alias="chartConstant")
    achievement: Decimal = Field(ge=0, le=101)
    full_combo: str | None = Field(default=None, alias="fullCombo")


class MaiToolsImportRequest(BaseModel):
    source_origin: Literal["https://maimaidx-eng.com"] = Field(alias="sourceOrigin")
    score_text: str = Field(min_length=1, max_length=2_000_000, alias="scoreText")

    model_config = ConfigDict(extra="forbid")


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


class ScoreExportResponse(PlayerImportResponse):
    source_origin: str = Field(alias="sourceOrigin")
    scores: list[dict[str, object]]
    issues: list[dict[str, object]]
