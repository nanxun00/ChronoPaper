"""测试 MemOS 不同方式获取记忆。"""
import requests
import json
import uuid

url = "https://mcp.api-inference.modelscope.net/da90181d7d554d/mcp"
token = "ms-716699a0-5afc-4088-9729-80e60c8ad565"

headers = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "Authorization": f"Bearer {token}",
}

# Initialize
resp = requests.post(url, headers=headers, json={
    "jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "initialize",
    "params": {"protocolVersion": "2025-03-26", "capabilities": {},
               "clientInfo": {"name": "ChronoPaper", "version": "1.0.0"}},
}, timeout=15)
mcp_sid = resp.headers.get("Mcp-Session-Id", "")
if mcp_sid:
    headers["Mcp-Session-Id"] = mcp_sid

requests.post(url, headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, timeout=10)

# 1. get_user_profile (full)
print("=== get_user_profile (full) ===")
r = requests.post(url, headers=headers, json={
    "jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tools/call",
    "params": {"name": "get_user_profile", "arguments": {
        "include_preference": True, "include_tool_memory": True,
    }},
}, timeout=30)
data = r.json()
text = data.get("result", {}).get("content", [{}])[0].get("text", "")
parsed = json.loads(text) if text else {}
print(json.dumps(parsed, ensure_ascii=False, indent=2)[:3000])

# 2. search_memory with broad query
print("\n=== search_memory (broad query) ===")
r2 = requests.post(url, headers=headers, json={
    "jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tools/call",
    "params": {"name": "search_memory", "arguments": {
        "query": "闫焕根 苹果 张凯富 偏好",
        "conversation_first_message": "default",
        "top_k": 20,
    }},
}, timeout=30)
data2 = r2.json()
text2 = data2.get("result", {}).get("content", [{}])[0].get("text", "")
print(text2[:2000])

# 3. search_memory with empty-ish query
print("\n=== search_memory (single char query) ===")
r3 = requests.post(url, headers=headers, json={
    "jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tools/call",
    "params": {"name": "search_memory", "arguments": {
        "query": " ",
        "conversation_first_message": "default",
        "top_k": 20,
    }},
}, timeout=30)
data3 = r3.json()
text3 = data3.get("result", {}).get("content", [{}])[0].get("text", "")
print(text3[:2000])
