import logging
from pathlib import Path

import config

_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    _logger = logging.getLogger("vlm-mcp")
    _logger.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))

    log_path = Path(__file__).parent / "log.txt"
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] vlm-mcp: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    _logger.addHandler(handler)

    return _logger