"""
提供图片接收接口，图片上传后，会先识别文本数据，识别成功后，会附带到下次请求的提示词。【功能可以参考Deepseek、腾讯元宝】
思路：
    1.提供图片接收接口，用post接口接收
    2.识别图片上的文字，可以使用ocr识别
    3.将识别后的文字保存，作为下一次请求的提示词
"""
from fastapi import FastAPI, File, UploadFile, HTTPException, APIRouter, Form
from fastapi.responses import JSONResponse
from src.config import logger
from src.utils import setup_logger
from typing import Optional, Dict
import pytesseract
from PIL import Image
import io
import uuid
import time
from pathlib import Path
import shutil
# from minio import Minio
# from minio.error import S3Error
import os


image = APIRouter(prefix="/image")

# 定义一些内容
# 支持图片的类型, 这里只支持常见的图片格式
supported_image_types = [
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/tiff"
]

# 配置常量
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
CACHE_EXPIRE = 300  # 5分钟缓存
pytesseract.pytesseract.tesseract_cmd = r"local\\Tesseract-OCR\\tesseract.exe"
ocr_cache: Dict[str, dict] = {}

# os.environ['TESSDATA_PREFIX'] = '/usr/share/tesseract-ocr/4.00/'
# # print("TESSDATA_PREFIX:", os.environ.get('TESSDATA_PREFIX'))
#
# tessdata_dir = '/usr/share/tesseract-ocr/4.00/tessdata/'


# 注释掉 MinIO 初始化与桶检查，避免启动时进行网络连接
# minio_client = Minio(
#     "47.103.8.209:19051",  # MinIO 服务器地址
#     access_key="ND7caoV4zRL3O2VL50nR",
#     secret_key="OeRy2hYTYnGbxYGzxIKqHHSHeGlusDpRm6ijBntb",
#     secure=False
# )
# BUCKET_NAME = "image"
# try:
#     if not minio_client.bucket_exists(BUCKET_NAME):
#         minio_client.make_bucket(BUCKET_NAME)
# except S3Error as e:
#     print(f"Error: {e}")
@image.post("/upload_image")
async def upload_image(file: UploadFile = File(...)):
    """
        1. 检查一下文件大小
        2. 判断一下图片格式(jpg，png...)
        3. ocr处理图片上传
    """
    try:
        file_content = await file.read()
        # print(file_content)
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="文件过大，最大为10MB")

        if file.content_type not in supported_image_types:
            raise HTTPException(status_code=415, detail="不支持的图片格式")

        # 生成唯一文件名
        file_suffix = Path(file.filename).suffix  # 获取原始文件后缀
        saved_filename = f"{uuid.uuid4()}{file_suffix}"
        # save_path = UPLOAD_DIR / saved_filename
        # print(saved_filename)
        # 上传文件到 MinIO（已禁用）
        # try:
        #     minio_client.put_object(
        #         BUCKET_NAME,
        #         saved_filename,
        #         io.BytesIO(file_content),
        #         len(file_content),
        #         content_type=file.content_type
        #     )
        # except S3Error as e:
        #     raise HTTPException(status_code=500, detail=f"MinIO 上传失败: {e}")

        image = Image.open(io.BytesIO(file_content))
        text = pytesseract.image_to_string(image, lang='chi_sim+eng')
        text = f"上传的图片或照片的内容识别出的结果为{text},若用户提问有关图片或照片的问题，则基于图片或照片的识别结果作为提示词。"
        # 生成会话id，并存储结果
        session_id = str(uuid.uuid4())
        ocr_cache[session_id] = {
            "text": text,
            "image_path": saved_filename,
            "expire_time": time.time()
        }
        # 生成图片访问链接（MinIO 已禁用，返回空字符串或按需改为本地路径）
        image_url = ""
        # print(image_url)
        return JSONResponse(
            content={
                "session_id": session_id,
                "ocr_text": text,
                "image_path": image_url,  # 返回访问路径
                "expires_in": CACHE_EXPIRE
            }
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.info(f"上传文件失败: {str(e)}")

#
# def get_cached_text(session_id: str) -> Optional[str]:
#     """获取缓存中的OCR结果"""
#     if session_id not in ocr_cache:
#         return None
#
#     cache_data = ocr_cache[session_id]
#     if time.time() - cache_data["expire_time"] > CACHE_EXPIRE:
#         del ocr_cache[session_id]
#         return None
#
#     return cache_data["text"]
#
#
# # 示例使用接口
#
# def ask_question(session_id: str, question: str):
#     ocr_text = get_cached_text(session_id)
#
#     prompt = f"{question}\n\n上下文信息：{ocr_text}" if ocr_text else question
#
#     # 这里可以添加实际处理逻辑
#     return JSONResponse(
#         content={
#             "response": f"已处理您的请求，附加OCR上下文：{prompt}"
#         }
#     )

