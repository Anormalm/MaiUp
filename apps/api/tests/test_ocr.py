from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.imports.ocr import (
    OCRLine,
    _card_anchors,
    _detect_full_combo,
    normalize_title,
    ocr_result_is_current,
    parse_achievement,
    parse_card_rating,
    parse_rank,
)


def test_parse_achievement_accepts_common_ocr_variants() -> None:
    assert parse_achievement("100.5000%") == Decimal("100.5000")
    assert parse_achievement("Achievement 99,1234") == Decimal("99.1234")
    assert parse_achievement("1O0.2500%") == Decimal("100.2500")
    assert parse_achievement("Rating 312") is None


def test_normalize_title_keeps_multilingual_letters_and_removes_punctuation() -> None:
    assert normalize_title("Ｇｌｏｒｉｏｕｓ Crown！") == "gloriouscrown"
    assert normalize_title("系ぎて") == "系ぎて"


def test_parse_card_fields_from_b50_text() -> None:
    assert parse_card_rating("13.8 → 310") == (Decimal("13.8"), 310)
    assert parse_card_rating("13,5 -> 303") == (Decimal("13.5"), 303)
    assert parse_rank("100.7553% SSS+") == "SSS+"


def test_card_anchors_exclude_summary_and_keep_template_slots() -> None:
    lines = [
        OCRLine("AVG ACHIEVEMENT: 100.5146%", 1, 50, 100, 300, 120),
        OCRLine("100.7553% SSS+", 1, 100, 400, 270, 430),
        OCRLine("100.6760% SSS+", 1, 340, 400, 510, 430),
        OCRLine("100.5327% SSS+", 1, 100, 520, 270, 550),
    ]
    anchors = _card_anchors(lines, width=1280, height=1824)
    assert [(slot, achievement) for slot, _, achievement in anchors] == [
        (1, Decimal("100.7553")),
        (2, Decimal("100.6760")),
        (6, Decimal("100.5327")),
    ]


def test_green_fc_detection_distinguishes_fc_plus_and_ignores_gray_badge() -> None:
    image = Image.new("RGB", (1280, 1824), "white")
    anchor = OCRLine("100.7553% SSS+", 1, 120, 430, 274, 457)
    assert _detect_full_combo(image, 1, anchor) is None
    for x in range(50, 100):
        for y in range(470, 520):
            image.putpixel((x, y), (30, 210, 90))
    assert _detect_full_combo(image, 1, anchor) == "FC"
    for x in range(78, 87):
        for y in range(483, 493):
            image.putpixel((x, y), (20, 60, 20))
    assert _detect_full_combo(image, 1, anchor) == "FC+"


def test_ocr_result_version_rejects_stale_draft() -> None:
    image_path = Path("source.png")
    with (
        patch.object(Path, "exists", return_value=True),
        patch.object(Path, "read_text", return_value='{"version": 1}') as read_result,
    ):
        assert not ocr_result_is_current(image_path)
        read_result.return_value = '{"version": 3}'
        assert ocr_result_is_current(image_path)
