import base64
import os
from pathlib import Path

import pytest

from image_utils import ImageInput, resolve_image

IMGS_DIR = Path(__file__).parent / "imgs"

TEST_CASES = [
    ("chart.png", "image/png"),
    ("form.jpg", "image/jpeg"),
    ("qa.jpg", "image/jpeg"),
    ("text.png", "image/png"),
    ("translate.png", "image/png"),
    ("what.png", "image/png"),
]


class TestRealImages:
    @pytest.mark.parametrize("filename,expected_mime", TEST_CASES)
    def test_resolve(self, filename, expected_mime):
        path = str(IMGS_DIR / filename)
        result = resolve_image(path)
        assert isinstance(result, ImageInput)
        assert result.mime_type == expected_mime
        assert result.data_uri.startswith(f"data:{expected_mime};base64,")
        assert len(result.sha256) == 64
        assert result.source == path

    @pytest.mark.parametrize("filename,expected_mime", TEST_CASES)
    def test_data_uri_decodable(self, filename, expected_mime):
        path = str(IMGS_DIR / filename)
        result = resolve_image(path)
        payload = result.data_uri.split(",", 1)[1]
        decoded = base64.b64decode(payload)
        assert len(decoded) > 0
        assert decoded.startswith(_mime_to_magic(expected_mime))

    @pytest.mark.parametrize("filename,_", TEST_CASES)
    def test_files_exist(self, filename, _):
        assert (IMGS_DIR / filename).is_file()

    @pytest.mark.parametrize("filename,_", TEST_CASES)
    def test_sha256_unique(self, filename, _):
        path = str(IMGS_DIR / filename)
        result = resolve_image(path)
        hex_chars = set("0123456789abcdef")
        assert all(c in hex_chars for c in result.sha256)


def _mime_to_magic(mime: str) -> bytes:
    if mime == "image/png":
        return b"\x89PNG"
    if mime == "image/jpeg":
        return b"\xff\xd8\xff"
    return b""