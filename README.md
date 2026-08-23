# VLM-MCP

[![GitHub](https://img.shields.io/badge/github-YC--CLT%2FVLM--mcp-blue?logo=github)](https://github.com/YC-CLT/VLM-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Server-orange.svg)](https://modelcontextprotocol.io/)

[English](#english) | [中文](#中文)

VLM-based image understanding MCP Server. Supports local llama.cpp and online VLMs (e.g. Qwen3-VL-Flash) via a unified OpenAI-compatible API.

---

## English

### Features

- **Dual backend**: local llama.cpp + online Qwen3-VL-Flash, unified OpenAI-compatible API
- **Three-tier cache**: L1 image encoding cache, L2 response cache (with TTL), L3 llama-server KV cache
- **Session management**: multi-turn conversation context, auto-eviction and timeout cleanup
- **Prompt templates**: built-in describe / ocr / chart / translate / qa
- **Lifecycle management**: llama-server subprocess auto-starts/stops with MCP, no manual management
- **Backend health**: auto-disable backends on API key errors, manual enable/disable support
- **Multi-source images**: local path, HTTP URL, Base64 Data URI, raw Base64 fallback

### Architecture

```
MCP Client (SSE :11432)
       │
       ▼
  server.py ── tool layer (analyze_image / create_session / ...)
       │
       ├── session_manager.py ── session lifecycle
       ├── cache.py ── L1 image cache + L2 response cache
       ├── image_utils.py ── image parsing (path/URL/Base64)
       │
       ▼
  providers/ ── OpenAI-compatible interface
       │
       ├── llama-cpp (localhost:11433) ← auto-launched by llama_launcher.py
       └── qwen-vl (dashscope API)
```

### Quick Start

#### Requirements

| Component | Notes |
|-----------|-------|
| Python 3.11+ | Runtime |
| [uv](https://github.com/astral-sh/uv) | Package manager |
| [llama.cpp](https://github.com/ggerganov/llama.cpp) | Native binary (`llama-server`), CUDA build required |
| Qwen3-VL-8B GGUF | Language model + vision projector |

> **Note: This project uses the llama.cpp native binary (`llama-server`), NOT `llama-cpp-python`.** No Python bindings needed — just download the llama.cpp executable.

**Recommended model**: Download two files from [Qwen3-VL-8B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF):

| File | Recommended | Notes |
|------|------------|-------|
| Vision model | `Qwen3VL-8B-Instruct-Q4_K_M.gguf` | Q4_K_M quantization, balance of speed & accuracy |
| Vision projector | `mmproj-Qwen3VL-8B-Instruct-F16.gguf` | Must be F16, do not quantize |

> 8 GB VRAM is sufficient. Online-only mode (qwen-vl backend only) can skip llama.cpp and GGUF models.

#### Install

```bash
git clone https://github.com/YC-CLT/VLM-mcp.git
cd VLM-mcp
uv sync
```

#### Configure

```bash
cp config.example.json config.json
```

Edit `config.json`:

```json
{
  "backends": {
    "llama-cpp": {
      "enabled": true,
      "base_url": "http://localhost:11433/v1",
      "api_key": "sk-no-key-required",
      "model_name": "qwen3-vl"
    },
    "qwen-vl": {
      "enabled": false,
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "api_key": "your-dashscope-api-key",
      "model_name": "qwen-vl-flash"
    }
  },
  "default_backend": "llama-cpp",
  "cache_enabled": true,
  "llama": {
    "server_exe": "llama-server",
    "model": "D:/path/to/Qwen3VL-8B-Instruct-Q4_K_M.gguf",
    "mmproj": "D:/path/to/mmproj-Qwen3VL-8B-Instruct-F16.gguf",
    "ngl": 99
  }
}
```

Key fields:

- `backends.<name>.enabled`: set `false` to manually disable a backend
- `llama.model` / `llama.mmproj`: absolute paths to model files (required)
- `llama.ngl`: GPU layers, `99` = all GPU, `0` = CPU only
- `llama.server_exe`: llama-server executable, defaults to PATH lookup

#### Run

```bash
uv run main.py
```

llama-server subprocess auto-starts and stops with MCP. No manual management needed.

MCP SSE endpoint: `http://127.0.0.1:11432/sse`

> Run from any directory: `uv run --directory D:\CodeFile\VLM-mcp main.py`

#### MCP Client Config

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "vlm-mcp": {
      "type": "sse",
      "url": "http://127.0.0.1:11432/sse"
    }
  }
}
```

### MCP Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `analyze_image` | `image`, `prompt`, `template`, `params`, `backend`, `session_id` | Analyze image with template & session support |
| `create_session` | `backend` | Create multi-turn conversation session |
| `close_session` | `session_id` | Close session |
| `list_sessions` | — | List all active sessions |
| `list_backends` | — | List backends and their status |
| `list_templates` | — | List available prompt templates |

#### Templates

| Template | Params | Description |
|----------|--------|-------------|
| `describe` | — | General image description |
| `ocr` | — | Text extraction |
| `chart` | — | Chart analysis |
| `translate` | `target_lang` | Image translation (default: zh) |
| `qa` | `question` | Image Q&A |

#### Examples

```json
// Single analysis
{
  "tool": "analyze_image",
  "args": {
    "image": "D:/photos/cat.png",
    "prompt": "What is in this image?"
  }
}

// Using template
{
  "tool": "analyze_image",
  "args": {
    "image": "https://example.com/chart.png",
    "template": "chart"
  }
}

// Multi-turn session
{ "tool": "create_session", "args": { "backend": "llama-cpp" } }
// → { "session_id": "xxx" }
{ "tool": "analyze_image", "args": { "image": "...", "prompt": "...", "session_id": "xxx" } }
{ "tool": "analyze_image", "args": { "prompt": "Tell me more", "session_id": "xxx" } }
{ "tool": "close_session", "args": { "session_id": "xxx" } }
```

### Configuration Constants

Non-sensitive constants in `config.py`:

| Constant | Default | Description |
|----------|---------|-------------|
| `IMAGE_MAX_SIZE_MB` | 20 | Max image size |
| `IMAGE_DOWNLOAD_TIMEOUT` | 10 | Image download timeout (s) |
| `CACHE_IMAGE_MAX_ENTRIES` | 100 | L1 cache limit |
| `CACHE_RESPONSE_MAX_ENTRIES` | 500 | L2 cache limit |
| `CACHE_RESPONSE_TTL_ONLINE` | 3600 | Online backend cache TTL (s) |
| `CACHE_RESPONSE_TTL_LOCAL` | 1800 | Local backend cache TTL (s) |
| `SESSION_TTL` | 1800 | Session timeout (s) |
| `SESSION_MAX` | 5 | Max sessions per backend |
| `LOG_LEVEL` | "INFO" | Log level |

### Development

```bash
uv sync --dev
uv run pytest tests/ -v
```

### FAQ

**llama-server running on CPU?**  
Check `llama.ngl` in `config.json` — `99` = all GPU, `0` = CPU only.

**llama-server fails to start?**  
Verify `server_exe` is executable and `model`/`mmproj` paths exist. Check `llama_server.log`.

**Online backend returns 401?**  
Invalid API key auto-disables the backend. Set a valid key and restart. Or set `"enabled": false` to skip.

**Port conflict?**  
MCP port 11432, llama-server port 11433. Change `llama.port` in `config.json` or the port in `server.py`.

---

## 中文

## 特性

- **双后端支持**：本地 llama.cpp + 在线 Qwen3-VL-Flash，统一 OpenAI 兼容 API
- **三层缓存**：L1 图片编码缓存、L2 响应缓存（带 TTL）、L3 llama-server KV Cache
- **会话管理**：多轮对话上下文保持，自动淘汰与超时清理
- **提示词模板**：内置 describe / ocr / chart / translate / qa 模板
- **生命周期管理**：llama-server 子进程与 MCP 同起同停，启动即用，无需手动管理
- **后端健康**：API Key 错误自动禁用后端，支持手动启用/禁用
- **多图片来源**：本地路径、HTTP URL、Base64 Data URI、纯 Base64 回退

## 架构

```
MCP Client (SSE :11432)
       │
       ▼
  server.py ── 工具层 (analyze_image / create_session / ...)
       │
       ├── session_manager.py ── 会话生命周期
       ├── cache.py ── L1 图片缓存 + L2 响应缓存
       ├── image_utils.py ── 图片解析 (路径/URL/Base64)
       │
       ▼
  providers/ ── OpenAI 兼容接口
       │
       ├── llama-cpp (localhost:11433) ← llama_launcher.py 自动启动
       └── qwen-vl (dashscope API)
```

## 快速开始

### 环境要求

| 组件 | 说明 |
|------|------|
| Python 3.11+ | 运行环境 |
| [uv](https://github.com/astral-sh/uv) | 包管理 |
| [llama.cpp](https://github.com/ggerganov/llama.cpp) | 原生二进制（`llama-server`），需 CUDA 版 |
| Qwen3-VL-8B GGUF | 语言模型 + 视觉投影器 |

> **注意：本项目使用 llama.cpp 原生二进制（`llama-server`），不是 `llama-cpp-python`。** 无需安装 Python 绑定（即无需`llama-cpp-python`，这个和单llama.cpp相互独立），只需下载 llama.cpp 可执行文件即可。

**推荐模型下载**：从 [Qwen3-VL-8B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF) 下载两个文件：

| 文件 | 推荐 | 说明 |
|------|------|------|
| 视觉模型 | `Qwen3VL-8B-Instruct-Q4_K_M.gguf` | Q4_K_M 量化，平衡速度与精度 |
| 图像编码器 | `mmproj-Qwen3VL-8B-Instruct-F16.gguf` | 建议 F16，不必量化 |

这样8G显存就可以跑

> 纯在线模式（仅用 qwen-vl 后端）可跳过 llama.cpp 和 GGUF 模型。

### 安装

```bash
git clone https://github.com/YC-CLT/VLM-mcp.git
cd VLM-mcp
uv sync
```

### 配置

```bash
cp config.example.json config.json
```

编辑 `config.json`：

```json
{
  "backends": {
    "llama-cpp": {
      "enabled": true,
      "base_url": "http://localhost:11433/v1",
      "api_key": "sk-no-key-required",
      "model_name": "qwen3-vl"
    },
    "qwen-vl": {
      "enabled": false,
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "api_key": "your-dashscope-api-key",
      "model_name": "qwen-vl-flash"
    }
  },
  "default_backend": "llama-cpp",
  "cache_enabled": true,
  "llama": {
    "server_exe": "llama-server",
    "model": "D:/path/to/Qwen3VL-8B-Instruct-Q4_K_M.gguf",
    "mmproj": "D:/path/to/mmproj-Qwen3VL-8B-Instruct-F16.gguf",
    "ngl": 99
  }
}
```

关键字段：

- `backends.<name>.enabled`：设为 `false` 可手动禁用后端
- `llama.model` / `llama.mmproj`：本地模型文件绝对路径（必填）
- `llama.ngl`：GPU 层数，`99` 表示全部 offload 到 GPU，`0` 为纯 CPU
- `llama.server_exe`：llama-server 可执行文件，默认从 PATH 查找

### 运行

```bash
uv run main.py
```

启动后会自动拉起 llama-server 子进程，MCP 退出时自动停止。无需手动管理 llama-server。

MCP SSE 端点：`http://127.0.0.1:11432/sse`

> 从任意目录运行：`uv run --directory D:\CodeFile\VLM-mcp main.py`

### MCP 客户端配置

在你的 MCP 客户端配置文件中添加：

```json
{
  "mcpServers": {
    "vlm-mcp": {
      "type": "sse",
      "url": "http://127.0.0.1:11432/sse"
    }
  }
}
```

## MCP 工具

| 工具 | 参数 | 说明 |
|------|------|------|
| `analyze_image` | `image`, `prompt`, `template`, `params`, `backend`, `session_id` | 分析图片，支持模板和会话 |
| `create_session` | `backend` | 创建多轮对话会话 |
| `close_session` | `session_id` | 关闭会话 |
| `list_sessions` | — | 列出所有活跃会话 |
| `list_backends` | — | 列出后端及其状态 |
| `list_templates` | — | 列出可用提示词模板 |

### 模板

| 模板 | 参数 | 说明 |
|------|------|------|
| `describe` | — | 通用图片描述 |
| `ocr` | — | 文字提取 |
| `chart` | — | 图表分析 |
| `translate` | `target_lang` | 图片翻译（默认中文） |
| `qa` | `question` | 图片问答 |

### 使用示例

```json
// 单次分析
{
  "tool": "analyze_image",
  "args": {
    "image": "D:/photos/cat.png",
    "prompt": "这张图片里有什么？"
  }
}

// 使用模板
{
  "tool": "analyze_image",
  "args": {
    "image": "https://example.com/chart.png",
    "template": "chart"
  }
}

// 多轮会话
{ "tool": "create_session", "args": { "backend": "llama-cpp" } }
// → { "session_id": "xxx" }
{ "tool": "analyze_image", "args": { "image": "...", "prompt": "...", "session_id": "xxx" } }
{ "tool": "analyze_image", "args": { "prompt": "继续分析", "session_id": "xxx" } }
{ "tool": "close_session", "args": { "session_id": "xxx" } }
```

## 配置常量

非敏感常量集中于 `config.py`，可在代码中直接修改：

| 常量 | 默认值 | 说明 |
|------|--------|------|
| `IMAGE_MAX_SIZE_MB` | 20 | 图片最大体积 |
| `IMAGE_DOWNLOAD_TIMEOUT` | 10 | 图片下载超时（秒） |
| `CACHE_IMAGE_MAX_ENTRIES` | 100 | L1 缓存上限 |
| `CACHE_RESPONSE_MAX_ENTRIES` | 500 | L2 缓存上限 |
| `CACHE_RESPONSE_TTL_ONLINE` | 3600 | 在线后端缓存 TTL（秒） |
| `CACHE_RESPONSE_TTL_LOCAL` | 1800 | 本地后端缓存 TTL（秒） |
| `SESSION_TTL` | 1800 | 会话超时（秒） |
| `SESSION_MAX` | 5 | 每后端最大会话数 |
| `LOG_LEVEL` | "INFO" | 日志级别 |

## 开发

```bash
uv sync --dev
uv run pytest tests/ -v
```

## 常见问题

**llama-server 跑在 CPU 上？**  
检查 `config.json` 中 `llama.ngl` 是否为 `99`（全 GPU），`0` 为纯 CPU。

**llama-server 启动失败？**  
确认 `server_exe` 可执行（PATH 中或绝对路径），`model`/`mmproj` 路径存在。查看 `llama_server.log`。

**在线后端 401 错误？**  
API Key 无效时会自动禁用该后端，设好 Key 后重启即可恢复。也可手动设 `"enabled": false` 跳过。

**端口被占用？**  
MCP 端口 11432，llama-server 端口 11433。修改 `config.json` 中 `llama.port` 或 `server.py` 中端口号。

## 许可

MIT