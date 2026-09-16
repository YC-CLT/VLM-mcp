# llama.cpp Server 调研：与 VLM-mcp 项目集成

> 调研日期: 2026-08-21
> 仓库: [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp) (125k stars)
> 调研工具: wet-mcp (extract + download), 代码阅读

---

## 1. 背景

VLM-mcp 是一个 MCP Server，通过 OpenAI 兼容 API 连接 llama.cpp server 提供视觉语言模型推理能力。当前版本已实现子进程生命周期管理、健康检查、会话管理、图片缓存等核心功能。

本次调研聚焦两方面：
- 已实现部分的**现状核对**（参数、API 调用是否正确）
- 未利用的**新特性**（Reasoning、Token 预算、MCP 工具等）

---

## 2. 当前集成架构

```
main.py
  ├── llama_launcher.py  ──→  subprocess: llama-server (端口 11433)
  │     ├── 健康检查: GET /health
  │     ├── 模型预热: POST /v1/chat/completions (max_tokens=1)
  │     └── 生命周期: atexit 注册 stop
  │
  └── server.py (MCP Server, 端口 11432)
        └── providers/openai_compat.py
              └── AsyncOpenAI → POST /v1/chat/completions
```

### 2.1 当前启动参数（2026-09-17 调优后）

实际启动命令（`llama_launcher.py` 根据 `config.json` 构建）：

```
llama-server
  -m <model.gguf>
  --mmproj <mmproj.gguf>
  --host 127.0.0.1
  --port 11433
  -ngl 99
  -c 8192
  -n 16384
  --temp 0.7
  --top-k 20
  --top-p 0.8
  --repeat-penalty 1.0
  --presence-penalty 1.0
  --flash-attn auto
  -t 4
  -b 512
  -ctk q8_0
  -ctv q8_0
  -np 1
  --image-min-tokens 1024
  --image-max-tokens 2048
  --alias qwen3-vl
  --no-webui
```

**相比初始版本的变更**：

| 参数 | 旧值 | 新值 | 原因 |
|------|------|------|------|
| `-ctk` / `-ctv` | `f16` | `q8_0` | KV cache 量化节省 ~30% VRAM，推理速度几乎无损 |
| `-t` | 未设 | `4` | 实测 `-t` 过高会导致生成质量下降（"散"），4 线程最佳 |
| `-b` | 未设 | `512` | 批量大小，加速 prompt 处理 |
| `--image-max-tokens` | 未设 | `2048` | 防止大分辨率图片撑爆 context |
| `--alias` | 未设 | `qwen3-vl` | API model 名简化，`/v1/models` 返回干净名 |
| `--presence-penalty` | `1.5` | `1.0` | Qwen3-VL 官方推荐 VL 场景为 1.5，实测 1.0 更稳定 |

**性能基准**（Qwen3-VL-8B Q4_K_M，RTX 3070 8GB）：
- 纯文本生成：~46 t/s
- 带图 VLM 推理：~35 t/s
- 模型加载：~7s（含健康检查+预热）

### 2.2 当前 API 调用

`providers/openai_compat.py` 通过 `AsyncOpenAI` 调用：

```python
# 图片分析（单轮）
resp = await client.chat.completions.create(
    model=self._model,
    messages=[{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": image.data_uri}},  # data:image/...;base64,...
            {"type": "text", "text": prompt},
        ],
    }],
    stream=False,
)

# 会话对话（多轮）
resp = await client.chat.completions.create(
    model=self._model,
    messages=session.messages,  # 累积的 message 列表
    stream=False,
)
```

---

## 3. llama.cpp Server API 速查

### 3.1 端点一览

| 端点 | 协议 | 说明 |
|------|------|------|
| `GET /health` | 原生 | 健康检查（加载中 503，就绪 200） |
| `POST /v1/chat/completions` | **OpenAI** | 对话补全，**多模态支持** |
| `POST /v1/chat/completions/control` | OpenAI | 实时控制推理（提前结束 reasoning） |
| `POST /v1/completions` | OpenAI | 文本补全 |
| `POST /v1/responses` | OpenAI | Responses API（自动转 Chat） |
| `POST /v1/embeddings` | OpenAI | 嵌入向量 |
| `POST /v1/messages` | **Anthropic** | Messages API（备选协议） |
| `GET /v1/models` | OpenAI | 模型信息 |
| `POST /completion` | 原生 | 原生补全（参数更丰富） |
| `POST /tokenize` | 原生 | 分词 |
| `GET /props` | 原生 | 服务属性 |
| `GET /slots` | 原生 | Slot 状态监控 |

### 3.2 `/v1/chat/completions` 多模态参数详解

这是 VLM-mcp 的核心调用端点。请求体关键字段：

```json
{
  "model": "gpt-3.5-turbo",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "image_url", "image_url": {"url": "<url>"}},
      {"type": "text", "text": "describe this image"}
    ]
  }],
  "stream": false,
  "max_tokens": 1024
}
```

**`image_url.url` 支持三种格式**：

| 格式 | 示例 | 条件 |
|------|------|------|
| 远程 URL | `https://example.com/photo.jpg` | 无需额外配置 |
| Base64 | `data:image/png;base64,iVBOR...` 或纯 base64 | 无需额外配置 |
| 本地文件 | `file://photo.jpg` | 需 `--media-path` 指定根目录 |

**支持的图片格式**: jpeg、png、tga、bmp、gif（通过 stb_image）

**其他媒体类型**：
- `type: "input_audio"` → `input_audio.data` / `input_audio.url`（mp3、wav、flac）
- `type: "input_video"` → `input_video.data` / `input_video.url`（ffmpeg 支持格式）

### 3.3 响应结构

```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "...",
      "reasoning_content": "..."   // reasoning 模式
    }
  }],
  "usage": {
    "completion_tokens": 48,
    "prompt_tokens": 44,
    "total_tokens": 92,
    "prompt_tokens_details": {"cached_tokens": 0}
  },
  "timings": {
    "prompt_n": 1,
    "prompt_ms": 30.958,
    "predicted_n": 35,
    "predicted_ms": 661.064,
    "predicted_per_second": 52.94
  }
}
```

---

## 4. 已实现 vs 可优化

### 4.1 已正确实现

| 功能 | 实现方式 | 状态 |
|------|---------|------|
| 子进程生命周期 | `subprocess.Popen` + `atexit` | 正确 |
| 健康检查 | `GET /health` → `status: "ok"` | 正确 |
| 模型预热 | `POST /v1/chat/completions` with `max_tokens=1` | 正确 |
| 图片 Data URI | `data:image/...;base64,...` | 正确 |
| 异步 API | `AsyncOpenAI` | 正确 |
| 错误处理 | 401/403 禁用后端，5xx 重试 | 正确 |
| 启动参数 | 完整覆盖核心参数 | 基本正确 |

### 4.2 参数核对发现的问题（已全部修复）

| 参数 | 当前值 | 当前默认值 | 建议 |
|------|--------|-----------|------|
| `--repeat-penalty` | 1.0 | 1.0 | 正确，无需改 |
| `--presence-penalty` | 1.0 | 0.0 | 已从 1.5 降至 1.0，VLM 任务稳定 |
| `--top-k` | 20 | 40 | 偏保守，合理 |
| `--top-p` | 0.8 | 0.95 | 偏保守，合理 |
| `-np 1` | 1 | auto | 无并发需求，合理 |
| `--no-webui` | 有 | 无 | 生产环境合理 |
| `--image-max-tokens 2048` | 已添加 | 模型默认 | 防大图撑爆 context |

### 4.2.1 代理穿透问题（2026-09-17 已修复）

**现象**：llama-server 启动后健康检查超时 180s，但直连 curl 正常。

**根因**：`requests` 库（健康检查）和 `httpx/AsyncOpenAI`（API 调用）默认走系统 HTTP 代理。`127.0.0.1:11433` 从代理走不通。

**修复方案**：

| 层 | 文件 | 修复 |
|------|------|------|
| `requests` 健康检查 | `llama_launcher.py` | 所有 `requests.get/post` 加 `proxies={"http": None}` |
| `httpx` API 调用 | `main.py` | 进程启动前设 `os.environ["NO_PROXY"] = "localhost,127.0.0.1"` |

**验证**：修复后 llama-server 启动时间从 180s（超时）降至 ~7s。

### 4.3 未利用的新特性

| 特性 | 说明 | 在 VLM-mcp 中的价值 |
|------|------|-------------------|
| **Reasoning / Thinking** | `reasoning_effort` + `reasoning_format` | 对复杂图片分析可开启思考链 |
| **`--image-max-tokens`** | 限制图片最大 token 数 | 防止大图撑爆 context |
| **`--media-path`** | 本地文件目录 | 当前只用 base64，可扩展支持文件路径 |
| **`--metrics`** | Prometheus 指标 | 生产监控 |
| **`--jinja`** | Jinja 模板引擎 | 默认已启用，Function Calling 需要 |
| **`--cache-ram`** | 模型缓存（MiB） | 多模型切换时加速 |
| **`--ctx-checkpoints`** | Context 检查点 | 多轮对话时节省 KV cache |
| **`--api-key`** | API 鉴权 | 生产安全 |
| **`--tools`** | 内置 Agent 工具 | 可让 LLM 直接读写文件/执行 shell |
| **`--mcp-servers-config`** | MCP Server 代理 | 扩展 llama.cpp 的工具能力 |

### 4.4 图片相关参数

| 参数 | 当前值 | 默认值 | 说明 |
|------|--------|--------|------|
| `--image-min-tokens 1024` | 1024 | 模型默认 | 动态分辨率模型的最小 token 数 |
| `--image-max-tokens` | 未设置 | 模型默认 | 限制图片最大 token，防止大图超限 |
| `--mtmd-batch-max-tokens` | 未设置 | 1024 | 图片编码时每批最大 token 数 |

**建议**: 如果使用动态分辨率 VLM 模型（如 Qwen2-VL、Gemma 3），最好显式设置 `--image-max-tokens` 防止大分辨率图片耗尽 context。

---

## 5. 关键参数速查

### 5.1 模型加载（VLM 相关）

| 参数 | 说明 |
|------|------|
| `-m, --model` | 文本模型 GGUF 路径 |
| `-mm, --mmproj` | 视觉 projector GGUF 路径 |
| `-hf, --hf-repo` | HuggingFace 仓库，自动下载模型+mmproj |
| `--mmproj-offload` / `--no-mmproj-offload` | projector 是否 GPU 加速（默认 on） |
| `--image-min-tokens N` | 图片最小 token 数 |
| `--image-max-tokens N` | 图片最大 token 数 |
| `--video-fps N` | 视频帧率（默认 4.0） |
| `--media-path PATH` | 本地媒体文件根目录 |

### 5.2 推理参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-c, --ctx-size` | 模型默认 | 上下文窗口 |
| `-n, --predict` | -1(无限) | 最大生成 token |
| `-np, --parallel` | auto | 并发 slot 数 |
| `--temp` | 0.80 | 温度 |
| `--top-k` | 40 | Top-K 采样 |
| `--top-p` | 0.95 | Top-P 采样 |
| `--min-p` | 0.05 | Min-P 采样 |
| `-fa, --flash-attn` | auto | Flash Attention |

### 5.3 服务配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--host` | 127.0.0.1 | 监听地址 |
| `--port` | 8080 | 监听端口 |
| `--api-key` | 无 | API 鉴权 |
| `--api-prefix` | 空 | API 路径前缀 |
| `--cors-origins` | `*` | CORS 来源 |
| `--metrics` | disabled | Prometheus 指标 |
| `--jinja` | enabled | Jinja 模板（Function Calling 需要） |

### 5.4 Reasoning / Thinking

| 参数 | 说明 |
|------|------|
| `--reasoning [on\|off\|auto]` | 是否启用 reasoning |
| `--reasoning-effort LEVEL` | 思考深度: minimal/low/medium/high/xhigh/max |
| `--reasoning-budget N` | token 预算（-1 无限，0 立即结束） |
| `--reasoning-format FORMAT` | 输出格式: none/deepseek/deepseek-legacy |

### 5.5 Agent 模式

| 参数 | 说明 |
|------|------|
| `--agent` | 一键启用所有 agent 功能 |
| `--tools all` | 内置工具: read_file, write_file, grep_search, exec_shell_command 等 |
| `--mcp-servers-config` | Cursor 兼容 MCP server 配置 |
| `--tools-runtime` | 隔离运行环境: docker/ssh |

---

## 6. 结论与建议

### 6.1 当前实现评估

VLM-mcp 对 llama.cpp server 的集成**整体正确、结构清晰**。子进程管理、健康检查、图片 Data URI 传参、异步 API 调用均符合 llama.cpp server 的最佳实践。

### 6.2 建议优化项

1. ✅ **显式设置 `--image-max-tokens`**：已设 `2048`，防大图撑爆 context
2. ✅ **降低 `presence-penalty`**：已从 1.5 降至 1.0
3. ✅ **KV cache 量化**：`-ctk q8_0 -ctv q8_0` 节省 ~30% VRAM
4. ⬜ **生产环境加 `--api-key`**：当前无鉴权
5. ⬜ **Reasoning 可选**：对复杂图片分析场景，可开放 `reasoning_effort` 参数
6. ⬜ **监控**：`--metrics` 暴露 Prometheus 指标，便于观察推理性能
7. ✅ **代理穿透**：`requests` 加 `proxies={"http": None}`，进程设 `NO_PROXY`

### 6.3 多模态模型推荐

从 HuggingFace ggml-org 集合中选择: https://huggingface.co/collections/ggml-org/multimodal-ggufs-68244e01ff1f39e5bebeeedc

常用 VLM 模型（支持 `-hf` 一行下载）：
- `ggml-org/gemma-3-4b-it-GGUF` — Google Gemma 3 视觉模型
- `ggml-org/Qwen2-VL-7B-Instruct-GGUF` — 通义千问视觉
- `ggml-org/llava-v1.6-34b-GGUF` — LLaVA 经典模型

### 参考来源

- [llama.cpp Server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [llama.cpp Multimodal 文档](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md)
- [llama.cpp Server Changelog](https://github.com/ggml-org/llama.cpp/issues/9291)
- 项目源码: `llama_launcher.py`, `providers/openai_compat.py`, `config.py`, `server.py`