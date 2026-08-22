import pytest
from cache import image_cache, response_cache


@pytest.mark.asyncio
async def test_image_cache_set_get():
    await image_cache.set("abc123", "data:image/png;base64,xxx")
    result = await image_cache.get("abc123")
    assert result == "data:image/png;base64,xxx"


@pytest.mark.asyncio
async def test_image_cache_miss():
    result = await image_cache.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_response_cache_set_get():
    img = b"fake_image_bytes"
    prompt = "describe this"
    backend = "llama-cpp"
    await response_cache.set(img, prompt, backend, {"text": "a red square", "tokens_used": 10, "model": "test"})
    result = await response_cache.get(img, prompt, backend)
    assert result is not None
    assert result["text"] == "a red square"