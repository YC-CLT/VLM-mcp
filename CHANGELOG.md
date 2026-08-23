# Changelog

## 2026-08-22 — auto_launch 开关

### Added

- **auto_launch 开关**：`config.json` 的 `llama` 段新增 `"auto_launch"` 字段，默认 `true`
  - `true`：自动启动 llama-server 子进程（与之前行为一致）
  - `false`：跳过子进程启动，适用手动启动或纯在线后端场景
  - `false` 且端口无人在听时，自动禁用 llama-cpp 后端并输出警告
- **providers**：新增 `disable_backend(name)` 公开函数，支持外部禁用后端

### Changed

- **main.py**：重构启动流程，根据 `auto_launch` 分支处理子进程生命周期

---

## 2026-08-22 — 完善与修复

### Fixed

- **GPU offload**：`ngl` 默认值从 `0` 改为 `99`，llama-server 默认全 GPU 运行
- **image-min-tokens**：llama-server 启动参数新增 `--image-min-tokens 1024`，满足 Qwen-VL 最低要求

### Added

- **后端 enabled 字段**：`config.json` 和 `config.example.json` 中每个后端增加 `"enabled"` 字段，支持手动禁用
- **using-vlm-mcp skill**：新增 `skills/using-vlm-mcp/SKILL.md`，为 AI 助手提供 VLM-MCP 使用指南

### Documentation

- **README.md**：补全项目地址、克隆 URL、GPU 配置说明、常见问题章节
- **config.example.json**：`ngl: 0` → `ngl: 99`

---

## 2026-08-22 — VLM-MCP Initial Implementation

### Added

- **Project Setup** (`pyproject.toml`, `.gitignore`, `config.example.json`)
  - Python 3.11 + uv，依赖 mcp>=1.0, openai>=1.0, Pillow, requests, uvicorn
  - 敏感配置 `config.json` 加入 gitignore，示例模板 `config.example.json` 提交

- **Config Module** (`config.py`)
  - 集中管理所有常量：模板、支持格式、缓存参数、会话参数、llama 默认值
  - 运行时从 `config.json` 加载 `BACKENDS`、`DEFAULT_BACKEND`、`CACHE_ENABLED`

- **Logger Module** (`logger.py`)
  - 单例 logger，输出到项目根目录 `log.txt`，追加模式

- **Image Utils** (`image_utils.py`)
  - 支持本地路径、HTTP URL、data URI（base64）三种图片输入
  - 格式校验、大小限制（20MB）、SHA256 哈希

- **Cache Module** (`cache.py`)
  - L1 图片缓存（LRU，100 条）、L2 响应缓存（LRU，500 条，分在线/本地 TTL）
  - 用 `asyncio.Lock` 保证线程安全

- **Session Manager** (`session_manager.py`)
  - 会话 CRUD，每后端最大 5 个会话，超 30 分钟自动清理
  - 满时自动驱逐最久未使用会话

- **Providers** (`providers/`)
  - 抽象基类 `BaseProvider` + `VLMResponse` 数据类
  - OpenAI 兼容后端（`OpenAICompatProvider`），支持本地 llama-cpp 和在线 Qwen3-VL
  - 认证失败自动禁用后端，重启恢复

- **Llama Launcher** (`llama_launcher.py`)
  - 子进程管理 llama-server，同起同停
  - 健康检查 + 模型预热，支持复用已运行实例

- **MCP Server** (`server.py`)
  - 基于 MCP 2.0 SDK (`MCPServer`)，SSE 传输，端口 11432
  - 6 个 MCP 工具：`analyze_image`、`create_session`、`close_session`、`list_sessions`、`list_backends_tool`、`list_templates`
  - 统一错误返回 `{"error": "CODE", "detail": "..."}`

- **Entry Point** (`main.py`)
  - llama-server 生命周期管理，`Ctrl+C` 优雅退出

- **Unit Tests** (`tests/`)
  - 10 个测试覆盖 `image_utils`、`cache`、`session_manager`，全部通过

### Changed

- `main.py` 从占位 Hello World 重写为正式入口点

### Fixed

- `server.py`：`session.in_use` 泄漏（外层 `try/finally` 覆盖所有退出路径）
- `server.py`：`run_server()` 事件循环时序（`async def _run()` + `asyncio.run()` 包裹）
- `providers/`：同步 `OpenAI` → `AsyncOpenAI`，避免阻塞 event loop
- `providers/`：补 `enabled: false` 手动禁用后端检查
- `providers/__init__.py`：补 `list_backends` 导出
- `llama_launcher.py`：`config._CONFIG` → `config.get_llama_exe()` / `get_llama_config()`
- `logger.py`：`logging.INFO` 硬编码 → `config.LOG_LEVEL`
- `config.py`：新增 `get_llama_config()` / `get_llama_exe()` 公开接口
- `pyproject.toml`：补 `description` 字段 + `[project.optional-dependencies] dev`

### Documentation

- `README.md`：从空文件补全（特性、架构、快速开始、工具表、配置常量）
- `AGENTS.md`：补关键文件表、关键常量表、新增 5 条经验/坑点

### Technical Notes

- MCP 2.0 API 与 1.x 不兼容：`FastMCP` → `MCPServer`，`mcp.run()` → `mcp.run_sse_async()`
- 23 个文件，6448 行新增，6 行删除