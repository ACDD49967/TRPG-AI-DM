"""模型列表获取与本地模型下载（BGE / 小模型）。"""
from __future__ import annotations

import asyncio
import json
import os as _os

from fastapi import APIRouter, HTTPException

from backend.config import ensure_valid_api_key, settings
from backend.engine.session import (
    get_session_for_user,
)

# 兼容搬移前的调用写法：归属校验直接复用 session 层实现
_get_session_for_user = get_session_for_user

# 装配仍在 backend.main：这里只提供本域路由
router = APIRouter(tags=["models"])



@router.post("/api/models")
async def fetch_models(payload: dict):
    """从 OpenAI 兼容接口获取模型列表，用于前端下拉菜单。"""
    import httpx
    base_url = str(payload.get("base_url") or settings.LLM_BASE_URL).rstrip("/")
    _verify = _os.environ.get("DND_INSECURE_TLS", "0") != "1"
    api_key = str(payload.get("api_key") or settings.LLM_API_KEY)
    try:
        api_key = ensure_valid_api_key(api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    candidates = [f"{base_url}/models"]
    if not base_url.endswith("/v1"):
        candidates.append(f"{base_url}/v1/models")
    last_err = None
    try:
        _ca_bundle = _os.environ.get("DND_CA_BUNDLE", "").strip()
        async with httpx.AsyncClient(timeout=20, verify=(_ca_bundle or _verify)) as hc:
            for url in candidates:
                try:
                    r = await hc.get(url, headers={"Authorization": f"Bearer {api_key}"})
                    if r.status_code == 200:
                        data = r.json()
                        models = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
                        return {"models": models, "base_url": base_url}
                    if r.status_code in (401, 403):
                        raise HTTPException(status_code=502, detail="认证失败：API Key 无效或没有权限")
                    last_err = f"HTTP {r.status_code}"
                except HTTPException:
                    raise
                except Exception as e:
                    last_err = str(e)
        raise HTTPException(status_code=502, detail=f"无法获取模型列表，请检查 API 地址与 Key（{last_err}）")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取模型列表失败: {e}") from e



@router.post("/api/models/download-bge")
async def download_bge_model(payload: dict):
    """按用户点击下载可选 BGE 模型：自动安装依赖并下载模型。仅手动触发，不自动拉取。"""
    from pathlib import Path
    from backend.model_setup import (
        ensure_bge_dependencies,
        ensure_reranker_dependencies,
        download_hf_repo,
    )

    kind = str(payload.get("kind") or "").strip()
    if kind not in ("embedding", "reranker"):
        raise HTTPException(status_code=400, detail="kind 仅支持 embedding 或 reranker")

    try:
        if kind == "embedding":
            await ensure_bge_dependencies()
            target_dir = str(settings.BGE_M3_DIR)
            collected = []
            async def _cb(pct, path):
                collected.append((pct, path))
            await download_hf_repo(settings.BGE_M3_REPO, target_dir, _cb)
            size = sum(f.stat().st_size for f in Path(target_dir).rglob("*") if f.is_file())
            return {
                "ok": True,
                "kind": "embedding",
                "path": target_dir,
                "size": size,
                "message": f"BGE-M3 已下载到 {target_dir}",
            }
        else:
            await ensure_reranker_dependencies()
            target_dir = str(settings.BGE_RERANKER_PATH)
            collected = []
            async def _cb(pct, path):
                collected.append((pct, path))
            await download_hf_repo(settings.BGE_RERANKER_REPO, target_dir, _cb)
            size = sum(f.stat().st_size for f in Path(target_dir).rglob("*") if f.is_file())
            return {
                "ok": True,
                "kind": "reranker",
                "path": target_dir,
                "size": size,
                "message": f"BGE-reranker-base 已下载到 {target_dir}",
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"下载失败: {e}") from e



@router.post("/api/models/download-bge/stream")
async def download_bge_model_stream(payload: dict):
    """SSE 流式下载可选 BGE 模型：自动安装依赖 + 下载模型，实时进度。"""
    from pathlib import Path
    from fastapi.responses import StreamingResponse
    from backend.model_setup import (
        ensure_bge_dependencies,
        ensure_reranker_dependencies,
        download_hf_repo,
    )

    kind = str(payload.get("kind") or "").strip()
    if kind not in ("embedding", "reranker"):
        raise HTTPException(status_code=400, detail="kind 仅支持 embedding 或 reranker")

    async def event_stream():
        try:
            if kind == "embedding":
                yield f"data: {json.dumps({'type':'status','msg':'正在安装 BGE-M3 依赖（首次可能需要几分钟）...'}, ensure_ascii=False)}\n\n"
                await ensure_bge_dependencies()
                target_dir = str(settings.BGE_M3_DIR)
                yield f"data: {json.dumps({'type':'status','msg':'依赖安装完成，开始下载 BGE-M3 模型...'}, ensure_ascii=False)}\n\n"

                q: asyncio.Queue = asyncio.Queue()
                async def _cb(pct, path):
                    await q.put((pct, path))

                task = asyncio.create_task(download_hf_repo(settings.BGE_M3_REPO, target_dir, _cb))
                while True:
                    if task.done():
                        while not q.empty():
                            pct, path = q.get_nowait()
                            yield f"data: {json.dumps({'type':'progress','percent':pct,'file':path}, ensure_ascii=False)}\n\n"
                        break
                    try:
                        pct, path = await asyncio.wait_for(q.get(), timeout=0.2)
                        yield f"data: {json.dumps({'type':'progress','percent':pct,'file':path}, ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        continue
                await task

                size = sum(f.stat().st_size for f in Path(target_dir).rglob("*") if f.is_file())
                yield f"data: {json.dumps({'type':'complete','kind':'embedding','path':target_dir,'size':size}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'type':'status','msg':'正在安装重排模型依赖（首次可能需要几分钟）...'}, ensure_ascii=False)}\n\n"
                await ensure_reranker_dependencies()
                target_dir = str(settings.BGE_RERANKER_PATH)
                yield f"data: {json.dumps({'type':'status','msg':'依赖安装完成，开始下载 BGE-reranker 模型...'}, ensure_ascii=False)}\n\n"

                q: asyncio.Queue = asyncio.Queue()
                async def _cb(pct, path):
                    await q.put((pct, path))

                task = asyncio.create_task(download_hf_repo(settings.BGE_RERANKER_REPO, target_dir, _cb))
                while True:
                    if task.done():
                        while not q.empty():
                            pct, path = q.get_nowait()
                            yield f"data: {json.dumps({'type':'progress','percent':pct,'file':path}, ensure_ascii=False)}\n\n"
                        break
                    try:
                        pct, path = await asyncio.wait_for(q.get(), timeout=0.2)
                        yield f"data: {json.dumps({'type':'progress','percent':pct,'file':path}, ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        continue
                await task

                size = sum(f.stat().st_size for f in Path(target_dir).rglob("*") if f.is_file())
                yield f"data: {json.dumps({'type':'complete','kind':'reranker','path':target_dir,'size':size}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','msg':str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")



@router.post("/api/models/download-small/stream")
async def download_small_models_stream():
    """一键安装并下载小中文向量模型 + 小重排模型（可作为 BGE 的轻量基底）。"""
    from pathlib import Path
    from fastapi.responses import StreamingResponse
    from backend.model_setup import ensure_small_dependencies, download_hf_repo

    async def event_stream():
        try:
            yield f"data: {json.dumps({'type':'status','msg':'正在安装小模型依赖（sentence-transformers 等）...'}, ensure_ascii=False)}\n\n"
            await ensure_small_dependencies()
            yield f"data: {json.dumps({'type':'status','msg':'依赖安装完成，开始下载小中文向量模型...'}, ensure_ascii=False)}\n\n"

            # 下载小向量模型
            q: asyncio.Queue = asyncio.Queue()
            async def _cb(pct, path):
                await q.put((pct, path))
            task = asyncio.create_task(download_hf_repo(settings.SMALL_EMBEDDING_REPO, str(settings.SMALL_EMBEDDING_DIR), _cb))
            while True:
                if task.done():
                    while not q.empty():
                        pct, path = q.get_nowait()
                        yield f"data: {json.dumps({'type':'progress','percent':pct,'file':path}, ensure_ascii=False)}\n\n"
                    break
                try:
                    pct, path = await asyncio.wait_for(q.get(), timeout=0.2)
                    yield f"data: {json.dumps({'type':'progress','percent':pct,'file':path}, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    continue
            await task

            # 如果重排模型还没下载，则一并下载小重排模型
            reranker_dir = str(settings.SMALL_RERANKER_DIR or settings.BGE_RERANKER_PATH or "")
            if not reranker_dir or not Path(reranker_dir).exists():
                yield f"data: {json.dumps({'type':'status','msg':'正在下载小重排模型...'}, ensure_ascii=False)}\n\n"
                q2: asyncio.Queue = asyncio.Queue()
                async def _cb2(pct, path):
                    await q2.put((pct, path))
                task2 = asyncio.create_task(download_hf_repo(settings.SMALL_RERANKER_REPO, reranker_dir, _cb2))
                while True:
                    if task2.done():
                        while not q2.empty():
                            pct, path = q2.get_nowait()
                            yield f"data: {json.dumps({'type':'progress','percent':pct,'file':path}, ensure_ascii=False)}\n\n"
                        break
                    try:
                        pct, path = await asyncio.wait_for(q2.get(), timeout=0.2)
                        yield f"data: {json.dumps({'type':'progress','percent':pct,'file':path}, ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        continue
                await task2

            yield f"data: {json.dumps({'type':'complete','kind':'small','embedding_dir':str(settings.SMALL_EMBEDDING_DIR),'reranker_dir':reranker_dir}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','msg':str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
