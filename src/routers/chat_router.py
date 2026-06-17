import json
import asyncio
from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse, Response
from concurrent.futures import ThreadPoolExecutor
from src.core import HistoryManager
from src.core.startup import startup
from src.utils.logging_config import setup_logger
from src.routers.image_router import ocr_cache

chat = APIRouter(prefix="/chat")
logger = setup_logger("server-chat")
# 创建线程池
executor = ThreadPoolExecutor()

refs_pool = {}

@chat.get("/")
async def chat_get():
    return "Chat Get!"

@chat.post("/")
def chat_post(
        query: str = Body(...),
        meta: dict = Body(None),
        history: list = Body(...),
        cur_res_id: str = Body(...)):
    '''
        处理聊天的POST请求
        参数：
            - query: 用户的查询信息
            - meta: 附加的元数据，用于控制聊天行为
            - history: 聊天历史记录
            - cur_res_id: 当前响应的ID
        返回：
            - StreamingResponse: 实时生成的聊天响应
    '''
    print(meta)
    # 检查 meta 中是否包含 OCR 识别的 session_id
    # session_id = meta.get("session_id") if meta else None
    # if session_id and session_id in ocr_cache:
    #     ocr_text = ocr_cache[session_id]["text"]
    #     query = f"【OCR 识别内容】：{ocr_text}\n\n{query}"  # 将 OCR 结果拼接到 query 前

    # 初始化历史记录管理器
    history_manager = HistoryManager(history)

    def make_chunk(content, status, history):
        '''
            创建响应块
            参数：
                - content: 相应内容
                - status: 响应状态
                - history：当前历史记录
            返回：
                - bytes: 编码后的响应块
        '''
        return json.dumps({
            "response": content,
            "history": history,
            "model_name": startup.config.model_name,
            "status": status,
            "meta": meta,
        }, ensure_ascii=False).encode('utf-8') + b"\n"

    def generate_response():
        '''
            生成响应
            该函数负责根据用户查询和历史记录生成聊天响应，如果启用了检索功能，他会首先检索相关信息
            然后使用模型生成响应，生成的响应被切分为块，以便实时推送到客户端
        '''

        # 如果采用了检索功能，他会首先进行检索
        if meta.get("enable_retrieval"):
            chunk = make_chunk("", "searching", history=None)
            yield chunk

            new_query, refs = startup.retriever(query, history_manager.messages, meta)
            refs_pool[cur_res_id] = refs
        else:
            new_query = query

        # 提那件带有新查询的历史记录，并添加用户查询到历史记录中
        messages = history_manager.get_history_with_msg(new_query, max_rounds=meta.get('history_round'))
        history_manager.add_user(query)
        logger.debug(f"Web history: {history_manager.messages}")

        content = ""
        # 初始化响应内容字典
        response_content = {
            'reasoning_content': '',
            'content': ''
        }
        # 使用模型预测响应，并实时生成响应块
        for delta in startup.model.predict(messages, stream=True):
            if not delta.content:
                continue
            if startup.model.model_name=="deepseek-r1:32b" or startup.model.model_name=="deepseek-r1:14b":
                if hasattr(delta, 'is_full') and delta.is_full:
                    if hasattr(delta, 'reasoning_content'):
                        response_content['reasoning_content'] = delta.reasoning_content
                    response_content['content'] = delta.content
                    content = delta.content
                else:
                    if hasattr(delta, 'reasoning_content'):
                        response_content['reasoning_content'] += delta.reasoning_content
                    response_content['content'] += delta.content
                    content += delta.content

            else:
                if hasattr(delta, 'is_full') and delta.is_full:
                    response_content['content'] = delta.content
                    content = delta.content
                else:
                    response_content['content'] += delta.content
                    content += delta.content

            chunk = make_chunk(response_content, "loading", history=history_manager.update_ai(content))
            yield chunk
            #     if hasattr(delta, 'is_full') and delta.is_full:
            #         if hasattr(delta, 'reasoning_content'):
            #             response_content['reasoning_content'] = delta.reasoning_content
            #             response_content['content'] = delta.content
            #             content = delta.content
            #         else:
            #             import re
            #             logger.info(type(delta.content))
            #             think_pattern = r"<think>(.*?)</think>"
            #             think_match = re.search(think_pattern, delta.content, re.DOTALL)
            #             think_content = think_match.group(1).strip() if think_match else ""
            #
            #             # 使用正则表达式提取<think>标签之后的内容
            #             remaining_pattern = r"</think>(.*)"
            #             remaining_match = re.search(remaining_pattern, delta.content, re.DOTALL)
            #             remaining_content = remaining_match.group(1).strip() if remaining_match else ""
            #
            #             # 打印结果
            #             print("Content inside <think>:\n", think_content)
            #             print("Content after <think>:\n", remaining_content)
            #             response_content['reasoning_content'] = delta.content
            #             response_content['content'] = delta.content
            #             content = delta.content
            #
            #
            #     else:
            #         if hasattr(delta, 'reasoning_content'):
            #             response_content['reasoning_content'] += delta.reasoning_content
            #             response_content['content'] += delta.content
            #             content += delta.content
            #         else:
            #             import re
            #             whether_think = 1
            #             if whether_think == 1:
            #                 response_content['reasoning_content'] += delta.content
            #             if delta.content == "</think>":
            #                 whether_think = 0
            #
            #             if whether_think == 0:
            #                 response_content['content'] += delta.content
            #                 content += delta.content
            #
            # else:
            #     if hasattr(delta, 'is_full') and delta.is_full:
            #         response_content['content'] = delta.content
            #         content = delta.content
            #     else:
            #         response_content['content'] += delta.content
            #         content += delta.content
            #
            # chunk = make_chunk(response_content, "loading", history=history_manager.update_ai(content))
            # yield chunk


    '''async def generate_response():
        try:
            # 模拟逐步生成响应
            for delta in startup.model.predict(history_manager.messages, stream=True):
                if not delta.content:
                    continue
                content += delta.content
                chunk = make_chunk(content, "loading", history=history_manager.update_ai(content))
                yield chunk
        except asyncio.CancelledError:
            # 处理任务取消的逻辑
            logger.warning("Request was cancelled by client.")
            raise'''

    # 返回生成的响应流
    return StreamingResponse(generate_response(), media_type='application/json')

@chat.post("/call")
async def call(query: str = Body(...), meta: dict = Body(None)):
    '''
        接收post请求，执行模型预测并返回结果
        参数：
            - query：str类型，必需，作为模型预测的输入
            - meta：dict类型，可选，提供额外的元数据

        返回:
            - 一个包含预测结果的字典
    '''
    async def predict_async(query):
        '''
            异步预测函数，用于在异步环境中执行模型预测
            参数：
                - query：str类型，模型预测的输入
            返回：
                - 模型预测的结果
        '''
        # 获取当前的事件循环
        loop = asyncio.get_event_loop()
        # 在事件循环中运行预测函数，并等待其完成
        return await loop.run_in_executor(executor, startup.model.predict, query)

    # 调用异步预测函数，并等待结果
    response = await predict_async(query)
    # 记录日志，记录查询和响应的内容
    logger.debug({"query": query, "response": response.content})

    return {"response": response.content}

@chat.get("/refs")
def get_refs(cur_res_id: str):
    '''
        从refs_pool中获取并移除当前资源的引用信息
        参数：
            - cur_res_id:（str)当前资源的ID，用于在refs_pool中查找对应的引用信息
        返回：
            - dict: 包含从refs_pool中移除的引用信息的字典，如果未找到则为None
    '''
    global refs_pool
    refs = refs_pool.pop(cur_res_id, None)
    return {"refs": refs}