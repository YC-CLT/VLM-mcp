import socket
import sys

import config
from llama_launcher import start, stop
from logger import get_logger
from providers import disable_backend

logger = get_logger()


def _check_port(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def main():
    logger.info("=== VLM-MCP starting ===")
    llama_config = config.get_llama_config()
    auto_launch = llama_config.get("auto_launch", True)
    proc = None

    if auto_launch:
        try:
            proc = start()
        except Exception as e:
            logger.error("Failed to start llama-server: %s", e)
            print(f"ERROR: Failed to start llama-server: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        host = llama_config.get("host", "127.0.0.1")
        port = llama_config.get("port", 11433)
        if _check_port(host, port):
            logger.info("llama-server already running on %s:%d, skipping auto-launch", host, port)
        else:
            logger.warning(
                "auto_launch=false but llama-server not found on %s:%d, disabling llama-cpp backend",
                host, port,
            )
            disable_backend("llama-cpp")

    try:
        from server import run_server
        run_server()
    except KeyboardInterrupt:
        logger.info("Received Ctrl+C, shutting down")
    except Exception as e:
        logger.error("Server error: %s", e, exc_info=True)
    finally:
        if proc is not None:
            stop(proc)
        logger.info("=== VLM-MCP stopped ===")


if __name__ == "__main__":
    main()