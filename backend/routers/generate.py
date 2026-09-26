"""世界大纲与角色属性的生成接口（含流式）。"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI

from backend.config import ensure_valid_api_key, settings
from backend.logging_utils import get_logger
from backend.engine.session import (
    get_session_for_user,
)
from backend.schemas import (
    GenerateAttributesRequest,
    WorldGenRequest,
)
from backend.character_generation import generate_character_payload


# 兼容搬移前的调用写法：归属校验直接复用 session 层实现
_get_session_for_user = get_session_for_user

# 装配仍在 backend.main：这里只提供本域路由
router = APIRouter(tags=["generation"])

@router.post("/api/generate/world")
async def generate_world(request: WorldGenRequest):
    """多Agent分层生成TRPG冒险世界大纲——5步生成+迭代评分至90+。

    返回大纲文本、评分、评分历史、以及结构化的世界状态（NPC/旗标/地点）。
    """
    from backend.engine.world_builder import build_world

    player_input = f"""冒险基调: {request.tone}
角色: {request.character_name}, {request.race} {request.char_class}, Lv.{request.character_level}
描述: {request.description}"""

    if not (request.model_name or settings.LLM_MODEL_NAME):
        raise HTTPException(status_code=400, detail="请先选择或填写模型名称")
    try:
        api_key = ensure_valid_api_key(request.api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        outline_text, score, history, world_state = await build_world(
            player_input=player_input,
            reference_script=request.description,  # 玩家描述即为参考剧本
            api_key=api_key,
            model_name=request.model_name,
            base_url=request.base_url,
            game_system=request.game_system,
            custom_rules=request.custom_rules or "",
            custom_classes=request.custom_classes,
            custom_skills=request.custom_skills,
            extra_attributes=request.extra_attributes,
            target_score=75,
            max_revisions=1,
            thinking_strength=request.thinking_strength,
            username=request.username,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"世界生成失败: {e}") from e

    # 提取 NPC 和旗标摘要
    npc_summary = [{"name": n.name, "role": n.role, "attitude": n.attitude}
                   for n in world_state.npcs]
    flag_summary = [{"key": f.key, "status": f.status} for f in world_state.plot_flags]

    # 自动保存剧本
    ws_json = json.dumps({
        "world_outline": outline_text,
        "npcs": [{"name":n.name,"race":n.race,"role":n.role,"location":n.location,
                   "attitude":n.attitude,"alive":n.alive,"personality":n.personality,
                   "motivation":n.motivation,"secret":n.secret,
                   "relation_to_plot":n.relation_to_plot,"visibility":n.visibility.to_dict(),"discovered":n.discovered}
                  for n in world_state.npcs],
        "plot_flags": [{"key":f.key,"status":f.status,"description":f.description,"consequence":f.consequence,"visible":f.visible}
                       for f in world_state.plot_flags],
        "locations": [{"name":l.name,"description":l.description,"status":l.status,"type":l.type,"culture":l.culture,"notable_figures":l.notable_figures,"dangers":l.dangers,"secrets":l.secrets,"secret_revealed":l.secret_revealed,"related_locations":l.related_locations,"related_npcs":l.related_npcs,"related_creatures":l.related_creatures,"discovered":l.discovered}
                      for l in world_state.locations],
        "world_rules": world_state.world_rules,
    }, ensure_ascii=False)
    from backend.scenario_importer import generate_summary
    from backend.scenario_store import create_scenario
    summary_client = AsyncOpenAI(
        api_key=api_key,
        base_url=request.base_url or settings.LLM_BASE_URL,
    )
    summary_model = request.model_name or settings.LLM_MODEL_NAME
    summary = await generate_summary(summary_client, summary_model, outline_text, request.description)
    saved = create_scenario(
        world_outline=outline_text, world_state_json=ws_json,
        reference_script=request.description, custom_rules=request.custom_rules or "",
        custom_classes=request.custom_classes, custom_skills=request.custom_skills,
        extra_attributes=request.extra_attributes, notes="",
        title=outline_text.split("\n")[0].replace("#", "").strip()[:60],
        description=request.description[:200], summary=summary,
        system=request.game_system, tone=request.tone,
        character_name=request.character_name, race=request.race,
        char_class=request.char_class, level=request.character_level,
        score=score, username=request.username,
    )
    scenario_id = saved.id
    try:
        from backend.media_manager import sync_scenario_bestiary, sync_scenario_maps, sync_scenario_spells
        sync_scenario_maps(request.username, scenario_id, world_state.locations, request.game_system)
        sync_scenario_bestiary(request.username, scenario_id, world_state.creatures, request.game_system)
        sync_scenario_spells(request.username, scenario_id, world_state.spells, request.game_system)
    except Exception as e:
        get_logger("scenario_sync").warning("sync_scenario_* 失败（已忽略）: %s", e, exc_info=True)

    return {
        "scenario_id": scenario_id,
        "content": outline_text,
        "summary": summary,
        "system": request.game_system,
        "score": score,
        "scores_detail": {},  # 多步生成不逐项返回详情
        "revision_history": history,
        "npcs": npc_summary,
        "plot_flags": flag_summary,
        "world_rules": world_state.world_rules,
        # 序列化 WorldState 以便前端传递给游戏创建
        "world_state_json": json.dumps({
            "world_outline": world_state.world_outline,
            "world_rules": world_state.world_rules,
            "npcs": [{"name":n.name,"race":n.race,"role":n.role,"location":n.location,
                       "attitude":n.attitude,"alive":n.alive,"personality":n.personality,
                       "motivation":n.motivation,"secret":n.secret,
                       "relation_to_plot":n.relation_to_plot,"visibility":n.visibility.to_dict(),
                       "discovered":n.discovered} for n in world_state.npcs],
            "plot_flags": [{"key":f.key,"status":f.status,"description":f.description,"consequence":f.consequence,"visible":f.visible} for f in world_state.plot_flags],
            "locations": [{"name":l.name,"description":l.description,"status":l.status,"type":l.type,"culture":l.culture,"notable_figures":l.notable_figures,"dangers":l.dangers,"secrets":l.secrets,"secret_revealed":l.secret_revealed,"related_locations":l.related_locations,"related_npcs":l.related_npcs,"related_creatures":l.related_creatures,"discovered":l.discovered} for l in world_state.locations],
        }, ensure_ascii=False),
    }



@router.post("/api/generate/world/stream")
async def generate_world_stream(request: WorldGenRequest):
    """流式生成世界：通过 SSE 实时推送进度，最后返回完整结果。"""
    from backend.engine.world_builder import build_world

    player_input = f"""冒险基调: {request.tone}
角色: {request.character_name}, {request.race} {request.char_class}, Lv.{request.character_level}
描述: {request.description}"""

    if not (request.model_name or settings.LLM_MODEL_NAME):
        raise HTTPException(status_code=400, detail="请先选择或填写模型名称")
    try:
        api_key = ensure_valid_api_key(request.api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    async def event_stream():
        queue: asyncio.Queue = asyncio.Queue()

        def progress(label: str, percent: int, detail: str = ""):
            queue.put_nowait({"type": "progress", "label": label, "percent": percent, "detail": detail})

        def stream_token(token: str):
            queue.put_nowait({"type": "gen_token", "token": token})

        async def run():
            try:
                outline_text, score, history, world_state = await build_world(
                    player_input=player_input,
                    reference_script=request.description,
                    api_key=api_key,
                    model_name=request.model_name,
                    base_url=request.base_url,
                    game_system=request.game_system,
                    custom_rules=request.custom_rules or "",
                    custom_classes=request.custom_classes,
                    custom_skills=request.custom_skills,
                    extra_attributes=request.extra_attributes,
                    target_score=75,
                    max_revisions=1,
                    progress_callback=progress,
                    thinking_strength=request.thinking_strength,
                    username=request.username,
                    token_callback=stream_token,
                )
                queue.put_nowait({"type": "__complete__", "data": (outline_text, score, history, world_state)})
            except Exception as e:
                queue.put_nowait({"type": "__error__", "msg": str(e)})

        task = asyncio.create_task(run())
        while True:
            item = await queue.get()
            if item["type"] == "progress":
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                continue
            if item["type"] == "gen_token":
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                continue
            if item["type"] == "__error__":
                yield f"data: {json.dumps({'type':'error','msg':item['msg']}, ensure_ascii=False)}\n\n"
                break
            # complete
            try:
                outline_text, score, history, world_state = item["data"]
                npc_summary = [{"name": n.name, "role": n.role, "attitude": n.attitude} for n in world_state.npcs]
                flag_summary = [{"key": f.key, "status": f.status} for f in world_state.plot_flags]
                ws_json = json.dumps({
                    "world_outline": outline_text,
                    "npcs": [{"name": n.name, "race": n.race, "role": n.role, "location": n.location,
                              "attitude": n.attitude, "alive": n.alive, "personality": n.personality,
                              "motivation": n.motivation, "secret": n.secret,
                              "relation_to_plot": n.relation_to_plot, "visibility": n.visibility.to_dict(), "discovered": n.discovered}
                             for n in world_state.npcs],
                    "plot_flags": [{"key": f.key, "status": f.status, "description": f.description, "consequence": f.consequence, "visible": f.visible} for f in world_state.plot_flags],
                    "locations": [{"name": l.name, "description": l.description, "status": l.status, "type": l.type, "culture": l.culture, "notable_figures": l.notable_figures, "dangers": l.dangers, "secrets": l.secrets, "secret_revealed": l.secret_revealed, "related_locations": l.related_locations, "related_npcs": l.related_npcs, "related_creatures": l.related_creatures, "discovered": l.discovered} for l in world_state.locations],
                    "world_rules": world_state.world_rules,
                }, ensure_ascii=False)
                from backend.scenario_importer import generate_summary
                from backend.scenario_store import create_scenario
                summary_client = AsyncOpenAI(api_key=api_key, base_url=request.base_url or settings.LLM_BASE_URL)
                summary_model = request.model_name or settings.LLM_MODEL_NAME
                summary = await generate_summary(summary_client, summary_model, outline_text, request.description, token_callback=stream_token)
                saved = create_scenario(
                    world_outline=outline_text, world_state_json=ws_json,
                    reference_script=request.description, custom_rules=request.custom_rules or "",
                    custom_classes=request.custom_classes, custom_skills=request.custom_skills,
                    extra_attributes=request.extra_attributes, notes="",
                    title=outline_text.split("\n")[0].replace("#", "").strip()[:60],
                    description=request.description[:200], summary=summary,
                    system=request.game_system, tone=request.tone,
                    character_name=request.character_name, race=request.race,
                    char_class=request.char_class, level=request.character_level,
                    score=score, username=request.username,
                )
                try:
                    from backend.media_manager import sync_scenario_bestiary, sync_scenario_maps, sync_scenario_spells
                    sync_scenario_maps(request.username, saved.id, world_state.locations, request.game_system)
                    sync_scenario_bestiary(request.username, saved.id, world_state.creatures, request.game_system)
                    sync_scenario_spells(request.username, saved.id, world_state.spells, request.game_system)
                except Exception:
                    pass
                result = {
                    "type": "complete",
                    "scenario_id": saved.id,
                    "content": outline_text,
                    "summary": summary,
                    "system": request.game_system,
                    "score": score,
                    "scores_detail": {},
                    "revision_history": history,
                    "npcs": npc_summary,
                    "plot_flags": flag_summary,
                    "world_rules": world_state.world_rules,
                    "world_state_json": json.dumps({
                        "world_outline": world_state.world_outline,
                        "world_rules": world_state.world_rules,
                        "npcs": [{"name": n.name, "race": n.race, "role": n.role, "location": n.location,
                                  "attitude": n.attitude, "alive": n.alive, "personality": n.personality,
                                  "motivation": n.motivation, "secret": n.secret,
                                  "relation_to_plot": n.relation_to_plot, "discovered": n.discovered} for n in world_state.npcs],
                        "plot_flags": [{"key": f.key, "status": f.status, "description": f.description, "consequence": f.consequence, "visible": f.visible} for f in world_state.plot_flags],
                        "locations": [{"name": l.name, "description": l.description, "status": l.status, "type": l.type, "culture": l.culture, "notable_figures": l.notable_figures, "dangers": l.dangers, "secrets": l.secrets, "secret_revealed": l.secret_revealed, "related_locations": l.related_locations, "related_npcs": l.related_npcs, "related_creatures": l.related_creatures, "discovered": l.discovered} for l in world_state.locations],
                    }, ensure_ascii=False),
                }
                yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
                break
            except Exception as e:
                yield f"data: {json.dumps({'type':'error','msg':f'世界生成完成处理失败: {e}'}, ensure_ascii=False)}\n\n"
                break
        await task

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})



@router.post("/api/generate/character")
async def generate_character(request: GenerateAttributesRequest):
    """AI 生成角色属性与背景故事（实现见 backend.character_generation）。"""
    return await generate_character_payload(request)


