import sys

from llama_launcher import start, stop
from logger import get_logger

logger = get_logger()


def main():
    logger.info("=== VLM-MCP starting ===")
    try:
        proc = start()
    except Exception as e:
        logger.error("Failed to start llama-server: %s", e)
        print(f"ERROR: Failed to start llama-server: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        from server import run_server
        run_server()
    except KeyboardInterrupt:
        logger.info("Received Ctrl+C, shutting down")
    except Exception as e:
        logger.error("Server error: %s", e, exc_info=True)
    finally:
        stop(proc)
        logger.info("=== VLM-MCP stopped ===")


if __name__ == "__main__":
    main()