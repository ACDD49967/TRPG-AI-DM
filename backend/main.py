"""FastAPI 应用入口——只负责应用装配（生命周期 / 中间件 / 路由挂载）。

各领域 API 已按域拆到 `backend/routers/`；这里保持"装配层"职责，
避免入口文件继续膨胀。拆分的动机与边界见 SKILL.md 的拆分记录。
"""

import asyncio
import os as _os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database import init_db
from backend.engine.session import session_manager
from backend.paths import InvalidResourceId
from backend.routers.auth import router as auth_router
from backend.routers.characters import router as characters_router
from backend.routers.extensions import router as extensions_router
from backend.routers.game import router as game_router
from backend.routers.generate import router as generate_router
from backend.routers.knowledge import router as knowledge_router
from backend.routers.levelup import router as levelup_router
from backend.routers.media import router as media_router
from backend.routers.models import router as models_router
from backend.routers.observability import router as observability_router
from backend.routers.observability import system_router as observability_system_router
from backend.routers.saves import router as saves_router
from backend.routers.scenarios import router as scenarios_router
from backend.routers.session_settings import router as session_settings_router
from backend.routers.tasks import router as tasks_router
from backend.routers.world import router as world_router
from backend.routers.memories import router as memories_router

# 兼容再导出：历史脚本（dist/_test_*.py）与外部调用方曾直接从 backend.main 取这两个名字。
# 它们已随路由搬到各自模块，这里保留入口层别名，避免旧脚本失效。
# 上传流水线已搬到 backend/knowledge_tasks；这里保留入口层名字，旧脚本（dist/_test_*.py）不受影响
from backend.knowledge_tasks import _run_knowledge_upload_task  # noqa: F401
from backend.routers.media import add_bestiary_api  # noqa: F401


# ═══════════════════════════════════════════════════════════════
# 应用生命周期
# ═══════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的生命周期管理。"""
    # 启动时：创建数据库表
    await init_db()
    # RAG 后台预热：模型加载与索引构建放到后台线程，启动立即就绪
    warmup_task = None
    try:
        from backend.engine.warmup import start_background_warmup
        warmup_task = await start_background_warmup()
    except Exception as e:
        print(f"[Warmup] 后台预热调度失败（已忽略）: {e}")
    # 自动清理无用的运行期 world_state 文件（存档内含快照，可安全清理）
    try:
        from backend.engine.world_state import cleanup_world_states
        cleanup_world_states(active_session_ids=list(session_manager._sessions.keys()))
    except Exception:
        pass
    # 后台会话回收任务：定期清理无订阅且超时的会话 + world_states
    async def _session_gc_loop():
        while True:
            await asyncio.sleep(300)
            try:
                removed = session_manager.prune_idle()
                if removed:
                    print(f"[AI-DM] 回收空闲会话 {len(removed)} 个")
                from backend.engine.world_state import cleanup_world_states
                cleanup_world_states(active_session_ids=list(session_manager._sessions.keys()))
            except Exception as e:
                print(f"[AI-DM] 会话回收失败（已忽略）: {e}")

    gc_task = asyncio.create_task(_session_gc_loop())
    print(f"[AI-DM] Server started at http://{settings.HOST}:{settings.PORT}")
    print(f"[AI-DM] Database: {settings.DATABASE_URL}")
    print(f"[AI-DM] Model: {settings.MODEL_NAME}")
    yield
    # 关闭时：停止 GC 任务与预热等待（线程本身无法中断）
    gc_task.cancel()
    try:
        await gc_task
    except asyncio.CancelledError:
        pass
    if warmup_task is not None and not warmup_task.done():
        warmup_task.cancel()


# ═══════════════════════════════════════════════════════════════
# FastAPI 应用实例
# ═══════════════════════════════════════════════════════════════

app = FastAPI(
    title="TRPG AI 跑团主持",
    description="由大语言模型驱动的单人 TRPG 跑团主持",
    version="0.3.5",
    lifespan=lifespan,
)


@app.exception_handler(InvalidResourceId)
async def invalid_resource_id_handler(request: Request, exc: InvalidResourceId):
    return JSONResponse(status_code=400, content={"detail": str(exc)})

# CORS 中间件 —— 允许前端开发服务器跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由装配：观测/升级接口 + 各领域路由（路径与拆分前完全一致）
app.include_router(observability_router)
app.include_router(observability_system_router)
app.include_router(levelup_router)
app.include_router(auth_router)
app.include_router(characters_router)
app.include_router(extensions_router)
app.include_router(game_router)
app.include_router(generate_router)
app.include_router(knowledge_router)
app.include_router(media_router)
app.include_router(models_router)
app.include_router(saves_router)
app.include_router(scenarios_router)
app.include_router(session_settings_router)
app.include_router(tasks_router)
app.include_router(world_router)
app.include_router(memories_router)

# 静态媒体（地图/生物/角色图片）：与拆分前一致，仍在所有路由之后挂载
_os.makedirs("media", exist_ok=True)
app.mount("/media", StaticFiles(directory="media"), name="media")
