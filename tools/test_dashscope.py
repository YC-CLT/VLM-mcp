"""直接测试 DashScope API 是否有效"""
import json
from pathlib import Path
from openai import OpenAI

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    cfg = json.load(f)

backend = cfg["backends"]["qwen-vl"]
client = OpenAI(
    base_url=backend["base_url"],
    api_key=backend["api_key"],
)

print(f"base_url: {backend['base_url']}")
print(f"model: {backend['model_name']}")
print()

try:
    resp = client.chat.completions.create(
        model=backend["model_name"],
        messages=[{"role": "user", "content": "回复 OK"}],
        max_tokens=10,
    )
    print("OK")
    print(f"   response: {resp.choices[0].message.content}")
    print(f"   model: {resp.model}")
    print(f"   tokens: {resp.usage.total_tokens}")
except Exception as e:
    print(f"FAIL: {e}")
    status = getattr(getattr(e, "response", None), "status_code", None)
    if status:
        print(f"   HTTP status: {status}")
    body = getattr(getattr(e, "response", None), "text", None)
    if body:
        print(f"   body: {body}")