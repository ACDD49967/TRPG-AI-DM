"""账号数据删除：删号时把它名下的内容一起清掉。

只服务"用户主动删自己的账号"这一条路径：路由层先验密码并删除账号行，
这里负责清理按用户名分目录的内容（角色卡/存档/剧本/扩展/媒体/长期记忆）、
归该用户所有的知识库文档、以及还在内存里的会话与其世界状态文件。

失败一律按"尽力而为"处理并把结果回报给调用方：删号不该因为某个可选目录
不存在或某个向量库条目删不掉而半途失败。
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from backend.paths import safe_username


def user_data_dirs(username: str) -> list[Path]:
    """该用户名下的内容目录（按各管理器的根目录现取，便于测试替换）。"""
    from backend.character_card_manager import CHAR_ROOT
    from backend.extension_manager import EXT_ROOT
    from backend.long_term_memory import VAULT_ROOT
    from backend.media_store import MEDIA_ROOT
    from backend.save_manager import SAVE_ROOT
    from backend.scenario_store import SCENARIO_DIR

    safe = safe_username(username)
    return [
        Path(CHAR_ROOT) / safe,
        Path(SAVE_ROOT) / safe,
        Path(SCENARIO_DIR) / safe,
        Path(EXT_ROOT) / safe,
        Path(MEDIA_ROOT) / safe,
        Path(VAULT_ROOT) / safe,
    ]


def _drop_sessions(username: str) -> tuple[int, list[str]]:
    """清掉该用户的在内存会话，并删掉它们的世界状态文件。"""
    from backend.engine.session import session_manager

    removed = 0
    world_files: list[str] = []
    for session_id, state in list(session_manager._sessions.items()):  # noqa: SLF001 - 会话表本就是模块私有单例
        if getattr(state, "username", "") != username:
            continue
        ws = getattr(state, "world_state", None)
        storage_dir = getattr(ws, "_storage_dir", None) if ws is not None else None
        state.request_abort()
        session_manager.remove_session(session_id)
        removed += 1
        if storage_dir:
            path = Path(storage_dir) / f"{session_id}.json"
            try:
                path.unlink()
                world_files.append(str(path))
            except FileNotFoundError:
                pass
            except OSError:
                pass
    return removed, world_files


def _drop_knowledge_docs(username: str) -> int:
    """删除归该用户所有的知识库文档（含向量库条目）。"""
    from backend.knowledge_base import get_knowledge_base

    kb = get_knowledge_base()
    kb.load()
    owned = [d["id"] for d in kb.documents if str(d.get("owner") or "") == username]
    if not owned:
        return 0
    try:
        from backend.local_vector_store import delete_doc_vectors
    except Exception:  # 向量库可选，缺了也要能删文档
        delete_doc_vectors = None  # type: ignore[assignment]
    for doc_id in owned:
        if delete_doc_vectors is not None:
            try:
                delete_doc_vectors(doc_id)
            except Exception:
                pass
    kb.documents = [d for d in kb.documents if str(d.get("owner") or "") != username]
    kb.save()
    return len(owned)


async def delete_account_data(username: str) -> dict[str, Any]:
    """清空该用户名下的全部内容，返回删了什么（供接口回执与人工核对）。"""
    name = (username or "").strip()
    if not name:
        return {"dirs": [], "knowledge_docs": 0, "sessions": 0, "world_state_files": []}

    sessions, world_files = _drop_sessions(name)
    knowledge_docs = _drop_knowledge_docs(name)

    removed_dirs: list[str] = []
    for path in user_data_dirs(name):
        if not path.exists():
            continue
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            removed_dirs.append(str(path))

    return {
        "dirs": removed_dirs,
        "knowledge_docs": knowledge_docs,
        "sessions": sessions,
        "world_state_files": world_files,
    }


__all__ = ["delete_account_data", "user_data_dirs"]
