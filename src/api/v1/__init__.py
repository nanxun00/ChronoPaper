from fastapi import APIRouter

from src.api.v1 import (
    admin,
    auth,
    chat,
    ideas,
    knowledge_base,
    latex,
    literature,
    search,
    smartbi,
    system,
    tasks,
    timerag,
    tools,
)

v1_router = APIRouter()
# 具体业务路由必须先于 auth 中的 `/{service}/{path:path}` 网关注册，
# 否则 /literature、/data 等会被网关拦截并因 services 未配置而返回 401。
v1_router.include_router(tasks.router)
v1_router.include_router(literature.router)
v1_router.include_router(chat.router)
v1_router.include_router(knowledge_base.router)
v1_router.include_router(smartbi.router)
v1_router.include_router(search.router)
v1_router.include_router(ideas.router)
v1_router.include_router(timerag.router)
v1_router.include_router(latex.router)
v1_router.include_router(admin.router)
v1_router.include_router(tools.router)
v1_router.include_router(system.router)
v1_router.include_router(auth.router)

try:
    from src.api.v1 import audio

    v1_router.include_router(audio.router)
except Exception:
    pass

try:
    from src.api.v1 import image

    v1_router.include_router(image.router)
except Exception:
    pass
