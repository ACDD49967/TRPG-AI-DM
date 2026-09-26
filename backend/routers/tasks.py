"""通用任务中心：上传解析、模型下载的进度查询与取消。"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from backend.config import settings
# 上传流水线的归属模块（此前从 routers.knowledge 再导出取用）
from backend.knowledge_tasks import _run_knowledge_upload_task
from backend.engine.session import (
    get_session_for_user,
)
from backend.task_center import (
    TaskCancelled,
    is_cancel_requested,
    task_manager,
    task_sse_generator,
)

# 兼容搬移前的调用写法：归属校验直接复用 session 层实现
_get_session_for_user = get_session_for_user

# 装配仍在 backend.main：这里只提供本域路由
router = APIRouter(tags=["tasks"])


@router.post("/api/tasks/upload-document")
async def create_upload_document_task(
    file: UploadFile = File(...),
    title: str = Form(""),
    system: str = Form("custom"),
    source: str = Form("user"),
    tags: str = Form(""),
    username: str = Form("default"),
    splitter: str = Form("semantic"),
    max_ocr_pages: int = Form(20),
    ocr_enabled: bool = Form(True),
    region_fusion: bool = Form(True),
    scenario_id: str = Form(""),
):
    """创建知识库文档上传后台任务，返回 task_id 后通过 SSE 查看进度。"""
    data = await file.read()
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件不能超过 30MB")
    task = task_manager.create("document_upload", message="任务已创建，等待开始")
    asyncio.create_task(_run_knowledge_upload_task(
        task.id, data, file.filename or "", title, system, source, tags,
        username, splitter, max_ocr_pages, ocr_enabled, region_fusion, scenario_id,
    ))
    return {
        "task_id": task.id,
        "status": "running",
        "events_url": f"/api/tasks/{task.id}/events",
    }



@router.get("/api/tasks/{task_id}/events")
async def task_events(task_id: str):
    """SSE 实时推送任务进度。"""
    if task_manager.get(task_id) is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return StreamingResponse(
        task_sse_generator(task_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )



@router.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    task = task_manager.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task.to_dict()



@router.get("/api/tasks")
async def list_tasks(limit: int = 50):
    return {"tasks": [t.to_dict() for t in task_manager.list(limit=limit)]}



@router.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    if task_manager.request_cancel(task_id):
        return {"ok": True, "cancel_requested": True}
    raise HTTPException(status_code=404, detail="任务不存在")



async def _run_model_download_task(task_id: str, kind: str):
    from pathlib import Path
    from backend.model_setup import (
        ensure_bge_dependencies,
        ensure_reranker_dependencies,
        download_hf_repo,
    )

    task_manager.update(task_id, status="running", phase="deps", message="正在安装模型依赖")
    _cancel = lambda: is_cancel_requested(task_id)
    try:
        if _cancel():
            task_manager.update(task_id, status="cancelled", phase="cancelled", message="已取消")
            return
        if kind == "embedding":
            await ensure_bge_dependencies(cancel_check=_cancel)
            target_dir = str(settings.BGE_M3_DIR)
            repo = settings.BGE_M3_REPO
        else:
            await ensure_reranker_dependencies(cancel_check=_cancel)
            target_dir = str(settings.BGE_RERANKER_PATH)
            repo = settings.BGE_RERANKER_REPO

        task_manager.update(task_id, status="running", phase="download", message="开始下载模型")
        async def _cb(pct, path):
            if _cancel():
                raise TaskCancelled("模型下载已取消")
            task_manager.update(
                task_id,
                status="running",
                phase="download",
                progress=pct if pct is not None else 0.0,
                message=f"下载中：{path}" if path else "下载中",
            )

        await download_hf_repo(repo, target_dir, _cb, cancel_check=_cancel)
        size = sum(f.stat().st_size for f in Path(target_dir).rglob("*") if f.is_file())
        task_manager.update(
            task_id,
            status="completed",
            phase="done",
            progress=100.0,
            message="模型下载完成",
            result={"kind": kind, "path": target_dir, "size": size},
        )
    except TaskCancelled:
        task_manager.update(task_id, status="cancelled", phase="cancelled", message="模型下载已取消")
    except Exception as e:
        task_manager.update(task_id, status="failed", phase="download", error=str(e))



@router.post("/api/tasks/model-download")
async def create_model_download_task(payload: dict):
    kind = str(payload.get("kind") or "").strip()
    if kind not in ("embedding", "reranker"):
        raise HTTPException(status_code=400, detail="kind 仅支持 embedding 或 reranker")
    task = task_manager.create("model_download", message="任务已创建，等待开始")
    asyncio.create_task(_run_model_download_task(task.id, kind))
    return {
        "task_id": task.id,
        "status": "running",
        "events_url": f"/api/tasks/{task.id}/events",
    }
