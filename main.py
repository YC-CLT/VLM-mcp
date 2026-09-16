import os

os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,.local")

from logger import get_logger

logger = get_logger()


def main():
    logger.info("=== VLM-MCP starting ===")
    try:
        from server import run_server
        run_server()
    except KeyboardInterrupt:
        logger.info("Received Ctrl+C, shutting down")
    except Exception as e:
        logger.error("Server error: %s", e, exc_info=True)
    finally:
        logger.info("=== VLM-MCP stopped ===")


if __name__ == "__main__":
    main()