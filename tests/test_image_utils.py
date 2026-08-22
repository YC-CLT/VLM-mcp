import base64
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from image_utils import (
    ImageInput,
    ImageNotFoundError,
    ImageTooLargeError,
    resolve_image,
)


def _make_test_image() -> bytes:
    from io import BytesIO
    img = Image.new("RGB", (10, 10), color="red")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_resolve_local_path():
    img_bytes = _make_test_image()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(img_bytes)
        tmp_path = f.name
    try:
        result = resolve_image(tmp_path)
        assert isinstance(result, ImageInput)
        assert result.mime_type == "image/png"
        assert result.data_uri.startswith("data:image/png;base64,")
        assert len(result.sha256) == 64
    finally:
        Path(tmp_path).unlink()


def test_resolve_data_uri():
    img_bytes = _make_test_image()
    data_uri = f"data:image/png;base64,{base64.b64encode(img_bytes).decode()}"
    result = resolve_image(data_uri)
    assert isinstance(result, ImageInput)
    assert result.mime_type == "image/png"


def test_resolve_nonexistent_path():
    with pytest.raises(ImageNotFoundError):
        resolve_image("/nonexistent/path/image.png")


def test_resolve_too_large_image():
    import config
    original = config.IMAGE_MAX_SIZE_MB
    config.IMAGE_MAX_SIZE_MB = 0.00001
    try:
        img_bytes = _make_test_image()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(img_bytes)
            tmp_path = f.name
        try:
            with pytest.raises(ImageTooLargeError):
                resolve_image(tmp_path)
        finally:
            Path(tmp_path).unlink()
    finally:
        config.IMAGE_MAX_SIZE_MB = original