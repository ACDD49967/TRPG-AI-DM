"""观测接口：回合阶段耗时、模型调用次数、token 用量与失败原因。"""
from __future__ import annotations

from fastapi import APIRouter

from backend.engine.session import get_session_for_user

router = APIRouter(prefix="/api/game", tags=["observability"])

_EMPTY_SNAPSHOT = {
    "totals": {
        "model_calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
        "total_tokens": 0, "failures": 0,
    },
    "recent_turns": [],
    "active_turn": None,
}


@router.get("/{session_id}/metrics")
async def get_game_metrics(session_id: str, username: str = "default"):
    """返回当前会话的用量统计；统计不可用时返回零值快照，不影响前端。"""
    state = get_session_for_user(session_id, username)
    telemetry = getattr(state, "telemetry", None)
    return telemetry.snapshot() if telemetry is not None else dict(_EMPTY_SNAPSHOT)


system_router = APIRouter(prefix="/api/system", tags=["observability"])


@system_router.get("/warmup")
async def get_warmup_status():
    """后台预热状态：state/stages_ms 便于确认模型与检索索引是否就绪。"""
    from backend.engine.warmup import status

    return status()
