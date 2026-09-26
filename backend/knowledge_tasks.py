"""知识库上传流水线：文档识别/切分/入库的长时间任务（含取消与进度上报）。

从 `backend/routers/knowledge.py` 搬出——路由不该承担分钟级的文档流水线；
`backend/routers/tasks.py` 与 `backend/main.py` 都改从本模块导入。
"""
from __future__ import annotations

import asyncio

from backend.task_center import (
    TaskCancelled,
    is_cancel_requested,
    task_manager,
    task_progress_callback,
)


async def run_knowledge_upload_task(
    task_id: str,
    data: bytes,
    filename: str,
    title: str,
    system: str,
    source: str,
    tags: str,
    username: str,
    splitter: str,
    max_ocr_pages: int,
    ocr_enabled: bool,
    region_fusion: bool = True,
    scenario_id: str = "",
):
    import uuid
    from backend.knowledge_base import get_knowledge_base
    from backend.scenario_importer import extract_text
    from backend.document_pipeline import run_document_pipeline
    from backend.document_pipeline.image_processor import auto_register_media_images
    from backend.document_pipeline.types import DocumentPipelineCancelled

    def _cancelled() -> bool:
        return is_cancel_requested(task_id)

    def _mark_cancelled(message: str = "已取消") -> None:
        task_manager.update(task_id, status="cancelled", phase="cancelled", message=message)

    if _cancelled():
        _mark_cancelled()
        return

    task_manager.update(task_id, status="running", phase="prepare", message="读取文件与旧逻辑回退文本")
    try:
        fallback_content = await asyncio.to_thread(extract_text, filename, data)
    except TaskCancelled:
        _mark_cancelled("读取阶段已取消")
        return
    except Exception as e:
        task_manager.update(task_id, status="failed", phase="prepare", error=str(e))
        return
    if _cancelled():
        _mark_cancelled("读取完成后已取消")
        return

    doc_id = uuid.uuid4().hex[:16]
    kb = get_knowledge_base()
    try:
        task_manager.update(task_id, status="running", phase="pipeline", message="文档识别/切分中")
        cb = task_progress_callback(task_id, "pipeline")
        result = await asyncio.to_thread(
            run_document_pipeline,
            data, filename, doc_id=doc_id, username=username,
            max_ocr_pages=max_ocr_pages, ocr_enabled=ocr_enabled,
            progress_callback=cb, splitter=splitter, region_fusion=region_fusion,
            cancel_callback=lambda: is_cancel_requested(task_id),
        )
        if _cancelled():
            _mark_cancelled("识别切分阶段已取消")
            return
        content = result.cleaned_text or fallback_content
        parents = result.parent_chunks
        children = result.child_chunks
        images = result.images
        tables = result.tables
        try:
            if _cancelled():
                _mark_cancelled("图片注册前已取消")
                return
            await asyncio.to_thread(auto_register_media_images, username, scenario_id, images, system=system)
        except TaskCancelled:
            _mark_cancelled("图片注册阶段已取消")
            return
        except Exception:
            pass
        pipeline_meta = result.metadata
        warning = ""
    except (TaskCancelled, DocumentPipelineCancelled):
        _mark_cancelled("识别切分阶段已取消")
        return
    except Exception as e:
        if _cancelled():
            _mark_cancelled("识别切分阶段已取消")
            return
        # 管线失败时回退旧逻辑，保证上传可用
        content = fallback_content
        parents = children = images = tables = None
        pipeline_meta = None
        warning = str(e)
        task_manager.update(task_id, status="running", phase="fallback", message=f"管线失败，使用旧文本回退：{warning}")

    if _cancelled():
        _mark_cancelled("写入知识库前已取消")
        return

    task_manager.update(task_id, status="running", phase="store", message="写入知识库")
    try:
        doc = await asyncio.to_thread(
            kb.add_document,
            title=title or filename or "上传资料",
            content=content,
            source=source,
            system=system,
            tags=[t.strip() for t in tags.split(",") if t.strip()],
            username=username,
            splitter=splitter,
            parent_chunks=parents,
            child_chunks=children,
            images=images,
            tables=tables,
            doc_id=doc_id,
            scenario_id=scenario_id,
        )
        if _cancelled():
            try:
                kb.remove_document(doc["id"], username)
            except Exception:
                pass
            _mark_cancelled("写入后取消，已回滚知识库条目")
            return
    except TaskCancelled:
        _mark_cancelled("写入知识库阶段已取消")
        return
    except Exception as e:
        task_manager.update(task_id, status="failed", phase="store", error=str(e))
        return

    if children:
        try:
            from backend.vector_store import add_document_vectors, pgvector_enabled
            if pgvector_enabled():
                if _cancelled():
                    _mark_cancelled("pgvector 写入前已取消")
                    return
                await add_document_vectors(doc_id, [
                    {
                        "chunk_id": getattr(c, "id", str(i)),
                        "block_type": getattr(c, "type", "text"),
                        "content": getattr(c, "content", ""),
                    }
                    for i, c in enumerate(children)
                ])
        except TaskCancelled:
            _mark_cancelled("pgvector 写入阶段已取消")
            return
        except Exception as e:
            task_manager.update(task_id, status="running", phase="store",
                                message=f"pgvector 写入失败（已忽略）：{e}")

    if _cancelled():
        _mark_cancelled("完成前已取消")
        return

    # P1-10: 不在 SSE 单帧内联全文/父子块；只回传可索引的摘要，完整内容走知识库接口。
    doc_summary = {
        "id": doc.get("id"),
        "title": doc.get("title"),
        "system": doc.get("system"),
        "source": doc.get("source"),
        "scenario_id": doc.get("scenario_id"),
        "content_length": len(doc.get("content") or ""),
        "parent_chunk_count": len(doc.get("parent_chunks") or []),
        "child_chunk_count": len(doc.get("child_chunks") or []),
        "image_count": len(doc.get("images") or []),
        "table_count": len(doc.get("tables") or []),
    }
    task_manager.update(
        task_id,
        status="completed",
        phase="done",
        message="上传完成",
        result={"doc": doc_summary, "pipeline": pipeline_meta, "warning": warning or None},
    )

# 兼容历史名（backend.main 与 dist/_test_task_direct.py 曾按这个名字引用）
_run_knowledge_upload_task = run_knowledge_upload_task
