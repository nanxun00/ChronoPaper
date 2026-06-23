"""Quick MemOS MCP smoke test after client fixes."""
from src.integrations.memos import MemosMCPClient

URL = "https://mcp.api-inference.modelscope.net/da90181d7d554d/mcp"
client = MemosMCPClient(URL, "")
tools = client.connect()
print("tools:", [t["name"] for t in tools])

profile = client.call_tool(
    "get_user_profile",
    {"include_preference": True, "include_tool_memory": False},
)
print("profile ok:", profile.ok, profile.error[:120] if profile.error else "")
print("profile content:", profile.content[:400])

search = client.call_tool(
    "search_memory",
    {"query": "research", "conversation_first_message": "test-session-1"},
)
print("search ok:", search.ok, search.error[:120] if search.error else "")
print("search content:", search.content[:400])

listed = client.list_all_memories("admin", "", 100)
print("list ok:", listed.ok, listed.error[:120] if listed.error else "")
print("list content:", listed.content[:400])
