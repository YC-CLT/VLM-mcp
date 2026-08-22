import asyncio
import hashlib
import time
from collections import OrderedDict

import config


class ImageCache:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._cache: OrderedDict[str, str] = OrderedDict()

    async def get(self, sha256: str) -> str | None:
        async with self._lock:
            if sha256 in self._cache:
                self._cache.move_to_end(sha256)
                return self._cache[sha256]
            return None

    async def set(self, sha256: str, data_uri: str) -> None:
        async with self._lock:
            if sha256 in self._cache:
                self._cache.move_to_end(sha256)
                return
            if len(self._cache) >= config.CACHE_IMAGE_MAX_ENTRIES:
                self._cache.popitem(last=False)
            self._cache[sha256] = data_uri


class ResponseCache:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._cache: OrderedDict[str, dict] = OrderedDict()

    @staticmethod
    def _make_key(img_bytes: bytes, prompt: str, backend: str) -> str:
        payload = img_bytes + prompt.encode("utf-8") + backend.encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    async def get(self, img_bytes: bytes, prompt: str, backend: str) -> dict | None:
        if not config.CACHE_ENABLED:
            return None
        key = self._make_key(img_bytes, prompt, backend)
        async with self._lock:
            if key not in self._cache:
                return None
            entry = self._cache[key]
            ttl = (
                config.CACHE_RESPONSE_TTL_ONLINE
                if backend != "llama-cpp"
                else config.CACHE_RESPONSE_TTL_LOCAL
            )
            if time.time() - entry["cached_at"] > ttl:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return entry

    async def set(self, img_bytes: bytes, prompt: str, backend: str, value: dict) -> None:
        if not config.CACHE_ENABLED:
            return
        key = self._make_key(img_bytes, prompt, backend)
        async with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return
            if len(self._cache) >= config.CACHE_RESPONSE_MAX_ENTRIES:
                self._cache.popitem(last=False)
            self._cache[key] = {
                "text": value["text"],
                "tokens_used": value["tokens_used"],
                "model": value["model"],
                "cached_at": time.time(),
            }


image_cache = ImageCache()
response_cache = ResponseCache()