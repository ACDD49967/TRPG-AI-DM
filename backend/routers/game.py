"""游戏会话：新局创建、行动提交、SSE 事件流、笔记与图谱。"""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.engine.dm_agent import process_player_action
from backend.engine.session import (
    GameSessionState,
    get_session_for_user,
    push_event,
    push_narrative_flush,
    sse_event_generator,
)
from backend.schemas import (
    ActionAcceptedResponse,
    ActionRequest,
    NewGameRequest,
    NewGameResponse,
)

# 兼容搬移前的调用写法：归属校验直接复用 session 层实现
_get_session_for_user = get_session_for_user

# 装配仍在 backend.main：这里只提供本域路由
router = APIRouter(tags=["game"])



# 新局创建的实现已搬到 backend/game_setup（路由只做装配）
from backend.game_setup import (  # noqa: F401  再导出，兼容旧的 _normalize_known_spells 用法
    _normalize_known_spells, create_game_session,
)

@router.post("/api/game/new", response_model=NewGameResponse)
async def create_new_game(request: NewGameRequest):
    """创建新游戏——生成角色和会话，返回 SSE 连接地址（实现见 backend.game_setup）。"""
    return await create_game_session(request)




@router.post("/api/game/{session_id}/action", response_model=ActionAcceptedResponse)
async def submit_action(session_id: str, request: ActionRequest, username: str = "default"):
    """提交玩家行动——触发 AI DM 处理并生成叙事。

    处理是异步的：此端点立即返回 accepted:true，
    实际的叙事生成在后台进行，通过 SSE 推送给前端。
    """
    state = _get_session_for_user(session_id, username)

    if not state.check_rate_limit():
        raise HTTPException(status_code=429, detail="操作太快，请稍等片刻再行动")

    if state.status != "active":
        raise HTTPException(status_code=400, detail="会话不是活跃状态")

    state.mark_action()

    # 在后台任务中启动 AI 处理
    asyncio.create_task(_handle_player_action(state, request.player_input))

    return ActionAcceptedResponse(accepted=True)



async def _handle_player_action(state: GameSessionState, player_input: str):
    """后台任务：处理玩家行动并推送 SSE 事件。"""
    try:
        await process_player_action(state, player_input)
        # P1-21：回合结束后把内存权威状态快照回写 SQLite，供审计/恢复辅助。
        try:
            from backend.session_store import persist_session_snapshot
            await persist_session_snapshot(state)
        except Exception:
            pass
    except Exception as e:
        await push_event(state, "error", {
            "code": "INTERNAL_ERROR",
            "msg": f"处理失败: {str(e)}",
        })
        await push_event(state, "end_of_turn", {})



@router.get("/api/game/{session_id}/stream")
async def stream_events(session_id: str, request: Request, last_event_seq: int = 0, username: str = "default"):
    """SSE 长连接——推送游戏事件流。

    支持 last_event_seq 查询参数与标准 Last-Event-ID 头部；
    重连时只补发缺失事件，不重新生成开场白。
    """
    state = _get_session_for_user(session_id, username)
    last_id = max(0, int(last_event_seq or 0))
    header_id = (request.headers.get("last-event-id") or "").strip()
    if header_id.isdigit():
        last_id = max(last_id, int(header_id))

    return StreamingResponse(
        sse_event_generator(state, last_event_id=last_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )



@router.get("/api/game/{session_id}/journal")
async def get_player_journal(session_id: str, username: str = "default"):
    """获取玩家笔记——侧边栏显示当前场景、NPC(可见信息)、剧情进度。

    这个端点返回仅对玩家可见的信息：
    - 当前场景（位置/时间/天气/氛围）
    - NPC按态度分组（仅可见字段）
    - 剧情旗标
    - 已发现地点
    """
    state = _get_session_for_user(session_id, username)

    ws = getattr(state, 'world_state', None)
    if ws is None:
        return {"scene": {"location": "未知", "time": "?", "weather": "", "atmosphere": ""},
                "npcs": {"allies": [], "enemies": [], "neutrals": [], "total": 0},
                "plot_flags": [], "locations": []}

    return ws.to_player_journal()



@router.get("/api/game/{session_id}/graph")
async def get_game_graph(session_id: str, query: str | None = None,
                         name: str | None = None, depth: int = 1, username: str = "default",
                         view: str = "player"):
    """返回当前会话的知识图谱（默认玩家安全视图，未暴露信息用 ??? 代替；view=dm 返回完整图）。"""
    state = _get_session_for_user(session_id, username)
    ws = getattr(state, "world_state", None)
    if ws is None:
        return {"graph": {"nodes": [], "edges": []}, "search": []}
    from backend.engine.knowledge_graph import (
        build_knowledge_graph, build_player_graph, get_local_subgraph,
        get_local_subgraph_from_graph, search_graph_nodes,
    )
    if view == "dm":
        if name:
            graph = get_local_subgraph(ws, name, depth=depth)
        else:
            graph = build_knowledge_graph(ws)
    else:
        player_full = build_player_graph(ws)
        graph = get_local_subgraph_from_graph(player_full, name, depth=depth) if name else player_full
    search = search_graph_nodes(graph, query) if query else []
    return {"graph": graph, "search": search}



@router.post("/api/game/{session_id}/equip")
async def equip_item_api(session_id: str, payload: dict, username: str = "default"):
    """玩家/前端手动装备或卸下物品，实时推送状态更新。"""
    state = _get_session_for_user(session_id, username)
    from backend.engine.dm_agent import _exec_equip_item
    result = await _exec_equip_item(payload, state)
    return {"result": result}



@router.post("/api/game/{session_id}/abort")
async def abort_generation(session_id: str, username: str = "default"):
    """中断当前 AI 生成——玩家点击"跳过"按钮时调用。"""
    state = _get_session_for_user(session_id, username)

    state.request_abort()
    await push_narrative_flush(state, "[生成已中断]")

    return {"aborted": True}



@router.delete("/api/game/{session_id}")
async def delete_game_session(session_id: str, username: str = "default"):
    """删除本局会话：清掉内存会话与它的世界状态文件。

    存档（/api/saves）与角色卡是独立资源、各有删除接口，这里不动它们，
    避免"删一局"顺手删掉玩家想留的存档。
    """
    from backend.engine.session import session_manager

    state = _get_session_for_user(session_id, username)
    ws = getattr(state, "world_state", None)
    storage_dir = getattr(ws, "_storage_dir", None) if ws is not None else None
    state.request_abort()
    session_manager.remove_session(session_id)

    world_state_removed = False
    if storage_dir:
        try:
            (Path(storage_dir) / f"{session_id}.json").unlink()
            world_state_removed = True
        except FileNotFoundError:
            pass
        except OSError as e:
            print(f"[Session] 删除世界状态文件失败（已忽略）: {e}")
    return {"deleted": True, "session_id": session_id, "world_state_removed": world_state_removed}
