# VLM-MCP

基于 VLM（Vision-Language Model）的图片理解 MCP Server，支持本地 llama.cpp 和在线 VLM（如 Qwen3-VL-Flash），统一 OpenAI 兼容接口。

## 特性

- **双后端支持**：本地 llama.cpp + 在线 Qwen3-VL-Flash，统一 OpenAI 兼容 API
- **三层缓存**：L1 图片编码缓存、L2 响应缓存（带 TTL）、L3 llama-server KV Cache
- **会话管理**：多轮对话上下文保持，自动淘汰与超时清理
- **提示词模板**：内置 describe / ocr / chart / translate / qa 模板
- **生命周期管理**：llama-server 子进程与 MCP 同起同停，健康检查 + 模型预热
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

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- （可选）[llama.cpp](https://github.com/ggerganov/llama.cpp) + Qwen3-VL GGUF 模型

### 安装

```bash
git clone <repo-url>
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
      "base_url": "http://localhost:11433/v1",
      "api_key": "sk-no-key-required",
      "model_name": "qwen3-vl"
    },
    "qwen-vl": {
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "api_key": "your-dashscope-api-key",
      "model_name": "qwen-vl-flash"
    }
  },
  "default_backend": "llama-cpp",
  "cache_enabled": true,
  "llama": {
    "server_exe": "llama-server",
    "model": "D:/path/to/model.gguf",
    "mmproj": "D:/path/to/mmproj.gguf"
  }
}
```

关键字段：

- `backends.<name>.enabled`：设为 `false` 可手动禁用后端
- `llama.model` / `llama.mmproj`：本地模型文件绝对路径（必填）
- `llama.server_exe`：llama-server 可执行文件，默认从 PATH 查找

### 运行

```bash
uv run main.py
```

MCP SSE 端点：`http://127.0.0.1:11432/sse`

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

## 许可

MIT