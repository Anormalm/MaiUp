from io import BytesIO

import pytest
from PIL import Image

from app.imports.image_inspection import ImageInspectionError, inspect_b50_image


def image_bytes(format_name: str = "PNG", size: tuple[int, int] = (1200, 800)) -> bytes:
    stream = BytesIO()
    Image.new("RGB", size, "#123456").save(stream, format=format_name)
    return stream.getvalue()


@pytest.mark.parametrize("format_name", ["PNG", "JPEG"])
def test_png_and_jpeg_are_decoded_without_storage(format_name: str) -> None:
    content = image_bytes(format_name)
    result = inspect_b50_image(content)
    assert result.format == format_name.lower()
    assert (result.width, result.height) == (1200, 800)
    assert result.byte_size == len(content)
    assert len(result.fingerprint) == 16


def test_fake_image_is_rejected() -> None:
    with pytest.raises(ImageInspectionError, match="not a valid"):
        inspect_b50_image(b"this is not an image")


def test_excessive_pixel_dimensions_are_rejected_before_full_processing() -> None:
    content = image_bytes(size=(6000, 5000))
    with pytest.raises(ImageInspectionError, match="dimensions"):
        inspect_b50_image(content)
