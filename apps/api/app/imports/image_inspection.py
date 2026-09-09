from __future__ import annotations

import hashlib
import warnings
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
ALLOWED_FORMATS = {"JPEG", "PNG"}


class ImageInspectionError(ValueError):
    pass


@dataclass(frozen=True)
class InspectedImage:
    fingerprint: str
    format: str
    width: int
    height: int
    byte_size: int


def inspect_b50_image(content: bytes) -> InspectedImage:
    if not content:
        raise ImageInspectionError("Image is empty")
    if len(content) > MAX_IMAGE_BYTES:
        raise ImageInspectionError("Image exceeds the 15 MB limit")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as candidate:
                image_format = candidate.format
                width, height = candidate.size
                if image_format not in ALLOWED_FORMATS:
                    raise ImageInspectionError("Only PNG and JPEG images are accepted")
                if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                    raise ImageInspectionError("Image pixel dimensions are not allowed")
                candidate.verify()
            with Image.open(BytesIO(content)) as decoded:
                decoded.load()
    except ImageInspectionError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ImageInspectionError("Image has unsafe pixel dimensions") from error
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise ImageInspectionError("File is not a valid PNG or JPEG image") from error

    return InspectedImage(
        fingerprint=hashlib.sha256(content).hexdigest()[:16],
        format=image_format.lower(),
        width=width,
        height=height,
        byte_size=len(content),
    )
