# llama 生态调研：作为后端推理引擎的用法

> 调研日期: 2026-08-21
> 调研工具: wet-mcp (download + extract), 原生 websearch

---

## 背景

需要将 llama 系列项目作为 VLM-mcp 的后端推理引擎之一。调研覆盖三个核心项目：**llama.cpp**（底层引擎）、**Ollama**（用户友好封装）、**llama-cpp-python**（Python 绑定），重点关注 API 用法和集成方式。

---

## 核心发现

### 一、三者关系与定位

```
llama.cpp (C/C++ 引擎)
  ├── llama-cpp-python (Python 绑定，直接调用 C API)
  │     └── 自带 OpenAI 兼容 HTTP Server
  ├── llama-server (llama.cpp 内置 HTTP Server)
  │     └── OpenAI + Anthropic 双协议兼容
  └── Ollama (独立项目，底层基于 llama.cpp)
        └── 自有 REST API + OpenAI 兼容 API
```

| 维度 | llama.cpp (server) | Ollama | llama-cpp-python |
|------|-------------------|--------|-----------------|
| **语言** | C/C++ | Go | Python |
| **Stars** | 125k | 极多 | 9k+ |
| **安装难度** | 需编译 | 一键安装脚本 | `pip install` |
| **模型管理** | 手动下载 / `-hf` 自动拉取 | 内置 pull/push/create | 手动下载 / `from_pretrained` |
| **API 协议** | OpenAI + Anthropic | 自有 REST + OpenAI 兼容 | OpenAI 兼容 |
| **默认端口** | 8080 | 11434 | 8000 |
| **GPU 支持** | CUDA/Metal/Vulkan/HIP/SYCL | 同 llama.cpp | 同 llama.cpp + 预编译 wheel |
| **多模态** | 原生支持 | 支持 (llava 等) | 支持 (llava 等) |
| **Function Calling** | 原生支持 | 支持 | 原生支持 |
| **流式输出** | SSE | SSE | SSE |
| **并发** | Continuous Batching | 有限 | 有限 |
| **适合场景** | 生产级高并发 | 开发/个人使用 | Python 项目内嵌 |

---

### 二、llama.cpp Server — 最推荐作为后端

**仓库**: [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp)

#### 2.1 快速启动

```bash
# 方式1: 一行拉起，自动从 HuggingFace 下载模型
llama serve -hf ggml-org/Qwen3.5-0.8B-GGUF

# 方式2: 指定本地模型文件
llama serve -m ./models/llama-3-8b-q4.gguf

# 方式3: 带 GPU 加速
llama serve -m ./models/llama-3-8b-q4.gguf -ngl 99

# 方式4: 生产级配置
llama serve \
  -m ./models/llama-3-8b-q4.gguf \
  -ngl 99 \
  -c 8192 \           # context size
  -np 4 \             # 并发 slot 数
  --host 0.0.0.0 \    # 监听所有网卡
  --port 8080 \
  --api-key sk-xxx     # API 鉴权
```

#### 2.2 OpenAI 兼容 API（核心接口）

Server 默认在 `http://localhost:8080` 提供以下端点：

| 端点 | 说明 |
|------|------|
| `GET /health` | 健康检查 |
| `GET /v1/models` | 模型信息 |
| `POST /v1/completions` | OpenAI 兼容文本补全 |
| `POST /v1/chat/completions` | OpenAI 兼容对话补全 |
| `POST /v1/chat/completions/control` | 实时控制推理（如提前结束 reasoning） |
| `POST /v1/responses` | OpenAI 兼容 Responses API |
| `POST /v1/embeddings` | OpenAI 兼容嵌入 |
| `POST /completion` | llama.cpp 原生补全（更多参数） |
| `POST /tokenize` | 分词 |
| `POST /embeddings` | 非 OAI 兼容嵌入 |

**关键特性**:
- **Anthropic Messages API 兼容**: 也支持 Anthropic 协议
- **内置 Web UI**: 访问 `http://localhost:8080` 即可使用
- **MCP 工具**: 内置 `read_file`, `write_file`, `exec_shell_command` 等 agent 工具（`--tools all`）
- **MCP Server 代理**: 支持 Cursor 兼容的 MCP server 配置（`--mcp-servers-config`）
- **多模态**: 支持图片、音频、视频输入
- **Function Calling**: 原生 tool call 支持
- **JSON Schema**: 约束输出格式
- **Reasoning**: 支持 DeepSeek 风格 reasoning_content
- **Continuous Batching**: 多用户并发推理
- **API Key 鉴权**: `--api-key` 或 `--api-key-file`

#### 2.3 Python 客户端示例

```python
import openai

client = openai.OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="sk-no-key-required"
)

# Chat Completion
response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]
)
print(response.choices[0].message.content)

# 多模态（图片理解）
response = client.chat.completions.create(
    model="gpt-4-vision",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "What's in this image?"},
            {"type": "image_url", "image_url": {"url": "https://example.com/photo.jpg"}}
        ]
    }]
)
```

#### 2.4 curl 示例

```bash
# 对话补全
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer no-key" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [
      {"role": "user", "content": "Say hello"}
    ]
  }'

# 流式输出
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Tell me a story"}],
    "stream": true
  }'
```

---

### 三、Ollama — 最易用的封装

**仓库**: [ollama/ollama](https://github.com/ollama/ollama)

#### 3.1 安装 & 启动

```bash
# Linux/macOS
curl -fsSL https://ollama.com/install.sh | sh

# Windows
irm https://ollama.com/install.ps1 | iex

# 拉取并运行模型
ollama run llama3.2
ollama pull gemma4
```

#### 3.2 自有 REST API（localhost:11434）

| 端点 | 说明 |
|------|------|
| `POST /api/generate` | 文本生成（自有格式） |
| `POST /api/chat` | 对话补全（自有格式） |
| `POST /api/embed` / `POST /api/embeddings` | 嵌入向量 |
| `GET /api/tags` | 列出本地模型 |
| `POST /api/show` | 模型详情 |
| `POST /api/pull` | 拉取模型 |
| `POST /api/push` | 推送模型 |
| `POST /api/create` | 创建模型 |
| `POST /api/copy` | 复制模型 |
| `DELETE /api/delete` | 删除模型 |
| `GET /api/ps` | 运行中的模型 |
| `GET /api/version` | 版本 |

#### 3.3 自有 API 调用示例

```bash
# /api/chat (自有格式)
curl http://localhost:11434/api/chat -d '{
  "model": "llama3.2",
  "messages": [{"role": "user", "content": "Why is the sky blue?"}],
  "stream": false
}'

# /api/generate (自有格式)
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.2",
  "prompt": "Why is the sky blue?",
  "stream": false
}'
```

#### 3.4 多模态 / 图片

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "llava",
  "prompt": "What is in this picture?",
  "stream": false,
  "images": ["<base64-encoded-image>"]
}'
```

#### 3.5 Structured Output / JSON Mode

```bash
curl http://localhost:11434/api/chat -d '{
  "model": "llama3.1",
  "messages": [{"role": "user", "content": "Return JSON with age and availability"}],
  "stream": false,
  "format": {
    "type": "object",
    "properties": {
      "age": {"type": "integer"},
      "available": {"type": "boolean"}
    },
    "required": ["age", "available"]
  }
}'
```

#### 3.6 与 llama.cpp 的对比

| 特性 | Ollama | llama.cpp server |
|------|--------|-----------------|
| 安装 | 一键脚本 | 需编译 |
| 模型管理 | 内置 pull/push | 手动或 `-hf` 自动 |
| API 协议 | 自有 + OpenAI 兼容 | OpenAI + Anthropic |
| 模型库 | ollama.com/library | 无（需 HuggingFace） |
| 并发 | 较弱 | Continuous Batching |
| 生产就绪 | 个人/开发 | 生产级 |
| Agent 工具 | 无 | 内置 MCP 工具 |

---

### 四、llama-cpp-python — Python 项目内嵌方案

**仓库**: [abetlen/llama-cpp-python](https://github.com/abetlen/llama-cpp-python)

#### 4.1 安装

```bash
# CPU 版本
pip install llama-cpp-python

# CUDA 预编译版本
pip install llama-cpp-python \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121

# Metal (Apple Silicon) 预编译
pip install llama-cpp-python \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/metal

# 从源码编译（自定义后端）
CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python
```

#### 4.2 内嵌 Python 用法（进程内推理）

```python
from llama_cpp import Llama

# 加载模型
llm = Llama(
    model_path="./models/llama-3-8b-q4.gguf",
    n_ctx=2048,        # context window
    n_gpu_layers=-1,   # -1 = 全部 GPU 加速
    verbose=False
)

# 文本补全
output = llm(
    "Q: Name the planets in the solar system? A: ",
    max_tokens=32,
    stop=["Q:", "\n"],
    echo=True
)
print(output["choices"][0]["text"])

# Chat Completion
response = llm.create_chat_completion(
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]
)
print(response["choices"][0]["message"]["content"])

# JSON Schema 约束输出
response = llm.create_chat_completion(
    messages=[
        {"role": "user", "content": "Who won the world series in 2020"}
    ],
    response_format={
        "type": "json_object",
        "schema": {
            "type": "object",
            "properties": {"team_name": {"type": "string"}},
            "required": ["team_name"]
        }
    }
)

# Function Calling
response = llm.create_chat_completion(
    messages=[{"role": "user", "content": "Extract: Jason is 25 years old"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "UserDetail",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"}
                },
                "required": ["name", "age"]
            }
        }
    }],
    tool_choice={"type": "function", "function": {"name": "UserDetail"}}
)

# 从 HuggingFace 直接拉取
llm = Llama.from_pretrained(
    repo_id="lmstudio-community/Qwen3.5-0.8B-GGUF",
    filename="*Q8_0.gguf",
    verbose=False
)
```

#### 4.3 多模态用法

```python
from llama_cpp import Llama
from llama_cpp.llama_chat_format import Llava15ChatHandler

chat_handler = Llava15ChatHandler(clip_model_path="path/to/mmproj.bin")
llm = Llama(
    model_path="./path/to/llava-model.gguf",
    chat_handler=chat_handler,
    n_ctx=2048
)

llm.create_chat_completion(
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "What's in this image?"},
            {"type": "image_url", "image_url": {"url": "https://example.com/photo.jpg"}}
        ]
    }]
)
```

#### 4.4 自带 OpenAI 兼容 Server

```bash
# 启动 OpenAI 兼容 Server
python -m llama_cpp.server \
  --model ./models/llama-3-8b-q4.gguf \
  --n_gpu_layers -1 \
  --host 0.0.0.0 \
  --port 8000
```

然后使用标准 OpenAI SDK 连接：
```python
import openai
client = openai.OpenAI(base_url="http://localhost:8000/v1", api_key="sk-xxx")
```

---

## 结论：推荐方案

### 作为 VLM-mcp 后端，按优先级排序：

| 优先级 | 方案 | 原因 |
|--------|------|------|
| **1** | **llama.cpp server** | 生产级，OpenAI + Anthropic 双协议，Continuous Batching，MCP 工具内置，多模态原生支持，API Key 鉴权 |
| 2 | llama-cpp-python 内嵌 | 如果已有 Python 进程，可避免额外 HTTP 开销，但并发弱于 server 模式 |
| 3 | Ollama | 开发体验最好，模型管理方便，但并发和生产能力不如 llama.cpp server |

### 统一接入方案

由于三者都支持 OpenAI 兼容 API，可以**统一用 OpenAI SDK 客户端**接入：
```python
import openai

class LlamaBackend:
    def __init__(self, base_url: str, api_key: str = "sk-no-key-required"):
        self.client = openai.OpenAI(base_url=base_url, api_key=api_key)

    def chat(self, messages, **kwargs):
        return self.client.chat.completions.create(
            model="gpt-3.5-turbo",  # 任意占位名
            messages=messages,
            **kwargs
        )

# 切换后端只需改 base_url
llama_cpp_backend = LlamaBackend("http://localhost:8080/v1")
ollama_backend = LlamaBackend("http://localhost:11434/v1")
```

---

## 参考来源

- [llama.cpp GitHub](https://github.com/ggml-org/llama.cpp) — 底层 C/C++ 推理引擎
- [llama.cpp Server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) — OpenAI 兼容 Server API 文档
- [Ollama GitHub](https://github.com/ollama/ollama) — 用户友好 LLM 运行工具
- [Ollama API 文档](https://github.com/ollama/ollama/blob/main/docs/api.md) — 自有 REST API
- [llama-cpp-python GitHub](https://github.com/abetlen/llama-cpp-python) — Python 绑定 + OpenAI 兼容 Server
- [llama-cpp-python 文档](https://llama-cpp-python.readthedocs.io/en/latest/) — 完整 API 参考