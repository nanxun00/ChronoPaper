"""检查 MemOS MCP 服务实际暴露的工具。"""
import requests
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

# List tools
r = requests.post(url, headers=headers, json={
    "jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tools/list", "params": {},
}, timeout=15)
tools = r.json().get("result", {}).get("tools", [])
print("=== MemOS MCP Tools ===")
for t in tools:
    print(f"  {t['name']}: {t.get('description', '')[:100]}")
    print(f"    params: {list(t.get('inputSchema', {}).get('properties', {}).keys())}")

# Try add_message
print("\n=== Try add_message ===")
r2 = requests.post(url, headers=headers, json={
    "jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tools/call",
    "params": {"name": "add_message", "arguments": {
        "conversation_first_message": "test_session_001",
        "messages": [{"role": "user", "content": "我的研究方向是自然语言处理"}],
    }},
}, timeout=30)
print(f"Status: {r2.status_code}")
print(f"Response: {r2.text[:500]}")

# Try search_memory
print("\n=== Try search_memory ===")
r3 = requests.post(url, headers=headers, json={
    "jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tools/call",
    "params": {"name": "search_memory", "arguments": {
        "query": "研究方向",
        "conversation_first_message": "test_session_001",
        "top_k": 5,
    }},
}, timeout=30)
print(f"Status: {r3.status_code}")
print(f"Response: {r3.text[:500]}")
