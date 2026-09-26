"""知识库文档管理与检索：上传、增删改查、检索与向量模式。

长时间的上传流水线在 `backend/knowledge_tasks.py`，
文档 → 图鉴的 LLM 注入在 `backend/knowledge_llm.py`；这里只保留参数校验与转发。
"""
from __future__ import annotations

import os as _os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.config import ensure_valid_api_key, settings
from backend.engine.session import (
    get_session_for_user,
)

# 兼容搬移前的调用写法：归属校验直接复用 session 层实现
_get_session_for_user = get_session_for_user

# 装配仍在 backend.main：这里只提供本域路由
router = APIRouter(tags=["knowledge"])



@router.get("/api/knowledge")
async def list_knowledge(username: str = "default"):
    """列出当前用户可见的知识库文档（不含正文片段）。"""
    from backend.knowledge_base import get_knowledge_base
    return {"documents": get_knowledge_base().list_documents(username)}



@router.post("/api/knowledge")
async def add_knowledge(payload: dict):
    """添加知识库文档/备注（JSON，按用户名隔离）。"""
    from backend.knowledge_base import get_knowledge_base
    title = str(payload.get("title") or "未命名知识")
    content = str(payload.get("content") or "")
    system = str(payload.get("system") or "custom")
    source = str(payload.get("source") or "user")
    tags = payload.get("tags") or []
    username = str(payload.get("username") or "default")
    splitter = str(payload.get("splitter") or "semantic")
    scenario_id = str(payload.get("scenario_id") or "")
    if not content.strip():
        raise HTTPException(status_code=400, detail="内容不能为空")
    doc = get_knowledge_base().add_document(
        title=title, content=content, source=source, system=system, tags=tags,
        username=username, splitter=splitter, scenario_id=scenario_id,
    )
    return {"doc": doc}



@router.post("/api/knowledge/upload")
async def upload_knowledge(
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
    """上传 PDF/DOCX/TXT/MD 到知识库（按用户名隔离）。"""
    import uuid
    from backend.knowledge_base import get_knowledge_base
    from backend.scenario_importer import extract_text
    from backend.document_pipeline import run_document_pipeline
    from backend.document_pipeline.image_processor import auto_register_media_images

    data = await file.read()
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件不能超过 30MB")
    try:
        fallback_content = extract_text(file.filename or "", data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    doc_id = uuid.uuid4().hex[:16]
    try:
        result = run_document_pipeline(data, file.filename or "", doc_id=doc_id,
                                       username=username, max_ocr_pages=max_ocr_pages,
                                       ocr_enabled=ocr_enabled, splitter=splitter,
                                       region_fusion=region_fusion)
        content = result.cleaned_text or fallback_content
        parents = result.parent_chunks
        children = result.child_chunks
        images = result.images
        tables = result.tables
        try:
            auto_register_media_images(username, scenario_id, images, system=system)
        except Exception:
            pass
    except Exception:
        # 管线失败时回退到旧逻辑，保证上传可用
        result = None
        content = fallback_content
        parents = children = images = tables = None

    doc = get_knowledge_base().add_document(
        title=title or file.filename or "上传资料",
        content=content,
        source=source,
        system=system,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        username=username, splitter=splitter,
        parent_chunks=parents, child_chunks=children,
        images=images, tables=tables, doc_id=doc_id, scenario_id=scenario_id,
    )
    return {"doc": doc, "pipeline": result.metadata if result else None}



# ── 长时间任务 / SSE 进度 ─────────────────────────────────────

# 上传流水线与 LLM 图鉴注入已搬到服务模块（路由只做参数校验与转发）
from backend.knowledge_llm import extract_media_entries

@router.delete("/api/knowledge/{doc_id}")
async def delete_knowledge(doc_id: str, username: str = "default"):
    from backend.knowledge_base import get_knowledge_base
    if not get_knowledge_base().remove_document(doc_id, username):
        raise HTTPException(status_code=404, detail="知识文档不存在或无权删除")
    return {"deleted": True}


@router.put("/api/knowledge/{doc_id}")
async def update_knowledge(doc_id: str, payload: dict, username: str = "default"):
    """编辑知识文档（标题/正文/标签/规则系统）；正文变了会重新切块并重建父子块。"""
    from backend.knowledge_base import get_knowledge_base
    content = payload.get("content")
    doc = get_knowledge_base().update_document(
        doc_id,
        title=payload.get("title"),
        content=None if content is None else str(content),
        tags=payload.get("tags"),
        system=payload.get("system"),
        username=username,
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="知识文档不存在或无权修改")
    return {"document": {"id": doc.get("id"), "title": doc.get("title"),
                         "system": doc.get("system"), "tags": doc.get("tags"),
                         "chunks": len(doc.get("chunks") or [])}}



@router.post("/api/knowledge/retrieve")
async def retrieve_knowledge(payload: dict):
    """RAG 检索：按查询返回最相关的知识片段（按用户名隔离）。"""
    from backend.knowledge_base import get_knowledge_base
    query = str(payload.get("query") or "")
    system = payload.get("system")
    top_k = int(payload.get("top_k") or 5)
    username = str(payload.get("username") or "default")
    scenario_id = str(payload.get("scenario_id") or "") or None
    if not query.strip():
        raise HTTPException(status_code=400, detail="查询不能为空")
    results = get_knowledge_base().retrieve(query, system=system, top_k=top_k, username=username, scenario_id=scenario_id)
    return {"results": results}



@router.post("/api/knowledge/pgvector-search")
async def pgvector_search(payload: dict):
    """可选 pgvector 向量检索；未启用时回退本地知识库检索。"""
    from backend.knowledge_base import get_knowledge_base
    from backend.vector_store import pgvector_enabled, search_document_vectors
    query = str(payload.get("query") or "")
    top_k = int(payload.get("top_k") or 10)
    system = payload.get("system")
    username = str(payload.get("username") or "default")
    if not query.strip():
        raise HTTPException(status_code=400, detail="查询不能为空")
    if pgvector_enabled():
        results = await search_document_vectors(query, top_k=top_k)
        return {"enabled": True, "results": results}
    return {
        "enabled": False,
        "results": get_knowledge_base().retrieve(query, system=system, top_k=top_k, username=username),
    }



@router.post("/api/knowledge/llm-process")
async def knowledge_llm_process(payload: dict):
    """使用 LLM 对知识库文档做智能切分与图鉴注入（地点/生物/法术）。"""
    username = str(payload.get("username") or "default")
    scenario_id = str(payload.get("scenario_id") or "")
    doc_id = str(payload.get("doc_id") or "")
    api_key = str(payload.get("api_key") or "")
    model_name = str(payload.get("model_name") or "")
    base_url = str(payload.get("base_url") or "")
    try:
        api_key = ensure_valid_api_key(api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    model = model_name or settings.LLM_MODEL_NAME
    base_url = base_url or settings.LLM_BASE_URL
    if not model:
        raise HTTPException(status_code=400, detail="请提供模型名称")

    return await extract_media_entries(
        username=username, doc_id=doc_id, scenario_id=scenario_id,
        api_key=api_key, base_url=base_url, model=model,
    )




@router.get("/api/knowledge/vector-mode")
async def get_knowledge_vector_mode():
    from backend.knowledge_base import get_knowledge_base
    kb = get_knowledge_base()
    return {
        "mode": kb.get_vector_mode(),
        "model_ready": kb.model_ready(),
        "small_ready": bool((settings.SMALL_EMBEDDING_DIR or "").strip() and _os.path.isdir(settings.SMALL_EMBEDDING_DIR)),
        "bge_ready": bool((settings.BGE_M3_DIR or "").strip() and _os.path.isdir(settings.BGE_M3_DIR)) or bool((settings.BGE_MODEL_PATH or "").strip() and _os.path.exists(settings.BGE_MODEL_PATH)),
        "reranker_ready": kb.reranker_ready(),
    }



@router.post("/api/knowledge/vector-mode")
async def set_knowledge_vector_mode(payload: dict):
    from backend.knowledge_base import get_knowledge_base
    mode = str(payload.get("mode") or "local")
    if mode not in ("local", "small", "bge"):
        raise HTTPException(status_code=400, detail="mode 仅支持 local、small 或 bge")
    kb = get_knowledge_base()
    kb.set_vector_mode(mode)
    return {
        "mode": kb.get_vector_mode(),
        "model_ready": kb.model_ready(),
        "small_ready": bool((settings.SMALL_EMBEDDING_DIR or "").strip() and _os.path.isdir(settings.SMALL_EMBEDDING_DIR)),
        "bge_ready": bool((settings.BGE_M3_DIR or "").strip() and _os.path.isdir(settings.BGE_M3_DIR)) or bool((settings.BGE_MODEL_PATH or "").strip() and _os.path.exists(settings.BGE_MODEL_PATH)),
        "reranker_ready": kb.reranker_ready(),
    }



@router.post("/api/knowledge/seed")
async def seed_knowledge():
    """重新填充内置规则备注（幂等）。"""
    from backend.knowledge_base import get_knowledge_base
    get_knowledge_base().seed_builtin_rules()
    return {"seeded": True}
