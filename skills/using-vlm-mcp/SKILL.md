---
name: using-vlm-mcp
description: Use when user provides images requiring VLM-based processing via VLM-mcp
---

# Using VLM-MCP

## Overview

通过 VLM-mcp MCP 工具对图片进行单次分析、模板处理或多轮对话。核心原则：无会话必传图，有会话可追问，用完必须关。

## 触发场景

用户提供图片并要求：描述、分析、OCR 提取文字、图表解读、翻译图中文字、基于图片问答。

**OCR 优先用 `ocr_image`**。**不要**优先用 `analyze_image` + `template: "ocr"` ，效果不好再换。

**不用此 skill 的场景：** 纯文本分析（无图片）、非 VLM-mcp 工具的图片处理。

## 快速参考

调用方式：`run_mcp(server_name="vlm-mcp", tool_name="工具名", args={...})`。
`image` 支持三种格式：**本地绝对路径**（如 `D:/images/photo.png`）、**URL**（`https://...`）、**base64 data URI**。

| 工具 | 操作 | args |
|------|------|------|
| `ocr_image` | 本地 OCR | `image` → `[{text, box, confidence}, ...]` |
| `analyze_image` | 自由描述 | `image`, `prompt` |
| `analyze_image` | 模板描述 | `image`, `template: "describe"` |
| `analyze_image` | 模板 OCR | `image`, `template: "ocr"` |
| `analyze_image` | 图表解读 | `image`, `template: "chart"` |
| `analyze_image` | 翻译图中文字 | `image`, `template: "translate"`, `params: {target_lang}` |
| `analyze_image` | 图片问答 | `image`, `template: "qa"`, `params: {question}` |
| `analyze_image` | 指定后端 | `image`, `prompt`, `backend` |
| `create_session` | 创建会话 | `backend`（可选）→ `{session_id}` |
| `close_session` | 关闭会话 | `session_id` |
| `list_sessions` | 活跃会话 | 无 |
| `list_backends_tool` | 可用后端 | 无 |
| `list_templates` | 可用模板 | 无 |

`analyze_image` 返回：`{text, model, tokens_used, cache_hit, session_id}`。

## 使用模式

### 模板分析
先用 `list_templates` 查看可用模板，再按上方快速参考表调用（独立调用，无需 session）。

### 多轮对话
```python
s = run_mcp("vlm-mcp", "create_session", args={"backend": "dashscope"})  # 可选 backend
sid = s["session_id"]
run_mcp("vlm-mcp", "analyze_image", args={"image": "doc.png", "prompt": "总结", "session_id": sid})
run_mcp("vlm-mcp", "analyze_image", args={"prompt": "第三节？", "session_id": sid})        # 追问可不传图
run_mcp("vlm-mcp", "close_session", args={"session_id": sid})                              # 用完必须关
```

## 常见错误

| 错误 | 现象 | 正确做法 |
|------|------|----------|
| 无会话忘传 `image` | `INVALID_PARAMS`: `image is required` | 无会话时 `image` 必传 |
| 不关会话 | 占槽位（每后端最多 5 个），后续创建报 `SESSION_FULL` | 用完 `close_session`；若已占满，`list_sessions` 查孤儿 → 逐一 `close_session` |
| 同时传 `template` 和 `prompt` | `template` 优先，`prompt` 被忽略 | 只传其中一个 |
| 会话内换后端 | `SESSION_BACKEND_MISMATCH` | 新建 session 换后端 |
| `image` 用相对路径 | `IMAGE_NOT_FOUND` | 用绝对路径、URL 或 base64 |
| 用 `analyze_image` + `template: "ocr"` 做简单提取 | 浪费在线 API 额度、延迟高 | 优先用 `ocr_image` |
| 模板名拼错 | `TEMPLATE_NOT_FOUND` | `list_templates` 查看可用模板名 |
| 忘传模板必填参数 | `INVALID_PARAMS`: `Missing required param` | `list_templates` 查看模板所需参数 |

## Red Flags

- [ ] 创建了 session 但用完没关？→ 调 `close_session`
- [ ] `image` 用了相对路径？→ 换绝对路径 / URL / base64
- [ ] 同时传了 `template` 和 `prompt`？→ 只传一个，`template` 优先