"""长期记忆的增删改查接口。

长期记忆（Markdown 记忆库 + SQLite 索引）此前**只能创建与检索**：
`delete_facts` 没有任何工具或接口调用，玩家既看不到"系统记住了什么"，
也无法删掉一条记错的事实——"所有内容可增删改查"在这里是缺的。

写入与删除复用存储层（`memory_store`），因此索引、Markdown 页面与语义事实
三条数据保持一致，不会出现"删了页面但索引还在"这类分叉。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/memories", tags=["memories"])


def _public(memory: dict | None) -> dict | None:
    if not memory:
        return None
    # vault_path 是服务器本地路径，不对外暴露
    return {k: v for k, v in memory.items() if k != "vault_path"}


def _types(raw) -> list[str] | None:
    if isinstance(raw, str):
        items = [t.strip() for t in raw.split(",")]
    elif isinstance(raw, list):
        items = [str(t).strip() for t in raw]
    else:
        items = []
    picked = [t for t in items if t]
    return picked or None


@router.get("")
async def list_memories(username: str = "default", limit: int = 50, memory_types: str = ""):
    """列出（最近的）长期记忆，供玩家/DM 核对系统记住了什么。"""
    from backend.memory_retrieve import load_recent_memories

    limit = max(1, min(int(limit or 50), 200))
    items = load_recent_memories(username, limit=limit, memory_types=_types(memory_types))
    return {"memories": [_public(item) for item in items]}


@router.post("")
async def create_memory(payload: dict):
    """新增一条记忆（与 DM 的 add_memory / record_plot_memory 走同一存储层）。"""
    from backend.memory_manage import load_memory
    from backend.memory_store import store_memory

    username = str(payload.get("username") or "default")
    content = str(payload.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="缺少 content（记忆正文）")
    mem_id = store_memory(
        username, content,
        memory_type=str(payload.get("memory_type") or "semantic"),
        summary=str(payload.get("summary") or ""),
        entities=payload.get("entities") or [],
        tags=payload.get("tags") or [],
        importance=float(payload.get("importance") or 0.5),
        confidence=float(payload.get("confidence") or 0.7),
        session_id=str(payload.get("session_id") or ""),
        turn=int(payload.get("turn") or 0),
        source=str(payload.get("source") or "api"),
    )
    if not mem_id:
        raise HTTPException(status_code=400, detail="记忆正文为空，未写入")
    return {"id": mem_id, "memory": _public(load_memory(username, mem_id))}


@router.put("/{mem_id}")
async def update_memory_api(mem_id: str, payload: dict):
    """改一条记忆。id 是内容哈希：改正文后返回的是**新**记忆（旧 id 随之失效）。"""
    from backend.memory_manage import update_memory

    username = str(payload.get("username") or "default")
    memory = update_memory(
        username, mem_id,
        content=payload.get("content"),
        summary=payload.get("summary"),
        memory_type=payload.get("memory_type"),
        importance=payload.get("importance"),
        confidence=payload.get("confidence"),
        tags=payload.get("tags"),
        entities=payload.get("entities"),
    )
    if memory is None:
        raise HTTPException(status_code=404, detail="记忆不存在（或新正文为空）")
    return {"memory": _public(memory)}


@router.delete("/{mem_id}")
async def delete_memory_api(mem_id: str, username: str = "default"):
    """删一条记忆：SQLite 行 + Markdown 页面 + 语义事实一起清掉。"""
    from backend.memory_manage import delete_memory

    if not delete_memory(username, mem_id):
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"deleted": mem_id}
