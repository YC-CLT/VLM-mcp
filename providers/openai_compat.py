from openai import OpenAI

from image_utils import ImageInput
from providers.base import BaseProvider, VLMResponse
import config

try:
    from logger import get_logger
    _logger = get_logger()
except Exception:
    import logging
    _logger = logging.getLogger(__name__)


class BackendError(Exception):
    pass


class BackendNotFoundError(BackendError):
    pass


class BackendAuthError(BackendError):
    pass


class BackendDisabledError(BackendError):
    pass


class BackendUnavailableError(BackendError):
    pass


_disabled_backends: set[str] = set()


class OpenAICompatProvider(BaseProvider):
    def __init__(self, backend_name: str):
        if backend_name not in config.BACKENDS:
            raise BackendNotFoundError(f"Backend '{backend_name}' not found")
        cfg = config.BACKENDS[backend_name]
        required = ["base_url", "model_name"]
        if backend_name != "llama-cpp":
            required.append("api_key")
        for field in required:
            if not cfg.get(field):
                _disabled_backends.add(backend_name)
                raise BackendDisabledError(
                    f"Backend '{backend_name}' is disabled: '{field}' is empty"
                )

        self._name = backend_name
        self._client = OpenAI(
            base_url=cfg["base_url"],
            api_key=cfg.get("api_key", "sk-no-key-required"),
        )
        self._model = cfg["model_name"]

    def _check_disabled(self):
        if self._name in _disabled_backends:
            raise BackendDisabledError(
                f"Backend '{self._name}' is disabled. Restart MCP to re-enable."
            )

    def _call_api(self, messages: list[dict]) -> VLMResponse:
        self._check_disabled()
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=False,
            )
            return VLMResponse(
                text=resp.choices[0].message.content or "",
                tokens_used=resp.usage.total_tokens if resp.usage else 0,
                model=resp.model,
            )
        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (401, 403):
                _disabled_backends.add(self._name)
                _logger.error("Backend '%s' auth failed (HTTP %s), disabled", self._name, status)
                raise BackendAuthError(
                    f"Backend '{self._name}' API key invalid, backend disabled"
                ) from e
            if status and status >= 500:
                raise BackendUnavailableError(
                    f"Backend '{self._name}' unavailable (HTTP {status})"
                ) from e
            raise BackendUnavailableError(
                f"Backend '{self._name}' error: {e}"
            ) from e

    def analyze(self, image: ImageInput, prompt: str) -> VLMResponse:
        message = {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image.data_uri}},
                {"type": "text", "text": prompt},
            ],
        }
        return self._call_api([message])

    def chat(self, messages: list[dict]) -> VLMResponse:
        return self._call_api(messages)


def get_provider(backend_name: str) -> OpenAICompatProvider:
    return OpenAICompatProvider(backend_name)


def list_backends() -> list[dict]:
    result = []
    for name, cfg in config.BACKENDS.items():
        status = "disabled" if name in _disabled_backends else "available"
        result.append({"name": name, "model": cfg.get("model_name", ""), "status": status})
    return result