from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path

from PIL import Image
from rapidfuzz import fuzz, process
from rapidocr import RapidOCR
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.catalog.versioning import VersionPolicy
from app.db.models import (
    CatalogSnapshot,
    Chart,
    ChartConstant,
    ChartRevision,
    GameVersion,
    ImportEntry,
    PlayerImport,
    Song,
    SongAlias,
)
from app.rating.calculator import calculate_chart_rating

ACHIEVEMENT_RE = re.compile(r"(?<!\d)(\d{2,3})\s*[.,]\s*(\d{3,4})\s*%?")
CARD_RATING_RE = re.compile(
    r"(?<!\d)(\d{1,2})\s*[.,]\s*(\d)\s*(?:→|->|—>|>|-)\s*(\d{2,3})(?!\d)"
)
RANK_RE = re.compile(r"(?<![A-Z])(SSS\+?|SS\+?|S\+?|AAA|AA|A)(?![A-Z])", re.IGNORECASE)
OCR_RESULT_VERSION = 3


@dataclass(frozen=True)
class OCRLine:
    text: str
    score: float
    left: float
    top: float
    right: float
    bottom: float

    @property
    def x(self) -> float:
        return (self.left + self.right) / 2

    @property
    def y(self) -> float:
        return (self.top + self.bottom) / 2


@lru_cache(maxsize=1)
def _engine() -> RapidOCR:
    return RapidOCR()


def normalize_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def parse_achievement(text: str) -> Decimal | None:
    match = ACHIEVEMENT_RE.search(text.replace("O", "0").replace("o", "0"))
    if match is None:
        return None
    fraction = match.group(2).ljust(4, "0")[:4]
    try:
        value = Decimal(f"{match.group(1)}.{fraction}")
    except InvalidOperation:
        return None
    return value if Decimal("0") <= value <= Decimal("101") else None


def parse_card_rating(text: str) -> tuple[Decimal, int] | None:
    match = CARD_RATING_RE.search(text.replace("O", "0").replace("o", "0"))
    if match is None:
        return None
    constant = Decimal(f"{match.group(1)}.{match.group(2)}")
    rating = int(match.group(3))
    if not Decimal("1") <= constant <= Decimal("15"):
        return None
    return constant, rating


def parse_rank(text: str) -> str | None:
    match = RANK_RE.search(text.upper())
    return match.group(1).upper() if match else None


def ocr_result_is_current(path: Path) -> bool:
    result_path = path.parent / "ocr.json"
    if not result_path.exists():
        return False
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return result.get("version") == OCR_RESULT_VERSION


def _read_lines(path: Path) -> list[OCRLine]:
    result = _engine()(path)
    if result.boxes is None or result.txts is None or result.scores is None:
        return []
    lines: list[OCRLine] = []
    for box, value, score in zip(result.boxes, result.txts, result.scores, strict=True):
        xs = [float(point[0]) for point in box]
        ys = [float(point[1]) for point in box]
        lines.append(
            OCRLine(str(value), float(score), min(xs), min(ys), max(xs), max(ys))
        )
    return lines


def _catalog_rows(session: Session, player_import: PlayerImport) -> list[dict[str, object]]:
    snapshot = session.get(CatalogSnapshot, player_import.catalog_snapshot_id)
    if snapshot is None:
        return []
    versions = tuple(session.scalars(select(GameVersion.name).order_by(GameVersion.ordinal)).all())
    policy = VersionPolicy(
        versions,
        str(json.loads(snapshot.validation_report)["current_version"]),
        b15_version_count=2,
    )
    aliases: dict[str, list[str]] = {}
    for song_id, alias in session.execute(select(SongAlias.song_id, SongAlias.name)).all():
        aliases.setdefault(song_id, []).append(alias)
    rows = session.execute(
        select(Chart, Song, ChartRevision, ChartConstant)
        .join(Song, Song.id == Chart.song_id)
        .join(
            ChartRevision,
            (ChartRevision.chart_id == Chart.id)
            & (ChartRevision.snapshot_id == player_import.catalog_snapshot_id),
        )
        .join(
            ChartConstant,
            (ChartConstant.chart_id == Chart.id)
            & (ChartConstant.snapshot_id == player_import.catalog_snapshot_id),
        )
        .where(ChartRevision.is_special.is_(False))
    ).all()
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for chart, song, revision, constant in rows:
        if chart.id in seen:
            continue
        seen.add(chart.id)
        bucket = policy.bucket_for(revision.intl_version)
        if bucket is not None:
            result.append(
                {
                    "chart": chart,
                    "song": song,
                    "revision": revision,
                    "constant": constant,
                    "bucket": bucket,
                    "names": [song.title, *aliases.get(song.id, [])],
                }
            )
    return result


def _card_anchors(
    lines: list[OCRLine],
    width: float,
    height: float,
) -> list[tuple[int, OCRLine, Decimal]]:
    candidates = [
        (line, achievement)
        for line in lines
        if "avgachievement" not in normalize_title(line.text)
        and (achievement := parse_achievement(line.text)) is not None
    ]
    candidates.sort(key=lambda item: item[0].y)
    row_tolerance = max(height * 0.012, 1)
    rows: list[list[tuple[OCRLine, Decimal]]] = []
    for item in candidates:
        if not rows:
            rows.append([item])
            continue
        row_y = sum(existing[0].y for existing in rows[-1]) / len(rows[-1])
        if abs(item[0].y - row_y) <= row_tolerance:
            rows[-1].append(item)
        else:
            rows.append([item])

    anchors: list[tuple[int, OCRLine, Decimal]] = []
    for row_index, row in enumerate(rows[:10]):
        by_column: dict[int, tuple[OCRLine, Decimal]] = {}
        for line, achievement in row:
            column = min(4, max(0, int(line.x * 5 / width)))
            existing = by_column.get(column)
            if existing is None or line.score > existing[0].score:
                by_column[column] = (line, achievement)
        for column, (line, achievement) in sorted(by_column.items()):
            anchors.append((row_index * 5 + column + 1, line, achievement))
    return anchors


def _field_lines(
    lines: list[OCRLine],
    anchor: OCRLine,
    width: float,
    height: float,
    *,
    top_offset: float,
    bottom_offset: float,
) -> list[OCRLine]:
    return [
        line
        for line in lines
        if abs(line.x - anchor.x) <= width * 0.075
        and height * top_offset <= line.y - anchor.y <= height * bottom_offset
    ]


def _detect_full_combo(image: Image.Image, slot: int, anchor: OCRLine) -> str | None:
    column = (slot - 1) % 5
    width, height = image.size
    card_left = width * (0.036 + 0.187 * column)
    crop = image.crop(
        (
            int(card_left + width * 0.003),
            int(anchor.y + height * 0.016),
            int(card_left + width * 0.044),
            int(anchor.y + height * 0.040),
        )
    ).convert("RGB")
    pixels = list(crop.get_flattened_data())
    if not pixels:
        return False
    green_pixels = sum(
        green > 95
        and green > red * 1.12
        and green > blue * 1.05
        and max(red, green, blue) - min(red, green, blue) > 35
        for red, green, blue in pixels
    )
    if green_pixels / len(pixels) < 0.06:
        return None

    plus_patch = crop.crop(
        (
            int(crop.width * 0.54),
            int(crop.height * 0.32),
            int(crop.width * 0.71),
            int(crop.height * 0.55),
        )
    )
    plus_pixels = list(plus_patch.get_flattened_data())
    dark_pixels = sum(
        red < 100 and green < 160 and blue < 120 for red, green, blue in plus_pixels
    )
    return "FC+" if plus_pixels and dark_pixels / len(plus_pixels) >= 0.06 else "FC"


def _candidate_song_scores(
    title_lines: list[OCRLine],
    choices: dict[str, str],
) -> tuple[dict[str, float], dict[str, str]]:
    song_scores: dict[str, float] = {}
    ocr_titles: dict[str, str] = {}
    for candidate in title_lines:
        candidate_text = ACHIEVEMENT_RE.sub("", candidate.text).strip()
        normalized = normalize_title(candidate_text)
        if len(normalized) < 2:
            continue
        results = process.extract(
            normalized,
            choices,
            scorer=fuzz.WRatio,
            score_cutoff=58,
            limit=30,
        )
        for _, score, key in results:
            song_id, matched_name = str(key).split(":", 1)
            adjusted_score = float(score)
            if len(matched_name) < len(normalized):
                adjusted_score *= len(matched_name) / len(normalized)
            weighted = adjusted_score * candidate.score
            if weighted > song_scores.get(song_id, 0):
                song_scores[song_id] = weighted
                ocr_titles[song_id] = candidate_text
    return song_scores, ocr_titles


def recognize_import(session: Session, import_id: str, path: Path) -> dict[str, int]:
    player_import = session.get(PlayerImport, import_id)
    if player_import is None:
        return {"recognized": 0, "matched": 0}
    lines = _read_lines(path)
    catalog = _catalog_rows(session, player_import)
    choices: dict[str, str] = {}
    rows_by_song: dict[str, list[dict[str, object]]] = {}
    for row in catalog:
        song = row["song"]
        assert isinstance(song, Song)
        rows_by_song.setdefault(song.id, []).append(row)
        for name in row["names"]:
            normalized = normalize_title(str(name))
            if len(normalized) >= 2:
                choices[f"{song.id}:{normalized}"] = normalized

    anchors = _card_anchors(lines, player_import.image_width, player_import.image_height)
    image = Image.open(path).convert("RGB")
    session.execute(
        update(ImportEntry)
        .where(ImportEntry.import_id == import_id)
        .values(
            chart_id=None,
            title=None,
            chart_type=None,
            difficulty=None,
            chart_version=None,
            chart_constant=None,
            achievement=None,
            full_combo=None,
            displayed_rating=None,
            calculated_rating=None,
            needs_review=True,
            issue_code="manual_entry_required",
        )
    )
    session.flush()

    matched = 0
    used_charts: set[str] = set()
    debug_items: list[dict[str, object]] = []
    for slot, anchor, achievement in anchors:
        entry = session.get(ImportEntry, (import_id, slot))
        if entry is None:
            continue
        title_lines = _field_lines(
            lines,
            anchor,
            player_import.image_width,
            player_import.image_height,
            top_offset=-0.031,
            bottom_offset=-0.004,
        )
        rating_lines = _field_lines(
            lines,
            anchor,
            player_import.image_width,
            player_import.image_height,
            top_offset=0.016,
            bottom_offset=0.045,
        )
        song_scores, _ = _candidate_song_scores(title_lines, choices)
        best_ocr_title = max(title_lines, key=lambda line: line.score).text if title_lines else None
        parsed_ratings = [
            (line.score, parsed)
            for line in rating_lines
            if (parsed := parse_card_rating(line.text)) is not None
        ]
        parsed_rating = max(parsed_ratings, default=None, key=lambda item: item[0])
        image_constant, displayed_rating = parsed_rating[1] if parsed_rating else (None, None)
        full_combo = _detect_full_combo(image, slot, anchor)

        entry.achievement = achievement
        entry.full_combo = full_combo
        entry.chart_constant = image_constant
        entry.displayed_rating = displayed_rating
        entry.needs_review = True
        entry.issue_code = "ocr_fields_missing"
        entry.title = best_ocr_title
        entry.chart_id = None
        entry.chart_type = None
        entry.difficulty = None
        entry.chart_version = None
        entry.calculated_rating = None
        debug_item: dict[str, object] = {
            "slot": slot,
            "title": best_ocr_title,
            "achievement": str(achievement),
            "rank": parse_rank(anchor.text),
            "constant": str(image_constant) if image_constant is not None else None,
            "displayed_rating": displayed_rating,
            "full_combo": full_combo,
            "matched": False,
        }
        if image_constant is None or displayed_rating is None or not song_scores:
            debug_item["issue"] = entry.issue_code
            debug_items.append(debug_item)
            continue

        calculated_from_image = calculate_chart_rating(
            image_constant,
            achievement,
            full_combo=full_combo,
        )
        entry.calculated_rating = calculated_from_image
        if calculated_from_image != displayed_rating:
            entry.issue_code = "ocr_rating_mismatch"
            debug_item["issue"] = entry.issue_code
            debug_items.append(debug_item)
            continue

        viable: list[tuple[float, Decimal, dict[str, object]]] = []
        for song_id, title_score in song_scores.items():
            for row in rows_by_song[song_id]:
                if row["bucket"] != entry.bucket:
                    continue
                constant = row["constant"]
                chart = row["chart"]
                assert isinstance(constant, ChartConstant)
                assert isinstance(chart, Chart)
                if chart.id in used_charts:
                    continue
                constant_delta = abs(constant.constant_value - image_constant)
                if constant_delta > Decimal("0.4"):
                    continue
                constant_bonus = max(0.0, 12.0 - float(constant_delta) * 30.0)
                viable.append((title_score + constant_bonus, constant_delta, row))
        viable.sort(key=lambda item: (-item[0], item[1]))
        best = viable[0] if viable else None
        runner_up = viable[1] if len(viable) > 1 else None
        unambiguous = bool(
            best
            and best[0] >= 60
            and (
                runner_up is None
                or best[0] - runner_up[0] >= 5
                or (
                    best[2]["song"].id == runner_up[2]["song"].id
                    and best[1] < runner_up[1]
                )
            )
        )
        if not unambiguous or best is None:
            entry.issue_code = "ocr_chart_uncertain"
            debug_item["issue"] = entry.issue_code
            debug_items.append(debug_item)
            continue
        _, _, row = best
        chart = row["chart"]
        revision = row["revision"]
        song = row["song"]
        assert isinstance(chart, Chart)
        assert isinstance(revision, ChartRevision)
        assert isinstance(song, Song)
        entry.chart_id = chart.id
        entry.title = song.title
        entry.chart_type = chart.chart_type
        entry.difficulty = chart.difficulty
        entry.chart_version = revision.intl_version
        entry.chart_constant = image_constant
        entry.displayed_rating = displayed_rating
        entry.calculated_rating = calculated_from_image
        entry.needs_review = False
        entry.issue_code = None
        used_charts.add(chart.id)
        matched += 1
        debug_item.update(
            {
                "matched": True,
                "matched_title": song.title,
                "chart_id": chart.id,
            }
        )
        debug_items.append(debug_item)

    (path.parent / "ocr.json").write_text(
        json.dumps(
            {
                "version": OCR_RESULT_VERSION,
                "recognized": len(anchors),
                "matched": matched,
                "lines": [asdict(line) for line in lines],
                "items": debug_items,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    session.commit()
    return {"recognized": len(anchors), "matched": matched}
