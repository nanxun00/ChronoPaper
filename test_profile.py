"""检查 MemOS get_user_profile 原始返回结构。"""
import requests
import uuid
import json

url = "https://mcp.api-inference.modelscope.net/da90181d7d554d/mcp"
token = "ms-716699a0-5afc-4088-9729-80e60c8ad565"

headers = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "Authorization": f"Bearer {token}",
}

resp = requests.post(url, headers=headers, json={
    "jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "initialize",
    "params": {"protocolVersion": "2025-03-26", "capabilities": {},
               "clientInfo": {"name": "ChronoPaper", "version": "1.0.0"}},
}, timeout=15)
mcp_sid = resp.headers.get("Mcp-Session-Id", "")
if mcp_sid:
    headers["Mcp-Session-Id"] = mcp_sid

requests.post(url, headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, timeout=10)

r = requests.post(url, headers=headers, json={
    "jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tools/call",
    "params": {"name": "get_user_profile", "arguments": {
        "include_preference": True, "include_tool_memory": True,
    }},
}, timeout=30)

data = r.json()
text = data.get("result", {}).get("content", [{}])[0].get("text", "")
parsed = json.loads(text) if text else {}

# 打印完整结构
print(json.dumps(parsed, ensure_ascii=False, indent=2)[:5000])
