"""剧本导入：上传文件 → 切分 → 建世界 → 落库，全程 SSE 汇报进度。

从 `backend/routers/scenarios.py` 拆出（这个端点是该文件里最长的一段）。
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from backend.task_center import TaskCancelled

router = APIRouter()


@router.post("/api/scenarios/import")
async def import_scenario(
    request: Request,
    file: UploadFile = File(...),
    splitter: str = Form("recursive"),
    chunk_size: int = Form(900),
    title: str = Form(""),
    username: str = Form("default"),
    description: str = Form(""),
    tone: str = Form("史诗奇幻"),
    system: str | None = Form(None),
    custom_rules: str = Form(""),
    custom_classes: str = Form("[]"),
    custom_skills: str = Form("[]"),
    extra_attributes: str = Form("{}"),
    character_name: str = Form("冒险者"),
    race: str = Form("人类"),
    char_class: str = Form("战士"),
    character_level: int = Form(1),
    api_key: str | None = Form(None),
    model_name: str | None = Form(None),
    base_url: str | None = Form(None),
    thinking_strength: str = Form("medium"),
):
    """上传剧本文件（pdf/txt/docx/doc/md/图片）→ 与知识库相同的识别/切分 → 生成并保存新剧本。

    识别、清洗、递归父子切分都在线程中执行，并通过 SSE 推送进度；
    前端断开连接或点击取消时，服务端会设置 cancel_event 中断管线。
    """
    from backend.scenario_importer import (
        detect_game_system,
        extract_text,
        generate_scenario_from_text,
        split_text,
    )
    from backend.engine.game_systems import SYSTEM_TYPES
    from backend.document_pipeline import run_document_pipeline
    from backend.document_pipeline.types import DocumentPipelineCancelled

    if splitter not in ("naive", "recursive", "semantic", "llm"):
        raise HTTPException(status_code=400, detail="splitter 仅支持 naive、recursive、semantic 或 llm")
    if chunk_size < 200 or chunk_size > 4000:
        raise HTTPException(status_code=400, detail="chunk_size 需在 200-4000 之间")

    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件不能超过 20MB")
    filename = file.filename or ""

    queue: asyncio.Queue = asyncio.Queue()
    cancel_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _emit(item: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, item)

    def progress(label: str, percent: int, detail: str = "") -> None:
        if cancel_event.is_set():
            raise TaskCancelled("剧本导入已取消")
        _emit({"type": "progress", "label": label, "percent": percent, "detail": detail})

    def stream_token(token: str) -> None:
        if cancel_event.is_set():
            raise TaskCancelled("剧本导入已取消")
        _emit({"type": "gen_token", "token": token})

    async def run():
        nonlocal system
        try:
            progress("读取文件", 2, "正在提取文本")
            text = await asyncio.to_thread(extract_text, filename, data)
            if cancel_event.is_set():
                raise TaskCancelled("剧本导入已取消")
            if not text.strip():
                raise ValueError("文件中没有可用的剧本文本")

            _pipeline_result = None
            progress("文档识别", 4, "统一文档管线识别/清洗/切分")
            try:
                def pipeline_progress(current: int, total: int, detail: str | None = None) -> None:
                    if cancel_event.is_set():
                        raise TaskCancelled("剧本导入已取消")
                    pct = 4 + int(28 * (current / max(1, total)))
                    progress("文档识别/切分", min(32, pct), detail or f"{current}/{total}")

                _pipeline_result = await asyncio.to_thread(
                    run_document_pipeline,
                    data, filename, doc_id="scenario_import", username=username,
                    splitter=splitter, progress_callback=pipeline_progress,
                    child_max_chars=chunk_size,
                    parent_max_chars=max(4000, chunk_size * 4),
                    cancel_callback=lambda: cancel_event.is_set(),
                )
                if _pipeline_result.cleaned_text.strip():
                    text = _pipeline_result.cleaned_text
            except (TaskCancelled, DocumentPipelineCancelled):
                raise TaskCancelled("剧本导入已取消")
            except Exception as e:
                progress("文档管线", 6, f"管线失败，使用旧文本回退：{e}")

            if cancel_event.is_set():
                raise TaskCancelled("剧本导入已取消")
            if not text.strip():
                raise ValueError("文件中没有可用的剧本文本")

            # 剧本切分与知识库保持一致：优先使用文档管线生成的 child_chunks
            chunks: list[str] = []
            if splitter != "llm":
                if _pipeline_result is not None and _pipeline_result.child_chunks:
                    chunks = [
                        c.content for c in _pipeline_result.child_chunks
                        if getattr(c, "content", "")
                    ]
                if not chunks:
                    chunks = split_text(text, mode=splitter, chunk_size=chunk_size)
                if not chunks:
                    raise ValueError("切分后没有生成任何片段")

            if not system or system == "auto":
                system = detect_game_system(text, title)
            if system not in SYSTEM_TYPES:
                raise ValueError(f"未知规则系统: {system}，可选: {', '.join(SYSTEM_TYPES)}")

            try:
                custom_classes_list = json.loads(custom_classes or "[]") or []
                custom_skills_list = json.loads(custom_skills or "[]") or []
                extra_attributes_dict = json.loads(extra_attributes or "{}") or {}
            except Exception:
                custom_classes_list, custom_skills_list, extra_attributes_dict = [], [], {}

            if cancel_event.is_set():
                raise TaskCancelled("剧本导入已取消")
            result = await generate_scenario_from_text(
                source_text=text,
                chunks=chunks,
                title=title,
                username=username,
                description=description,
                tone=tone,
                system=system,
                custom_rules=custom_rules,
                custom_classes=custom_classes_list,
                custom_skills=custom_skills_list,
                extra_attributes=extra_attributes_dict,
                character_name=character_name,
                race=race,
                char_class=char_class,
                character_level=character_level,
                api_key=api_key,
                model_name=model_name,
                base_url=base_url,
                splitter=splitter,
                target_score=75,
                max_revisions=1,
                thinking_strength=thinking_strength,
                progress_callback=progress,
                token_callback=stream_token,
            )
            if cancel_event.is_set():
                raise TaskCancelled("剧本导入已取消")

            # 把复合剧本中的图片/地图/生物图谱关联到该剧本，而不是全局知识库
            if _pipeline_result is not None and _pipeline_result.images:
                try:
                    from backend.document_pipeline.image_processor import auto_register_media_images
                    await asyncio.to_thread(
                        auto_register_media_images, username,
                        str(result.get("scenario_id") or ""),
                        _pipeline_result.images, system,
                    )
                except Exception:
                    pass

            # 剧本原件绑定到该剧本知识库：采用知识库父子块/图片/表格方法
            if _pipeline_result is not None:
                try:
                    from backend.knowledge_base import get_knowledge_base
                    kb = get_knowledge_base()
                    scenario_id_new = str(result.get("scenario_id") or "")
                    scenario_kb_source = f"scenario:{scenario_id_new}"

                    def _bind_kb():
                        for d in kb.list_documents(username, include_scenario=True):
                            if d.get("source") == scenario_kb_source or d.get("scenario_id") == scenario_id_new:
                                kb.remove_document(d["id"], username)
                        kb.add_document(
                            title=f"剧本原件：{title or '导入剧本'}",
                            content=_pipeline_result.cleaned_text or text,
                            source=scenario_kb_source,
                            system=system,
                            tags=["剧本原件", system, splitter],
                            username=username,
                            parent_chunks=_pipeline_result.parent_chunks,
                            child_chunks=_pipeline_result.child_chunks,
                            images=_pipeline_result.images,
                            tables=_pipeline_result.tables,
                            scenario_id=scenario_id_new,
                        )
                    await asyncio.to_thread(_bind_kb)
                except Exception as e:
                    print(f"[Scenario] 剧本原件知识库绑定失败（不影响剧本生成）: {e}")

            _emit({"type": "__complete__", "data": result})
        except TaskCancelled:
            _emit({"type": "__cancelled__"})
        except Exception as e:
            _emit({"type": "__error__", "msg": f"剧本生成失败: {e}"})

    async def event_stream():
        task = asyncio.create_task(run())
        try:
            while True:
                if await request.is_disconnected():
                    cancel_event.set()
                    task.cancel()
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                if item["type"] == "progress":
                    yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                    continue
                if item["type"] == "gen_token":
                    yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                    continue
                if item["type"] == "__cancelled__":
                    yield f"data: {json.dumps({'type':'error','msg':'已取消'}, ensure_ascii=False)}\n\n"
                    break
                if item["type"] == "__error__":
                    yield f"data: {json.dumps({'type':'error','msg':item['msg']}, ensure_ascii=False)}\n\n"
                    break
                result = item["data"]
                result["type"] = "complete"
                yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
                break
        finally:
            if not task.done():
                cancel_event.set()
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
