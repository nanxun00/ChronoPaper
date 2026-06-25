import os
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Any, Dict, List

from src.services.document_gen.generator import (
    DocumentGenerateRequest,
    DOCUMENTS_DIR,
    ensure_documents_dir,
    generate_document_file,
)
from src.utils import setup_logger

tool = APIRouter(prefix="/tool")
router = tool

logger = setup_logger("server-tools")


class Tool(BaseModel):
    name: str
    title: str
    description: str
    url: str
    method: str


@tool.get("/", response_model=List[Tool])
async def route_index():
    """返回工具列表，供前端页面展示。"""
    return [
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
        ),
    ]


@tool.post("/generate-document")
async def generate_document(body: DocumentGenerateRequest):
    """生成 DOCX 或 PDF 文档并返回下载链接。"""
    if body.format.lower() not in ("docx", "pdf"):
        raise HTTPException(status_code=400, detail="仅支持 docx 和 pdf 格式")

    logger.info("开始生成文档: %s (%s)", body.title, body.format.lower())

    try:
        result = generate_document_file(
            title=body.title,
            content=body.content,
            format=body.format,
            font_family=body.font_family,
            font_size=body.font_size,
            line_spacing=body.line_spacing,
        )
        logger.info("文档生成成功: %s, 大小: %s bytes", result["filename"], result["file_size"])
        return result
    except ImportError as e:
        logger.error("文档生成依赖未安装: %s", e)
        if "docx" in str(e).lower():
            raise HTTPException(status_code=500, detail="DOCX 生成依赖未安装")
        raise HTTPException(status_code=500, detail="PDF 生成依赖未安装")
    except Exception as e:
        logger.error("文档生成失败: %s", e)
        raise HTTPException(status_code=500, detail=f"文档生成失败: {str(e)}")


@tool.get("/download-document/{filename}")
async def download_document(filename: str):
    """下载生成的文档。"""
    ensure_documents_dir()

    if "." not in filename:
        raise HTTPException(status_code=400, detail="无效的文件名")

    file_ext = Path(filename).suffix.lower()
    if file_ext not in (".docx", ".pdf"):
        raise HTTPException(status_code=400, detail="不支持的文件格式")

    file_path = DOCUMENTS_DIR / filename

    try:
        file_path = file_path.resolve()
        if not str(file_path).startswith(str(DOCUMENTS_DIR.resolve())):
            raise HTTPException(status_code=403, detail="禁止访问")
    except HTTPException:
        raise

    if not file_path.exists():
        logger.warning("下载请求但文件不存在: %s", filename)
        raise HTTPException(status_code=404, detail="文档不存在")

    media_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if file_ext == ".docx"
        else "application/pdf"
    )

    logger.info("下载文档: %s (%s)", filename, file_path)

    return FileResponse(
        file_path,
        media_type=media_type,
        filename=filename,
    )


@tool.post("/text-chunking")
async def text_chunking(text: str = Body(...), params: Dict[str, Any] = Body(...)):
    from src.services.rag.indexing import chunk

    nodes = chunk(text, params=params)
    return {"nodes": [node.to_dict() for node in nodes]}


@tool.post("/pdf2txt")
async def handle_pdf2txt(file: str = Body(...)):
    from src.parsers import pdf_simple as pdf2txt

    text = pdf2txt(file, return_text=True)
    return {"text": text}
