from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from app.config import get_settings


def _import_dir(import_id: str) -> Path:
    if not import_id or any(character not in "0123456789abcdef-" for character in import_id):
        raise ValueError("Invalid import id")
    root = get_settings().import_asset_dir.resolve()
    destination = (root / import_id).resolve()
    if root not in destination.parents:
        raise ValueError("Unsafe import asset path")
    return destination


def store_source_image(import_id: str, content: bytes) -> Path:
    """Decode and re-encode locally so metadata and the original filename are discarded."""
    destination = _import_dir(import_id)
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "source.png"
    with Image.open(BytesIO(content)) as source:
        normalized = ImageOps.exif_transpose(source).convert("RGB")
        normalized.save(path, format="PNG", optimize=True)
    return path


def source_image_path(import_id: str) -> Path | None:
    path = _import_dir(import_id) / "source.png"
    return path if path.is_file() else None


def delete_source_image(import_id: str) -> bool:
    directory = _import_dir(import_id)
    removed = False
    for name in ("source.png", "ocr.json"):
        path = directory / name
        if path.is_file():
            path.unlink()
            removed = True
    if directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()
    return removed
