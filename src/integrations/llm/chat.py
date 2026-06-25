import os
from openai import OpenAI
from openai.types.beta.threads import Message

from src.utils.logging_config import setup_logger
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

logger = setup_logger(__name__)

class ChatOpenAIBase():

    def __init__(self, api_key, base_url, model_name):
        self.client = ChatOpenAI(api_key=api_key, base_url=base_url, model=model_name)
        self.model_name = model_name

    def predict(self, message, stream=False, tools=None, *, user_id: str = "", session_id: str = ""):
        if isinstance(message, str):
            messages = [
                SystemMessage(content="You're a helpful assistant"),
                HumanMessage(content=message),
            ]
        else:
            messages = message

        if tools:
            return self._predict_with_tools(messages, tools, user_id=user_id, session_id=session_id)

        if stream:
            return self._stream_response(messages)
        else:
            return self._get_response(messages)

    def _stream_response(self, messages):
        response = self.client.stream(messages, stream=True)
        for chunk in response:
            yield chunk


    def _get_response(self, messages):
        response = self.client.invoke(messages, stream=False)
        return response

    def _predict_with_tools(self, messages, tools, *, user_id: str = "", session_id: str = ""):
        """支持 Function Calling 的预测方法。

        当 tools 非空时，模型可能返回 tool_calls，需要执行工具并将结果
        回传给模型，直到模型返回最终文本响应。
        """
        from src.services.memos import get_memory_service

        bound_client = self.client.bind_tools(tools) if tools else self.client
        response = bound_client.invoke(messages, stream=False)

        # 如果模型没有调用工具，直接返回
        if not getattr(response, "tool_calls", None):
            forced = self._maybe_force_datetime_tool(messages, tools, bound_client)
            if forced is not None:
                return forced
            return response

        # 执行工具调用并循环
        max_rounds = 5
        current_messages = list(messages) + [response]

        for _ in range(max_rounds):
            tool_calls = getattr(response, "tool_calls", [])
            if not tool_calls:
                break

            tool_results = self._execute_tool_calls(tool_calls, user_id=user_id, session_id=session_id)
            current_messages.extend(tool_results)

            response = bound_client.invoke(current_messages, stream=False)
            current_messages.append(response)

            if not getattr(response, "tool_calls", None):
                break

        return response

    def _maybe_force_datetime_tool(self, messages, tools, bound_client):
        """模型未主动调用日期工具时，服务端补执行一次。"""
        from langchain_core.messages import HumanMessage, SystemMessage

        from src.integrations.native_tools.intent import query_needs_datetime
        from src.services.native_tools import get_native_tool_service

        tool_names = {
            (t.get("function") or {}).get("name")
            for t in (tools or [])
            if isinstance(t, dict)
        }
        if "get_current_datetime" not in tool_names:
            return None

        last_user = ""
        for item in reversed(messages or []):
            if isinstance(item, dict):
                if item.get("role") == "user":
                    last_user = str(item.get("content") or "")
                    break
            else:
                role = getattr(item, "type", "") or item.__class__.__name__.lower()
                if "human" in role or role == "user":
                    last_user = str(getattr(item, "content", "") or "")
                    break
        if not query_needs_datetime(last_user):
            return None

        result = get_native_tool_service().call_tool(
            "get_current_datetime",
            {"timezone": "Asia/Shanghai"},
        )
        tool_text = result.get("content") or result.get("error") or ""
        if not tool_text:
            return None

        followup = list(messages) + [
            SystemMessage(
                content=(
                    "用户正在询问日期或时间。以下是 get_current_datetime 的返回，"
                    "请严格据此回答，不要修改日期和星期：\n"
                    f"{tool_text}"
                )
            ),
            HumanMessage(content=last_user),
        ]
        return bound_client.invoke(followup, stream=False)

    def _execute_tool_calls(self, tool_calls, *, user_id: str = "", session_id: str = ""):
        """执行模型的 tool_calls 并返回 ToolMessage 列表。

        支持 MemOS 工具 (add_message, search_memory, delete_memory)
        以及 Web Search 工具 (bing_search, fetch_web_page 等)
        以及原生 Tool (get_current_datetime, get_weather)。
        """
        from langchain_core.messages import ToolMessage
        from src.services.memos import get_memory_service
        from src.services.native_tools import NATIVE_TOOL_NAMES, get_native_tool_service
        from src.services.web_search import get_web_search_service

        memos_service = get_memory_service()
        web_search_service = get_web_search_service()
        native_tool_service = get_native_tool_service()
        results = []

        for tc in tool_calls:
            tool_name = tc.get("name", "")
            tool_args = dict(tc.get("args", {}))
            tool_id = tc.get("id", "")

            content = ""
            try:
                # ── 记忆工具 (MemOS) ──────────────────────────────────
                if tool_name == "add_message":
                    messages = tool_args.get("messages", [])
                    msg_text = ""
                    if isinstance(messages, list):
                        for m in messages:
                            if isinstance(m, dict):
                                msg_text += m.get("content", "") + "\n"
                    result = memos_service.add_memory(
                        user_id=user_id,
                        session_id=session_id,
                        content=msg_text.strip(),
                    )
                    content = result.get("content") or result.get("error")
                elif tool_name == "search_memory":
                    query = tool_args.get("query", "")
                    result = memos_service.search_memory(
                        user_id=user_id,
                        session_id=session_id,
                        query=query,
                    )
                    content = result.get("content") or result.get("error")
                elif tool_name == "delete_memory":
                    result = memos_service.clear_session_memory(
                        user_id=user_id,
                        session_id=session_id,
                    )
                    content = result.get("content") or result.get("error")

                # ── 原生 Tool（日期 / 天气）──────────────────────────
                elif tool_name in NATIVE_TOOL_NAMES:
                    result = native_tool_service.call_tool(tool_name, tool_args)
                    content = result.get("content") or result.get("error")
                    if not content and not result.get("ok"):
                        content = f"工具执行失败或返回为空: {tool_name}"

                # ── 联网搜索工具 (Hosted MCP) ─────────────────────────
                # 如果不是记忆/原生工具，尝试调用 WebSearch 服务（MCP 动态工具名）
                else:
                    result = web_search_service.call_tool(tool_name, tool_args)
                    content = result.get("content") or result.get("error")
                    if not content and not result.get("ok"):
                        content = f"工具执行失败或返回为空: {tool_name}"
            except Exception as exc:
                content = f"工具执行异常: {exc}"

            results.append(ToolMessage(content=str(content), tool_call_id=tool_id))

        return results

class OpenAIBase():
    def __init__(self, api_key, base_url, model_name):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name = model_name

    def predict(self, message, stream=False):
        if isinstance(message, str):
            messages=[{"role": "user", "content": message}]
        else:
            messages = message

        if stream:
            return self._stream_response(messages)
        else:
            return self._get_response(messages)

    def _stream_response(self, messages):
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            stream=True,
        )
        for chunk in response:
            yield chunk.choices[0].delta

    def _get_response(self, messages):
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            stream=False,
        )
        return response.choices[0].message


class OpenModel(OpenAIBase):
    def __init__(self, model_name=None):
        model_name = model_name or "gpt-4o-mini"
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_API_BASE")
        super().__init__(api_key=api_key, base_url=base_url, model_name=model_name)

class OpenModelNew(ChatOpenAIBase):
    def __init__(self, model_name=None):
        model_name = model_name or "gpt-4o-mini"
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_API_BASE")
        super().__init__(api_key=api_key, base_url=base_url, model_name=model_name)

class DeepSeek(OpenAIBase):
    def __init__(self, model_name=None):
        model_name = model_name or "deepseek-chat"
        api_key = os.getenv("DEEPSEEK_API_KEY")
        base_url = "https://api.deepseek.com"
        super().__init__(api_key=api_key, base_url=base_url, model_name=model_name)

# TODO
class DeepSeekNew(ChatOpenAIBase):
    def __init__(self, model_name=None):
        model_name = model_name or "deepseek-chat"
        api_key = os.getenv("DEEPSEEK_API_KEY")
        base_url = "https://api.deepseek.com"
        super().__init__(api_key=api_key, base_url=base_url, model_name=model_name)

class DeepSeekLocal(ChatOpenAIBase):
    def __init__(self, model_name=None):
        model_name = model_name or "deepseek-r1:14b"
        from src.settings import get_settings
        s = get_settings()
        super().__init__(api_key=s.ollama_api_key, base_url=s.ollama_api_base, model_name=model_name)

# class DeepSeekLocal(OpenAIBase):
#     def __init__(self, model_name=None):
#         model_name = model_name or "deepseek-r1:14b"
#         # api_key = os.getenv("DEEPSEEKNEW_API_KEY")
#         api_key = 'ollama'
#         base_url = "http://47.103.8.209:19020/v1/"
#         super().__init__(api_key=api_key, base_url=base_url, model_name=model_name)

class Zhipu(OpenAIBase):
    def __init__(self, model_name=None):
        model_name = model_name or "glm-4-flash"
        api_key = os.getenv("ZHIPUAI_API_KEY")
        base_url = "https://open.bigmodel.cn/api/paas/v4/"
        super().__init__(api_key=api_key, base_url=base_url, model_name=model_name)

class ZhipuNew(ChatOpenAIBase):
    def __init__(self, model_name=None):
        model_name = model_name or "glm-4-flash"
        api_key = os.getenv("ZHIPUAI_API_KEY")
        base_url = "https://open.bigmodel.cn/api/paas/v4/"
        super().__init__(api_key=api_key, base_url=base_url, model_name=model_name)

class SiliconFlow(OpenAIBase):
    def __init__(self, model_name=None):
        model_name = model_name or "meta-llama/Meta-Llama-3.1-8B-Instruct"
        api_key = os.getenv("SILICONFLOW_API_KEY")
        base_url = "https://api.siliconflow.cn/v1"
        super().__init__(api_key=api_key, base_url=base_url, model_name=model_name)

class SiliconFlowNew(ChatOpenAIBase):
    def __init__(self, model_name=None):
        model_name = model_name or "meta-llama/Meta-Llama-3.1-8B-Instruct"
        api_key = os.getenv("SILICONFLOW_API_KEY")
        base_url = "https://api.siliconflow.cn/v1"
        super().__init__(api_key=api_key, base_url=base_url, model_name=model_name)

class MiMoNew(ChatOpenAIBase):
    def __init__(self, model_name=None):
        model_name = model_name or "mimo-v2-flash"
        api_key = os.getenv("MIMO_API_KEY")
        base_url = os.getenv("MIMO_API_BASE") or "https://api.xiaomimimo.com/v1"
        super().__init__(api_key=api_key, base_url=base_url, model_name=model_name)

class CustomModel(OpenAIBase):
    def __init__(self, model_info):
        model_name = model_info["name"]
        api_key = model_info["api_key"]
        base_url = model_info["api_base"]
        super().__init__(api_key=api_key, base_url=base_url, model_name=model_name)

class CustomModelNew(ChatOpenAIBase):
    def __init__(self, model_info):
        model_name = model_info["name"]
        api_key = model_info["api_key"]
        base_url = model_info["api_base"]
        super().__init__(api_key=api_key, base_url=base_url, model_name=model_name)

class GeneralResponse:
    def __init__(self, content):
        self.content = content
        self.is_full = False

class Qianfan:

    def __init__(self, model_name="ernie_speed") -> None:
        import qianfan
        self.model_name = model_name
        access_key = os.getenv("QIANFAN_ACCESS_KEY")
        secret_key = os.getenv("QIANFAN_SECRET_KEY")
        self.client = qianfan.ChatCompletion(ak=access_key, sk=secret_key)

    def predict(self, message, stream=False):
        if isinstance(message, str):
            messages=[{"role": "user", "content": message}]
        else:
            messages = message

        if stream:
            return self._stream_response(messages)
        else:
            return self._get_response(messages)

    def _stream_response(self, messages):
        response = self.client.do(
            model=self.model_name,
            messages=messages,
            stream=True,
        )
        for chunk in response:
            yield GeneralResponse(chunk["body"]["result"])

    def _get_response(self, messages):
        response = self.client.do(
            model=self.model_name,
            messages=messages,
            stream=False,
        )
        return GeneralResponse(response["body"]["result"])



class DashScope:

    def __init__(self, model_name="qwen-max-latest") -> None:
        self.model_name = model_name
        self.api_key= os.getenv("DASHSCOPE_API_KEY")

    def predict(self, message, stream=False):
        if isinstance(message, str):
            messages=[{"role": "user", "content": message}]
        else:
            messages = message

        if stream:
            return self._stream_response(messages)
        else:
            return self._get_response(messages)

    def _stream_response(self, messages):
        import dashscope
        response = dashscope.Generation.call(
            api_key=self.api_key,
            model=self.model_name,
            messages=messages,
            result_format='message',
            stream=True,
        )
        for chunk in response:
            message = chunk.output.choices[0].message
            message.is_full = True
            yield chunk.output.choices[0].message

    def _get_response(self, messages):
        import dashscope
        response = dashscope.Generation.call(
            api_key=self.api_key,
            model=self.model_name,
            messages=messages,
            result_format='message',
            stream=False,
        )
        return response.output.choices[0].message


# if __name__ == "__main__":    #openai的测试接口
#     # model = SiliconFlow()
#     # for a in model.predict("你好", stream=True):
#     #     print(a.content, end="")
#
#     model = DeepSeekNew("llama3")
#     for a in model.predict("你好", stream=True):
#         print(a.content, end="")

if __name__ == "__main__":    #chatopenai的测试接口
    # model = SiliconFlow()
    # for a in model.predict("你好", stream=True):
    #     print(a.content, end="")
    import re

    content = ""
    reasoning_content = ""
    # 初始化响应内容字典
    response_content = {
        'reasoning_content': '',
        'content': ''
    }

    model = DeepSeekLocal("deepseek-r1:14b")
    # model = DeepSeekLocal("deepseek-r1:14b")

    text=""" """
    for delta in model.predict("1+1=?", stream=True):
        print(delta,end="")

    # text="""<think>\nFirst, I need to add the numbers 1 and 1 together.\n\nAdding these two numbers results in 2.\n</think>\n\nTo find \\(1 + 1\\), follow these simple steps:\n\n1. **Start with the first number:**  \n   You begin with the number 1.\n\n2. **Add the second number:**  \n   Add another 1 to it.\n\n3. **Calculate the sum:**  \n   \\[\n   1 + 1 = 2\n   \\]\n\n**Final Answer:**\n\\[\n\\boxed{2}\n\\]"""
    # # # 使用正则表达式提取<think>标签内的内容
    # think_pattern = r"<think>(.*?)</think>"
    # think_match = re.search(think_pattern, text, re.DOTALL)
    # think_content = think_match.group(1).strip() if think_match else ""
    #
    # # 使用正则表达式提取<think>标签之后的内容
    # remaining_pattern = r"</think>(.*)"
    # remaining_match = re.search(remaining_pattern, text, re.DOTALL)
    # remaining_content = remaining_match.group(1).strip() if remaining_match else ""

    # # 打印结果
    # print("Content inside <think>:\n", think_content)
    # print("Content after <think>:\n", remaining_content)


    # for chunk in model.predict("1+1=?", stream=True):
    #     if chunk.reasoning_content:
    #         reasoning_content += chunk.choices[0].delta.reasoning_content
    #     else:
    #         content += chunk.content

    # print(reasoning_content)
    # print(content)
    # model = DeepSeekNew("deepseek-chat")
    # for delta in model.predict("1+1=?", stream=False):
    #     print(delta.content, end="")


        # think_start = delta[1].find('<think>')
        # think_end = delta[1].find('</think>')
        # if think_start != -1 and think_end != -1:
        #     reasoning_content = delta[1][think_start + len('<think>'): think_end].strip()
        #     response_content['reasoning_content'] = reasoning_content
        #
        # # 提取content
        # if think_end != -1:
        #     left_content = delta[1][think_end + len('</think>\n\n'):].strip()
        #     response_content['content'] = left_content
        #     content = left_content
        #
        # print(response_content)
    # model = DeepSeek()
    # for a in model.predict("你是谁？", stream=True):
    #     print(a.content, end="")