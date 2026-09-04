from unittest.mock import AsyncMock, patch

import pytest

from image_utils import ImageInput
from providers.openai_compat import (
    BackendAuthError,
    BackendDisabledError,
    BackendNotFoundError,
    BackendUnavailableError,
    OpenAICompatProvider,
    VLMResponse,
    _disabled_backends,
    disable_backend,
    get_provider,
    list_backends,
)


def _make_image() -> ImageInput:
    return ImageInput(
        source="test.png",
        mime_type="image/png",
        data_uri="data:image/png;base64,iVBORw0KGgo=",
        sha256="a" * 64,
    )


def _mock_chat_response(text="hello", tokens=10, model="test-model"):
    resp = AsyncMock()
    resp.choices = [AsyncMock()]
    resp.choices[0].message.content = text
    resp.usage = AsyncMock()
    resp.usage.total_tokens = tokens
    resp.model = model
    return resp


class TestProvider:

    def setup_method(self):
        _disabled_backends.clear()

    def test_get_provider_llama(self):
        with patch.dict("config.BACKENDS", {
            "llama-cpp": {
                "enabled": True,
                "base_url": "http://127.0.0.1:11433/v1",
                "model_name": "test-model",
            }
        }):
            provider = get_provider("llama-cpp")
            assert provider._name == "llama-cpp"

    def test_get_provider_not_found(self):
        with pytest.raises(BackendNotFoundError):
            get_provider("nonexistent")

    def test_get_provider_disabled_backend(self):
        with patch.dict("config.BACKENDS", {
            "qwen-vl": {
                "enabled": False,
                "base_url": "https://example.com/v1",
                "api_key": "sk-test",
                "model_name": "qwen-vl-flash",
            }
        }):
            with pytest.raises(BackendDisabledError):
                get_provider("qwen-vl")

    def test_get_provider_missing_api_key(self):
        with patch.dict("config.BACKENDS", {
            "qwen-vl": {
                "enabled": True,
                "base_url": "https://example.com/v1",
                "api_key": "",
                "model_name": "qwen-vl-flash",
            }
        }):
            with pytest.raises(BackendDisabledError):
                get_provider("qwen-vl")

    @pytest.mark.asyncio
    async def test_analyze_mock(self):
        fake_resp = _mock_chat_response(text="a cat", tokens=42)
        with patch.dict("config.BACKENDS", {
            "llama-cpp": {
                "enabled": True,
                "base_url": "http://127.0.0.1:11433/v1",
                "model_name": "test-model",
            }
        }):
            with patch("providers.openai_compat._ensure_llama_running", new_callable=AsyncMock):
                with patch("providers.openai_compat._schedule_llama_unload"):
                    with patch("providers.openai_compat.AsyncOpenAI") as mock_client:
                        mock_client.return_value.chat.completions.create = AsyncMock(
                            return_value=fake_resp
                        )
                        provider = get_provider("llama-cpp")
                        image = _make_image()
                        result = await provider.analyze(image, "describe")
                        assert result.text == "a cat"
                        assert result.tokens_used == 42
                        assert result.model == "test-model"

    @pytest.mark.asyncio
    async def test_analyze_auth_error(self):
        fake_resp = AsyncMock()
        fake_resp.status_code = 401
        exc = Exception("unauthorized")
        exc.response = fake_resp

        with patch.dict("config.BACKENDS", {
            "llama-cpp": {
                "enabled": True,
                "base_url": "http://127.0.0.1:11433/v1",
                "model_name": "test-model",
            }
        }):
            with patch("providers.openai_compat._ensure_llama_running", new_callable=AsyncMock):
                with patch("providers.openai_compat._schedule_llama_unload"):
                    with patch("providers.openai_compat.AsyncOpenAI") as mock_client:
                        mock_client.return_value.chat.completions.create = AsyncMock(
                            side_effect=exc
                        )
                        provider = get_provider("llama-cpp")
                        with pytest.raises(BackendAuthError):
                            await provider.analyze(_make_image(), "describe")
                        assert "llama-cpp" in _disabled_backends

    @pytest.mark.asyncio
    async def test_analyze_500_error(self):
        fake_resp = AsyncMock()
        fake_resp.status_code = 500
        exc = Exception("server error")
        exc.response = fake_resp

        with patch.dict("config.BACKENDS", {
            "llama-cpp": {
                "enabled": True,
                "base_url": "http://127.0.0.1:11433/v1",
                "model_name": "test-model",
            }
        }):
            with patch("providers.openai_compat._ensure_llama_running", new_callable=AsyncMock):
                with patch("providers.openai_compat._schedule_llama_unload"):
                    with patch("providers.openai_compat.AsyncOpenAI") as mock_client:
                        mock_client.return_value.chat.completions.create = AsyncMock(
                            side_effect=exc
                        )
                        provider = get_provider("llama-cpp")
                        with pytest.raises(BackendUnavailableError):
                            await provider.analyze(_make_image(), "describe")

    def test_disable_backend(self):
        disable_backend("llama-cpp")
        assert "llama-cpp" in _disabled_backends

    def test_list_backends(self):
        disable_backend("qwen-vl")
        backends = list_backends()
        names = {b["name"] for b in backends}
        assert "llama-cpp" in names
        assert "qwen-vl" in names
        for b in backends:
            if b["name"] == "qwen-vl":
                assert b["status"] == "disabled"
            else:
                assert b["status"] == "available"