"""会话生命周期：创建/查询/回收活跃会话，并按账号校验归属（从 session.py 拆出）。

MVP 阶段用内存字典，生产环境要换 Redis；归属校验供各路由复用。
"""
import time

from backend.engine.session_state import GameSessionState


class SessionManager:
    """全局会话管理器。

    管理所有活跃游戏会话的生命周期。
    MVP 阶段使用内存字典存储，生产环境需替换为 Redis 后端。
    """

    def __init__(self):
        self._sessions: dict[str, GameSessionState] = {}

    def create_session(
        self,
        session_id: str,
        character_id: str,
        character_name: str,
        character_info: dict,
        api_key: str | None = None,
        model_name: str | None = None,
        username: str = "default",
    ) -> GameSessionState:
        """创建并注册一个新的游戏会话。"""
        state = GameSessionState(
            session_id=session_id,
            character_id=character_id,
            character_name=character_name,
            character_info=character_info,
            api_key=api_key,
            model_name=model_name,
            username=username,
        )
        self._sessions[session_id] = state
        return state

    def get_session(self, session_id: str) -> GameSessionState | None:
        """根据 ID 查找活跃会话。"""
        return self._sessions.get(session_id)

    def remove_session(self, session_id: str):
        """从内存中移除会话（不影响数据库记录）。"""
        state = self._sessions.pop(session_id, None)
        if state is not None:
            state.subscribers.clear()

    def prune_idle(self, max_idle_seconds: float = 7200.0) -> list[str]:
        """回收长时间无活动且没有 SSE 订阅者的会话。"""
        now = time.time()
        removed: list[str] = []
        for session_id, state in list(self._sessions.items()):
            if state.subscribers:
                continue
            idle = now - float(getattr(state, "last_active_at", now))
            if state.status != "active" or idle > max_idle_seconds:
                self._sessions.pop(session_id, None)
                removed.append(session_id)
        return removed

    def is_active(self, session_id: str) -> bool:
        """检查会话是否在内存中（是否活跃）。"""
        return session_id in self._sessions


# 全局单例
session_manager = SessionManager()


def get_session_for_user(session_id: str, username: str = "default") -> GameSessionState:
    """按会话归属校验并返回状态；不存在/非归属返回 404。

    放在会话层，供主路由与拆分出的路由模块共用，避免各路由重复实现归属校验。
    """
    from fastapi import HTTPException

    state = session_manager.get_session(session_id)
    if state is None or state.username != (username or "default"):
        raise HTTPException(status_code=404, detail="会话不存在或已结束")
    return state
