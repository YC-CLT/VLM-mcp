"""测试 DashScope 图片请求耗时"""
import json, time, base64
from pathlib import Path
from openai import OpenAI

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    cfg = json.load(f)

backend = cfg["backends"]["qwen-vl"]
client = OpenAI(base_url=backend["base_url"], api_key=backend["api_key"])

img_path = PROJECT_ROOT / "tests" / "imgs" / "what.png"
with open(img_path, "rb") as f:
    img_bytes = f.read()
img_b64 = base64.b64encode(img_bytes).decode()
data_uri = f"data:image/png;base64,{img_b64}"

print(f"图片大小: {len(img_bytes)/1024:.1f} KB, base64: {len(img_b64)/1024:.1f} KB")
print(f"模型: {backend['model_name']}")
print()

t0 = time.time()
r = client.chat.completions.create(
    model=backend["model_name"],
    messages=[{"role": "user", "content": "回复 OK"}],
    max_tokens=10,
)
t1 = time.time()
print(f"纯文本: {t1-t0:.1f}s")

t0 = time.time()
r = client.chat.completions.create(
    model=backend["model_name"],
    messages=[{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": data_uri}},
            {"type": "text", "text": "用一句话描述这张图片"},
        ],
    }],
    max_tokens=100,
)
t1 = time.time()
print(f"图片+简短描述: {t1-t0:.1f}s, tokens={r.usage.total_tokens}")
print(f"  响应: {r.choices[0].message.content[:80]}...")
print(f"  模型: {r.model}")