import asyncio
import base64

from mcp.server.mcpserver import MCPServer

import config
from cache import image_cache, response_cache
from image_utils import (
    ImageInput,
    ImageNotFoundError,
    ImageDownloadError,
    ImageInvalidFormatError,
    ImageTooLargeError,
    ImageInvalidBase64Error,
    resolve_image,
)
from logger import get_logger
from providers import get_provider, list_backends
from providers.ocr_provider import ocr
from providers.openai_compat import (
    BackendNotFoundError,
    BackendAuthError,
    BackendDisabledError,
    BackendUnavailableError,
)
from session_manager import (
    SessionNotFoundError,
    SessionFullError,
    session_manager,
)

logger = get_logger()
mcp = MCPServer("vlm-mcp")


def _build_message(image: ImageInput | None, prompt: str) -> dict:
    if image is None:
        return {"role": "user", "content": prompt}
    return {
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": image.data_uri}},
            {"type": "text", "text": prompt},
        ],
    }


@mcp.tool(description="分析图片：传 image + prompt 或 template。无 session 时 image 必传")
async def analyze_image(
    image: str | None = None,
    prompt: str | None = None,
    template: str | None = None,
    params: dict | None = None,
    backend: str | None = None,
    session_id: str | None = None,
) -> dict:
    if session_id and backend is None:
        session = await session_manager.get(session_id)
        backend = session.backend
    if backend is None:
        backend = config.DEFAULT_BACKEND

    if prompt is None and template is None:
        return {"error": "INVALID_PARAMS", "detail": "prompt or template is required"}

    if session_id is None and image is None:
        return {"error": "INVALID_PARAMS", "detail": "image is required when no session_id"}

    if template:
        tmpl = config.TEMPLATES.get(template)
        if tmpl is None:
            return {"error": "TEMPLATE_NOT_FOUND", "detail": f"Template '{template}' not found"}
        merged_params = {**tmpl.get("params", {}), **(params or {})}
        for req in tmpl.get("required_params", []):
            if req not in merged_params:
                return {
                    "error": "INVALID_PARAMS",
                    "detail": f"Missing required param '{req}' for template '{template}'",
                }
        prompt = tmpl["prompt"].format(**merged_params)

    if session_id:
        session = await session_manager.get(session_id)
        if session.backend != backend:
            return {
                "error": "SESSION_BACKEND_MISMATCH",
                "detail": f"Session '{session_id}' is bound to backend '{session.backend}', not '{backend}'",
            }
        session.in_use = True

    try:
        try:
            provider = get_provider(backend)
        except BackendNotFoundError as e:
            return {"error": "BACKEND_NOT_FOUND", "detail": str(e)}
        except BackendDisabledError as e:
            return {"error": "BACKEND_DISABLED", "detail": str(e)}

        img_input: ImageInput | None = None
        img_bytes: bytes | None = None
        if image is not None:
            try:
                img_input = resolve_image(image)
                img_bytes = base64.b64decode(img_input.data_uri.split(",", 1)[1])
                cached_uri = await image_cache.get(img_input.sha256)
                if cached_uri:
                    img_input.data_uri = cached_uri
                else:
                    await image_cache.set(img_input.sha256, img_input.data_uri)
            except ImageNotFoundError as e:
                return {"error": "IMAGE_NOT_FOUND", "detail": str(e)}
            except ImageDownloadError as e:
                return {"error": "IMAGE_DOWNLOAD_FAILED", "detail": str(e)}
            except ImageInvalidFormatError as e:
                return {"error": "IMAGE_INVALID_FORMAT", "detail": str(e)}
            except ImageTooLargeError as e:
                return {"error": "IMAGE_TOO_LARGE", "detail": str(e)}
            except ImageInvalidBase64Error as e:
                return {"error": "IMAGE_INVALID_BASE64", "detail": str(e)}

        if session_id is None and img_bytes is not None and config.CACHE_ENABLED:
            cached = await response_cache.get(img_bytes, prompt, backend)
            if cached:
                return {
                    "text": cached["text"],
                    "model": cached["model"],
                    "tokens_used": cached["tokens_used"],
                    "cache_hit": True,
                    "session_id": None,
                }

        try:
            if session_id:
                session = await session_manager.get(session_id)
                message = _build_message(img_input, prompt)
                session.messages.append(message)
                session.msg_count += 1
                if img_input is not None:
                    session.image_uris.append(img_input.data_uri)
                result = await provider.chat(session.messages)
                session.messages.append({"role": "assistant", "content": result.text})
                session.msg_count += 1
                return {
                    "text": result.text,
                    "model": result.model,
                    "tokens_used": result.tokens_used,
                    "cache_hit": False,
                    "session_id": session_id,
                }
            else:
                result = await provider.analyze(img_input, prompt)
                if img_bytes is not None and config.CACHE_ENABLED:
                    await response_cache.set(
                        img_bytes, prompt, backend,
                        {"text": result.text, "tokens_used": result.tokens_used, "model": result.model},
                    )
                return {
                    "text": result.text,
                    "model": result.model,
                    "tokens_used": result.tokens_used,
                    "cache_hit": False,
                    "session_id": None,
                }
        except BackendAuthError as e:
            return {"error": "BACKEND_AUTH_ERROR", "detail": str(e)}
        except BackendDisabledError as e:
            return {"error": "BACKEND_DISABLED", "detail": str(e)}
        except BackendUnavailableError as e:
            return {"error": "BACKEND_UNAVAILABLE", "detail": str(e)}
        except Exception as e:
            logger.error("Unexpected error: %s", e, exc_info=True)
            return {"error": "BACKEND_API_ERROR", "detail": str(e)}
    finally:
        if session_id:
            try:
                s = await session_manager.get(session_id)
                s.in_use = False
            except SessionNotFoundError:
                pass


@mcp.tool(description="创建多轮对话会话，绑定后端。用完必须 close_session")
async def create_session(backend: str | None = None) -> dict:
    if backend is None:
        backend = config.DEFAULT_BACKEND
    try:
        sid = await session_manager.create(backend)
        return {"session_id": sid, "backend": backend}
    except SessionFullError as e:
        return {"error": "SESSION_FULL", "detail": str(e)}


@mcp.tool(description="关闭会话，释放槽位")
async def close_session(session_id: str) -> dict:
    try:
        await session_manager.close(session_id)
        return {"closed": session_id}
    except SessionNotFoundError as e:
        return {"error": "SESSION_NOT_FOUND", "detail": str(e)}


@mcp.tool(description="列出所有活跃会话")
async def list_sessions() -> dict:
    sessions = await session_manager.list_sessions()
    return {"sessions": sessions}


@mcp.tool(description="列出可用后端及其状态")
async def list_backends_tool() -> dict:
    return {"backends": list_backends()}


@mcp.tool(description="列出内置提示词模板")
async def list_templates() -> dict:
    return {
        "templates": [
            {
                "name": name,
                "description": t["description"],
                "params": t.get("required_params", []),
            }
            for name, t in config.TEMPLATES.items()
        ]
    }


@mcp.tool(description="OCR 提取图片文字，优先使用。返回文字、位置坐标、置信度。")
async def ocr_image(image: str) -> list:
    try:
        img_input = resolve_image(image)
    except ImageNotFoundError as e:
        return {"error": "IMAGE_NOT_FOUND", "detail": str(e)}
    except ImageDownloadError as e:
        return {"error": "IMAGE_DOWNLOAD_FAILED", "detail": str(e)}
    except ImageInvalidFormatError as e:
        return {"error": "IMAGE_INVALID_FORMAT", "detail": str(e)}
    except ImageTooLargeError as e:
        return {"error": "IMAGE_TOO_LARGE", "detail": str(e)}
    except ImageInvalidBase64Error as e:
        return {"error": "IMAGE_INVALID_BASE64", "detail": str(e)}
    img_bytes = base64.b64decode(img_input.data_uri.split(",", 1)[1])
    try:
        return await ocr.recognize(img_bytes)
    except Exception as e:
        return {"error": "OCR_ERROR", "detail": str(e)}


def run_server():
    async def _run():
        session_manager.start_cleanup_task()
        logger.info("VLM-MCP server starting (stdio)")
        try:
            await mcp.run_stdio_async()
        finally:
            session_manager.stop_cleanup_task()

    asyncio.run(_run())