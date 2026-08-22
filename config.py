import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent

TEMPLATES = {
    "describe": {
        "prompt": "请详细描述这张图片的内容。",
        "description": "通用图片描述",
    },
    "ocr": {
        "prompt": "提取这张图片中的所有文字，按原文排版输出。",
        "description": "文字提取",
    },
    "chart": {
        "prompt": "分析这张图表，提取关键数据和趋势，用中文输出。",
        "description": "图表分析",
    },
    "translate": {
        "prompt": "将图片中的文字翻译为{target_lang}。",
        "params": {"target_lang": "中文"},
        "required_params": ["target_lang"],
        "description": "图片翻译",
    },
    "qa": {
        "prompt": "根据图片内容回答：{question}",
        "params": {},
        "required_params": ["question"],
        "description": "图片问答",
    },
}

SUPPORTED_FORMATS = ["png", "jpeg", "jpg", "webp", "gif", "bmp"]
IMAGE_MAX_SIZE_MB = 20
IMAGE_DOWNLOAD_TIMEOUT = 10

CACHE_IMAGE_MAX_ENTRIES = 100
CACHE_RESPONSE_MAX_ENTRIES = 500
CACHE_RESPONSE_TTL_ONLINE = 3600
CACHE_RESPONSE_TTL_LOCAL = 1800

SESSION_TTL = 1800
SESSION_MAX = 5

LOG_LEVEL = "INFO"

LLAMA_DEFAULTS = {
    "server_exe": "llama-server",
    "host": "127.0.0.1",
    "port": 11433,
    "ngl": 0,
    "ctx_size": 8192,
    "predict": 16384,
    "temperature": 0.7,
    "top_k": 20,
    "top_p": 0.8,
    "repeat_penalty": 1.0,
    "presence_penalty": 1.5,
    "flash_attn": "auto",
    "cache_type_k": "f16",
    "cache_type_v": "f16",
    "parallel": 1,
    "health_poll_interval": 3,
    "health_poll_timeout": 180,
}


def _load_json():
    config_path = PROJECT_ROOT / "config.json"
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


_CONFIG = _load_json()
BACKENDS = _CONFIG.get("backends", {})
DEFAULT_BACKEND = _CONFIG.get("default_backend", "llama-cpp")
CACHE_ENABLED = _CONFIG.get("cache_enabled", True)