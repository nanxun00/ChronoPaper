import json
import os
import shutil
from fastapi import FastAPI, File, UploadFile, APIRouter, Depends
from dashscope import MultiModalConversation
import dashscope

from src.api.deps import get_current_user
from src.settings import get_settings
from src.utils import setup_logger

_settings = get_settings()
dashscope.api_key = _settings.dashscope_api_key

# 初始化日志
logger = setup_logger("server-audio")

# 设置文件上传的目录
# UPLOAD_DIR = r"E:\TYUT\ipbd工作\Private-domain-model-material\src\saves\audio"
UPLOAD_DIR = r"src/saves/audio"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 设置 DashScope API Key（从 .env 读取）

# 定义路由
audio = APIRouter(prefix="/audio")
router = audio

@audio.post("/upload")
async def create_audio_file(file: UploadFile = File(...),
                            ):
    def load_file(file):
        # 生成文件名
        filename = f"{file.filename}_{os.urandom(8).hex()}.wav"
        file_path = os.path.join(UPLOAD_DIR, filename)  # 使用 os.path.join 拼接路径

        # 保存文件
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return {"filename": filename, "file_path": file_path}

    def convert(file_path):
        # 确保路径格式正确
        full_path = r"file://" + file_path.replace("\\", "/")  # 替换反斜杠为正斜杠
        messages = [
            {
                "role": "user",
                "content": [{"audio": full_path}],
            }
        ]

        response = MultiModalConversation.call(model="qwen-audio-asr", messages=messages)
        response_dict = json.loads(str(response))

        if response_dict.get("output") and response_dict["output"].get("choices"):
            choices = response_dict["output"]["choices"]
            if choices and choices[0].get("message") and choices[0]["message"].get("content"):
                content = choices[0]["message"]["content"]
                if content and content[0].get("text"):
                    text_content = content[0]["text"]
                    return text_content
                else:
                    logger.error("No text content found in response.")
            else:
                logger.error("No choices or message found in response.")
        else:
            logger.error("No output found in response.")

        return None

    # 加载文件并获取文件路径
    file_info = load_file(file)
    file_path = file_info.get("file_path")

    # 调用转换函数
    return convert(file_path)