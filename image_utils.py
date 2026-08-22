import base64
import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import Path

import requests
from PIL import Image

import config


class ImageNotFoundError(Exception):
    pass


class ImageDownloadError(Exception):
    pass


class ImageInvalidFormatError(Exception):
    pass


class ImageTooLargeError(Exception):
    pass


class ImageInvalidBase64Error(Exception):
    pass


@dataclass
class ImageInput:
    source: str
    mime_type: str
    data_uri: str
    sha256: str


def resolve_image(source: str) -> ImageInput:
    if source.startswith("data:image/"):
        return _resolve_data_uri(source)
    if source.startswith("http://") or source.startswith("https://"):
        return _resolve_url(source)
    return _resolve_local_path(source)


def _resolve_local_path(source: str) -> ImageInput:
    path = Path(source).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    if not path.exists():
        return _try_base64_fallback(source)
    return _read_image_bytes(path.read_bytes(), source)


def _resolve_url(source: str) -> ImageInput:
    try:
        resp = requests.get(
            source,
            timeout=config.IMAGE_DOWNLOAD_TIMEOUT,
            headers={"User-Agent": "vlm-mcp/1.0"},
        )
        resp.raise_for_status()
        return _read_image_bytes(resp.content, source)
    except requests.RequestException as e:
        raise ImageDownloadError(f"Failed to download image: {e}") from e


def _resolve_data_uri(source: str) -> ImageInput:
    match = re.match(r"data:(image/\w+);base64,(.+)", source)
    if not match:
        raise ImageInvalidBase64Error("Invalid data URI format")
    mime_type = match.group(1)
    try:
        img_bytes = base64.b64decode(match.group(2))
    except Exception as e:
        raise ImageInvalidBase64Error(f"Invalid base64: {e}") from e
    return _validate_and_build(img_bytes, mime_type, source)


def _try_base64_fallback(source: str) -> ImageInput:
    try:
        img_bytes = base64.b64decode(source)
        return _read_image_bytes(img_bytes, source)
    except Exception as e:
        raise ImageNotFoundError(f"File not found: {source}") from e


def _read_image_bytes(img_bytes: bytes, source: str) -> ImageInput:
    try:
        img = Image.open(io.BytesIO(img_bytes))
        fmt = img.format
        if fmt is None:
            raise ImageInvalidFormatError("Cannot determine image format")
        if fmt.lower() not in (f.lower() for f in config.SUPPORTED_FORMATS):
            raise ImageInvalidFormatError(
                f"Unsupported format: {fmt}. Supported: {config.SUPPORTED_FORMATS}"
            )
        mime_type = f"image/{fmt.lower()}"
    except ImageInvalidFormatError:
        raise
    except Exception as e:
        raise ImageInvalidFormatError(f"Invalid image: {e}") from e
    return _validate_and_build(img_bytes, mime_type, source)


def _validate_and_build(img_bytes: bytes, mime_type: str, source: str) -> ImageInput:
    size_mb = len(img_bytes) / (1024 * 1024)
    if size_mb > config.IMAGE_MAX_SIZE_MB:
        raise ImageTooLargeError(
            f"Image size {size_mb:.1f}MB exceeds limit {config.IMAGE_MAX_SIZE_MB}MB"
        )
    sha256 = hashlib.sha256(img_bytes).hexdigest()
    data_uri = f"data:{mime_type};base64,{base64.b64encode(img_bytes).decode()}"
    return ImageInput(source=source, mime_type=mime_type, data_uri=data_uri, sha256=sha256)