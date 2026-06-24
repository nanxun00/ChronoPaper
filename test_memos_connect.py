import requests, json, uuid

url = "https://mcp.api-inference.modelscope.net/da90181d7d554d/mcp"

# Step 1: initialize
headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
payload = {
    "jsonrpc": "2.0",
    "id": str(uuid.uuid4()),
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "ChronoPaper", "version": "1.0.0"},
    },
}
resp = requests.post(url, headers=headers, json=payload, timeout=15)
sid = resp.headers.get("Mcp-Session-Id", "")
print("Session ID:", sid)

# Step 2: initialized notification
headers["Mcp-Session-Id"] = sid
requests.post(url, headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, timeout=10)

# Step 3: tools/list
r = requests.post(url, headers=headers, json={"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tools/list", "params": {}}, timeout=15)
tools = r.json()["result"]["tools"]
for t in tools:
    name = t["name"]
    desc = t["description"][:120]
    schema = json.dumps(t.get("inputSchema", {}), ensure_ascii=False)[:300]
    print(f"Tool: {name}")
    print(f"  Desc: {desc}")
    print(f"  Schema: {schema}")
    print()
