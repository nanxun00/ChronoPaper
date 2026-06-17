import os
from fastapi import APIRouter, File, UploadFile, Body
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from src.utils import setup_logger
import shutil

tool = APIRouter(prefix="/tool")

logger = setup_logger("server-tools")

class Tool(BaseModel):
    name: str
    title: str
    description: str
    url: str
    method: str

@tool.get("/", response_model=List[Tool])
async def route_index():
    '''
        返回一个工具列表，共前端页面中展示
        创建一个工具列表，包含两个tool实例
        第一个工具用于文本分块，第二个工具用于pdf转文本

    '''
    tools = [
        Tool(
            name="text-chunking",
            title="文本分块",
            description="将文本分块以更好地理解。可以输入文本或者上传文件。",
            url="/tools/text-chunking",
            method="POST",
        ),
        Tool(
            name="pdf2txt",
            title="PDF转文本",
            description="将PDF文件转换为文本文件。",
            url="/tools/pdf2txt",
            method="POST",
        )
    ]

    return tools

@tool.post("/text-chunking")
async def text_chunking(text: str = Body(...), params: Dict[str, Any] = Body(...)):
    '''
        文本分块功能的异步API接口
        该函数通过接收post请求，对传入的文本进行分块处理。它使用了外部的chunk函数来进行实际的文本分块操作
        参数：
            - text: 待分块的文本，类型为字符串，通过请求体传递
            - params: 分块操作的参数，类型为字典，包含分块操作所需的额外信息，通过请求体传递
        返回：
        返回一个json对象，包含分块后的文本节点列表，每个节点以字典形式表示
    '''
    from src.core.indexing import chunk
    nodes = chunk(text, params=params)
    return {"nodes": [node.to_dict() for node in nodes]}


@tool.post("/pdf2txt")
async def handle_pdf2txt(file: str = Body(...)):
    '''
        将pdf文件转换为文本
        此函数通过接收一个pdf文件作为输入，然后使用pdf2txt插件将其转换为文本格式
        转换后的文本以json格式返回，包含转换后的文本数据

        参数：
            - file(str)；以字符串形式接受的pdf文件内容
        返回：
            - dict: 包含转换后的文本数据的字典
    '''
    # filename = f"{file.filename}_{os.urandom(8).hex()}.pdf"
    # file_path = os.path.join(UPLOAD_DIR, filename)  # 使用 os.path.join 拼接路径

    # # 保存文件
    # with open(file_path, "wb") as buffer:
    #     shutil.copyfileobj(file.file, buffer)
    from src.plugins import pdf2txt
    text = pdf2txt(file, return_text=True)
    return {"text": text}
