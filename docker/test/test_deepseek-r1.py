from openai import OpenAI

client = OpenAI(
    api_key="sk-0d71ecb7339c4315b717af147c8a30d1",
    base_url="https://api.deepseek.com"
)

response = client.chat.completions.create(
    model="deepseek-reasoner",
    messages=[
        {"role": "user", "content": "分析一下 Python 和 JavaScript 的区别"}
    ]
)

# 获取最终答案
answer = response.choices.message.content
print("答案:", answer)

# 获取思考过程
reasoning = response.choices.message.reasoning_content
print("\n思考过程:", reasoning)