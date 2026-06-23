"""直接测试 MemOS MCP API，查看实际工具列表和返回格式。"""
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

# 1. Initialize
init_payload = {
    "jsonrpc": "2.0",
    "id": str(uuid.uuid4()),
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "ChronoPaper", "version": "1.0.0"},
    },
}
resp = requests.post(url, headers=headers, json=init_payload, timeout=15)
print("=== Initialize ===")
print(f"Status: {resp.status_code}")
mcp_sid = resp.headers.get("Mcp-Session-Id", "")
print(f"Mcp-Session-Id: {mcp_sid[:50]}")

if mcp_sid:
    headers["Mcp-Session-Id"] = mcp_sid

# 2. Initialized notification
requests.post(url, headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, timeout=10)

# 3. List tools
tools_resp = requests.post(url, headers=headers, json={
    "jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tools/list", "params": {}
}, timeout=15)
print("\n=== Tools ===")
tools = tools_resp.json().get("result", {}).get("tools", [])
for t in tools:
    print(f"  Name: {t['name']}")
    print(f"  Desc: {t.get('description', '')[:120]}")
    schema = t.get("inputSchema", {})
    print(f"  Schema: {json.dumps(schema, ensure_ascii=False)[:300]}")
    print()

# 4. Try get_user_profile
print("=== get_user_profile ===")
profile_resp = requests.post(url, headers=headers, json={
    "jsonrpc": "2.0", "id": str(uuid.uuid4()),
    "method": "tools/call",
    "params": {
        "name": "get_user_profile",
        "arguments": {"include_preference": True, "include_tool_memory": False},
    }
}, timeout=30)
print(f"Status: {profile_resp.status_code}")
profile_data = profile_resp.json()
print(json.dumps(profile_data, ensure_ascii=False, indent=2)[:2000])

# 5. Try search_memory with empty query
print("\n=== search_memory (empty query) ===")
search_resp = requests.post(url, headers=headers, json={
    "jsonrpc": "2.0", "id": str(uuid.uuid4()),
    "method": "tools/call",
    "params": {
        "name": "search_memory",
        "arguments": {"query": " ", "top_k": 10},
    }
}, timeout=30)
print(f"Status: {search_resp.status_code}")
search_data = search_resp.json()
print(json.dumps(search_data, ensure_ascii=False, indent=2)[:2000])
