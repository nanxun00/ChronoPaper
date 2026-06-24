"""MemOS 长期记忆测试脚本。

测试流程：
1. 发送含关键信息的消息（开启记忆）
2. 查看长期记忆是否存储
3. 刷新页面后询问之前内容，验证记忆召回
"""
import requests
import time

BASE = "http://localhost:8081/api/v1"
USER_ID = "admin"

def chat(message: str, enable_memory: bool = True) -> str:
    """发送聊天请求。"""
    resp = requests.post(f"{BASE}/chat", json={
        "message": message,
        "meta": {
            "enable_memory": enable_memory,
            "stream": False,
        },
        "user_id": USER_ID,
    }, timeout=120)
    data = resp.json()
    content = data.get("content", "") or data.get("message", {}).get("content", "")
    return content

def get_memories() -> dict:
    """获取所有长期记忆。"""
    resp = requests.get(f"{BASE}/chat/memories", params={"user_id": USER_ID}, timeout=15)
    return resp.json()

def main():
    print("=" * 60)
    print("MemOS 长期记忆测试")
    print("=" * 60)

    # 测试 1：发送含关键信息的消息
    print("\n[测试 1] 发送含关键信息的消息（开启记忆）...")
    reply = chat("我的研究方向是自然语言处理和知识图谱，我特别关注大语言模型的应用。")
    print(f"  回复：{reply[:200]}")

    # 等待 MemOS 异步存储
    time.sleep(3)

    # 测试 2：查看长期记忆
    print("\n[测试 2] 查看长期记忆存储...")
    memories = get_memories()
    print(f"  结果：{memories}")

    # 测试 3：再聊几轮
    print("\n[测试 3] 继续聊天（覆盖上下文）...")
    for msg in ["Transformer 和 BERT 有什么区别？", "GPT-3 有多少参数？", "解释一下 attention 机制"]:
        reply = chat(msg, enable_memory=True)
        print(f"  Q: {msg}")
        print(f"  A: {reply[:150]}")
        time.sleep(2)

    # 测试 4：询问之前的信息
    print("\n[测试 4] 询问之前的关键信息（验证记忆召回）...")
    reply = chat("我之前说过我的研究方向是什么？", enable_memory=True)
    print(f"  回复：{reply[:300]}")

    # 测试 5：关闭记忆后询问
    print("\n[测试 5] 关闭记忆开关后询问（验证硬隔离）...")
    reply = chat("我之前说过我的研究方向是什么？", enable_memory=False)
    print(f"  回复：{reply[:300]}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
