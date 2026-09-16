import atexit
import shutil
import subprocess
import time
from pathlib import Path

import requests

import config
from logger import get_logger

logger = get_logger()


def _find_exe() -> str:
    server_exe = config.get_llama_exe()
    if Path(server_exe).is_absolute() and Path(server_exe).exists():
        return server_exe
    found = shutil.which(server_exe)
    if found:
        return found
    raise FileNotFoundError(
        f"llama-server executable not found. "
        f"Ensure '{server_exe}' is in PATH or set absolute path in config.json"
    )


def _get_llama_config() -> dict:
    merged = config.get_llama_config()
    if not merged.get("model"):
        raise ValueError("config.json: llama.model is required (GGUF model path)")
    if not merged.get("mmproj"):
        raise ValueError("config.json: llama.mmproj is required (vision projector path)")
    for key in ("model", "mmproj"):
        if not Path(merged[key]).exists():
            raise FileNotFoundError(f"Model file not found: {merged[key]}")
    return merged


def _check_health(host: str, port: int, timeout: int, interval: int) -> bool:
    url = f"http://{host}:{port}/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=5, proxies={"http": None})
            if resp.status_code == 200 and resp.json().get("status") == "ok":
                return True
        except requests.RequestException:
            pass
        time.sleep(interval)
    return False


def _check_model_ready(host: str, port: int) -> bool:
    url = f"http://{host}:{port}/v1/chat/completions"
    try:
        resp = requests.post(
            url,
            json={"messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
            timeout=30,
            proxies={"http": None},
        )
        if resp.status_code == 200:
            return True
        logger.warning("Model warmup returned %s: %s", resp.status_code, resp.text[:200])
        return False
    except requests.RequestException as e:
        logger.warning("Model warmup failed: %s", e)
        return False


def start() -> subprocess.Popen | None:
    cfg = _get_llama_config()
    host = cfg["host"]
    port = cfg["port"]

    try:
        resp = requests.get(f"http://{host}:{port}/health", timeout=3, proxies={"http": None})
        if resp.status_code == 200 and resp.json().get("status") == "ok":
            logger.info("Reusing existing llama-server on %s:%s", host, port)
            return None
    except requests.RequestException:
        pass

    exe = _find_exe()
    cmd = [
        exe,
        "-m", cfg["model"],
        "--mmproj", cfg["mmproj"],
        "--host", str(host),
        "--port", str(port),
        "-ngl", str(cfg["ngl"]),
        "-c", str(cfg["ctx_size"]),
        "-n", str(cfg["predict"]),
        "--temp", str(cfg["temperature"]),
        "--top-k", str(cfg["top_k"]),
        "--top-p", str(cfg["top_p"]),
        "--repeat-penalty", str(cfg["repeat_penalty"]),
        "--presence-penalty", str(cfg["presence_penalty"]),
        "--flash-attn", str(cfg["flash_attn"]),
        "-ctk", str(cfg["cache_type_k"]),
        "-ctv", str(cfg["cache_type_v"]),
        "-np", str(cfg["parallel"]),
        "--image-min-tokens", str(cfg.get("image_min_tokens", 1024)),
        "--image-max-tokens", str(cfg.get("image_max_tokens", 2048)),
        "--no-webui",
    ]

    if "threads" in cfg:
        cmd.extend(["-t", str(cfg["threads"])])
    if "batch_size" in cfg:
        cmd.extend(["-b", str(cfg["batch_size"])])
    if "alias" in cfg:
        cmd.extend(["--alias", str(cfg["alias"])])

    log_path = Path(__file__).parent / "llama_server.log"
    log_file = open(log_path, "a", encoding="utf-8")

    logger.info("Starting llama-server: %s", " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )

    if not _check_health(
        host, port,
        cfg["health_poll_timeout"],
        cfg["health_poll_interval"],
    ):
        proc.kill()
        proc.wait()
        raise RuntimeError(
            f"llama-server health check failed (timeout={cfg['health_poll_timeout']}s). "
            f"Check llama_server.log for details."
        )

    if not _check_model_ready(host, port):
        proc.kill()
        proc.wait()
        raise RuntimeError(
            "llama-server started but model warmup failed. "
            "Check llama_server.log for details."
        )

    logger.info("llama-server ready on %s:%s", host, port)
    atexit.register(lambda: stop(proc))
    return proc


def stop(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    logger.info("Stopping llama-server (pid=%s)", proc.pid)
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    logger.info("llama-server stopped")