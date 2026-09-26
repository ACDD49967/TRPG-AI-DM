"""剧本列表、导入、编辑、删除与游玩计数。

按职责拆成两个子路由，这里只做装配（`backend/main.py` 仍只 include 这一个 scenarios 路由）：
- `scenarios_crud`：列表 / 经典剧本 / 详情 / 游玩计数 / 改名 / 删除
- `scenarios_import`：POST /api/scenarios/import（SSE 长任务）

OpenAPI 路径与 `scenarios` 标签保持不变。
"""
from fastapi import APIRouter

from backend.routers.scenarios_crud import router as scenarios_crud_router
from backend.routers.scenarios_import import router as scenarios_import_router

router = APIRouter()
router.include_router(scenarios_crud_router, tags=["scenarios"])
router.include_router(scenarios_import_router, tags=["scenarios"])
