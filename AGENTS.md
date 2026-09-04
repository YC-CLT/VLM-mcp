# AGENTS.md

## 环境

- Python 3.11，uv 管理依赖
- config.py 集中配置所有常量，pyproject.toml 管理依赖
- **命令**：用 `cmd-exec-mcp`

## 关键文件

| 文件 | 作用 |
|------|------|
| `main.py` | 入口，纯启动脚本，启动 MCP |
| `server.py` | MCP Server，7 个工具，stdio 传输 |
| `config.py` | 所有常量 + `config.json` 加载 |
| `config.json` | 敏感配置（API Key、模型路径），不入 git |
| `llama_launcher.py` | llama-server 子进程生命周期（启/停/健康检查） |
| `providers/ocr_provider.py` | OCR Provider（RapidOCR 懒加载 + 延迟卸载） |
| `providers/openai_compat.py` | OpenAI 兼容 API 客户端（AsyncOpenAI）+ llama 懒启动 |
| `session_manager.py` | 会话 CRUD + 超时清理 + 满时驱逐 |
| `cache.py` | L1 图片缓存（LRU）+ L2 响应缓存（LRU + TTL） |
| `image_utils.py` | 图片源解析（路径/URL/Data URI/Base64 回退） |
| `logger.py` | 单例 logger → `log.txt` |

## 关键常量

| 常量 | 位置 | 说明 |
|------|------|------|
| `IMAGE_MAX_SIZE_MB` | `config.py` | 图片最大体积 (20MB) |
| `IMAGE_DOWNLOAD_TIMEOUT` | `config.py` | 图片下载超时秒数 (10s) |
| `CACHE_IMAGE_MAX_ENTRIES` | `config.py` | L1 缓存上限 (100) |
| `CACHE_RESPONSE_MAX_ENTRIES` | `config.py` | L2 缓存上限 (500) |
| `CACHE_RESPONSE_TTL_ONLINE` | `config.py` | 在线后端缓存 TTL (3600s) |
| `CACHE_RESPONSE_TTL_LOCAL` | `config.py` | 本地后端缓存 TTL (1800s) |
| `SESSION_TTL` | `config.py` | 会话超时秒数 (1800s) |
| `SESSION_MAX` | `config.py` | 每后端最大会话数 (5) |
| `LOG_LEVEL` | `config.py` | 日志级别 ("INFO") |
| `LLAMA_DEFAULTS` | `config.py` | llama-server 启动参数默认值 |
| `BACKENDS` | `config.py` | 从 `config.json` 加载的后端配置 |
| `CACHE_ENABLED` | `config.py` | 从 `config.json` 加载的缓存开关 |

## 规则

- **monkeypatch 必须用 `import config` + `config.X`**：`from config import X` 创建本地副本，monkeypatch 无法穿透；executor 同理 patch `executors.模块名.X`
- **config 重命名全量 grep**：常量改名/移除后搜索所有引用
- **跨 Task 依赖等待**：并行派发时先检查上游产物是否存在

## 工具

- 部分工具有相应的skill
- MCP详见 `mcp_tools_summary.csv`
- `Read` 无法访问 `D:\Temp`，MCP 长输出需 `Copy-Item` 到项目根目录，正则替换 `\\n` 为 `\n`
- **Edit `replace_all` 错误**：`replace_all=True` 无法使用。优先用 PowerShell `Select-String` + 正则做精确替换，或手动逐处 Edit
- 浏览器操控用 `chrome-devtools-edge`（Edge CDP），**禁止用 `cua-driver` 操控浏览器**
- **WebFetch 无法使用**：用 `wet-mcp extract`

## 工作流

0. 读AGENTS.md
1. 构想：调用 brainstorming → 产出 `docs/superpowers/specs/<date>-design.md`
2. 计划：调用 writing-plans → 产出 `docs/superpowers/plans/<date>-plan.md`
3. 发派：调用 dispatching-parallel-agents 产出给n号机（目前只有1，2号机）的提示词 `docs/superpowers/subprompts/<date>-plan-subprompt-n.md` ，用于手动发派（当前环境是win且不支持子代理，无法自动 dispatch），创建`docs/superpowers/subprompts/<date>-plan-process.md` 用于记录进度，防止冲突
4. 实施：调用 executing-plans
   - 先隔离，使用git创建新的dev分支（1号机）或者进入已有分支（2号机）  
   - 遇到 bug 自动触发 systematic-debugging（先找根因再修）
   - 写代码自动触发 test-driven-development（先写测试再实现）
5. 验证：调用 verification-before-completion → 跑验证命令确认完成
6. 记录：调用 writing-agents → 写CHANGELOG.md + 经验教训到AGENTS.md
7. 提交：调用 finishing-a-development-branch → 分组提交

## 经验/坑点

- **MCP 2.0 API 变更**：`mcp.server.fastmcp.FastMCP` → `mcp.server.mcpserver.MCPServer`，`mcp.run(transport="sse")` → `mcp.run_sse_async(host=, port=)` 是 async 方法需 `asyncio.run()` 包装
- **cmd-exec-mcp 参数名**：`execute_local` 用 `cwd` 而非 `workdir`
- **uv 需先 `uv venv` 再 `uv pip install`**，否则报 `No virtual environment found`
- **test 阈值**：`IMAGE_MAX_SIZE_MB` monkeypatch 测试时需设极小值（如 0.00001）才能触发 10x10 PNG 的超大判断
- **asyncio.create_task 时序**：必须在 running event loop 内调用，同步代码中需用 `async def` + `asyncio.run()` 包裹
- **session.in_use 泄漏**：工具函数中 `in_use = True` 后所有退出路径必须重置，用外层 `try/finally` 兜底
- **AsyncOpenAI 必用**：async MCP 工具内必须用 `AsyncOpenAI`，同步 `OpenAI` 会阻塞整个 event loop
- **__init__.py 导出完整性**：公开接口全部从 `__init__.py` 导出，调用方不从子模块直接导入，保持风格一致
- **config 常量消费**：`config.py` 定义的常量必须在对应模块中实际使用，避免死代码
- **config 热加载无效**：`config.py` 在 import 时加载 `config.json`，修改配置后必须重启服务端才能生效
- **HTTP 403 不等价 Auth Error**：API 返回 403 可能是额度耗尽（`AllocationQuota.FreeTierOnly`）而非 Key 无效，provider 中勿将 401/403 统一按 Auth Error 禁用后端
- **懒加载 Provider 测试需 mock 启动函数**：openai_compat 中 `_ensure_llama_running` 会启动真实子进程，测试中必须 patch 掉，否则挂起超时
- **config.json 真实值影响测试**：`get_provider("llama-cpp")` 依赖 `config.BACKENDS["llama-cpp"]["enabled"]`，若真实配置为 `false` 则测试需 `patch.dict("config.BACKENDS", ...)` 覆盖
- **`git add -A` 会删除文件**：提交时勿用 `-A`，会意外删除不在版本控制中的文件，应用 `git add <specific files>`