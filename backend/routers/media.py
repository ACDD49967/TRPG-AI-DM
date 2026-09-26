"""地图/法术/生物图鉴、角色与 NPC 图片、翻译接口。

按资源拆成四个子路由，这里只做装配——顺序与拆分前一致：
- `media_maps`：/api/maps
- `media_spells`：/api/spells、/api/game/{sid}/translate-srd|translate-media
- `media_bestiary`：/api/bestiary
- `media_images`：/api/media/character、/api/game/{sid}/image|npc|npc/image

`backend/main.py` 仍然只 include 这一个 media 路由，OpenAPI 路径与 `media` 标签保持不变。
"""
from fastapi import APIRouter

from backend.routers.media_bestiary import router as media_bestiary_router
from backend.routers.media_images import router as media_images_router
from backend.routers.media_maps import router as media_maps_router
from backend.routers.media_spells import router as media_spells_router

router = APIRouter()
router.include_router(media_maps_router, tags=["media"])
router.include_router(media_spells_router, tags=["media"])
router.include_router(media_bestiary_router, tags=["media"])
router.include_router(media_images_router, tags=["media"])

# 兼容搬移前的调用写法：归属校验直接复用 session 层实现
from backend.engine.session import get_session_for_user as _get_session_for_user  # noqa: E402,F401
# 历史脚本/入口层曾直接从本模块取处理器（如 main.py 与 dist/_test_*.py），这里再导出
from backend.routers.media_bestiary import add_bestiary_api  # noqa: E402,F401
