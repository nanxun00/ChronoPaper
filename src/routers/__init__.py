from fastapi import APIRouter

from .smartbi_router import smartbi
from .chat_router import chat
from .data_router import data
from .base_router import base
from .login_router import login
from .tool_router import tool
from .image_router import image
from .audio_router import audio

router = APIRouter()
router.include_router(base)
router.include_router(chat)
router.include_router(data)
router.include_router(tool)
# router.include_router(image)
router.include_router(audio)
router.include_router(smartbi)
router.include_router(login)


