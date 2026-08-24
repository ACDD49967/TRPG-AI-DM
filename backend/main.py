"""FastAPI 应用入口——API路由、SSE长连接、生命周期管理。"""

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

import random, re

from backend.config import ensure_valid_api_key, settings
from backend.database import get_db, init_db
from backend.engine.dm_agent import process_player_action
from backend.engine.world_state import WorldState
from backend.engine.session import (
    GameSessionState,
    push_event,
    push_narrative_flush,
    session_manager,
    sse_event_generator,
)
from backend.models import Character, GameSession, User
from backend.schemas import (
    ActionAcceptedResponse,
    ActionRequest,
    GenerateAttributesRequest,
    GenerateBackstoryRequest,
    NewGameRequest,
    NewGameResponse,
    WorldGenRequest,
)


# ═══════════════════════════════════════════════════════════════
# 应用生命周期
# ═══════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的生命周期管理。"""
    # 启动时：创建数据库表
    await init_db()
    print(f"[AI-DM] Server started at http://{settings.HOST}:{settings.PORT}")
    print(f"[AI-DM] Database: {settings.DATABASE_URL}")
    print(f"[AI-DM] Model: {settings.MODEL_NAME}")
    yield
    # 关闭时：清理资源（如有需要）


# ═══════════════════════════════════════════════════════════════
# FastAPI 应用实例
# ═══════════════════════════════════════════════════════════════

app = FastAPI(
    title="TRPG AI 跑团主持",
    description="由大语言模型驱动的单人 TRPG 跑团主持",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 中间件 —— 允许前端开发服务器跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 静态媒体（地图/生物/角色图片）
import os as _os
_os.makedirs("media", exist_ok=True)
app.mount("/media", StaticFiles(directory="media"), name="media")


# ═══════════════════════════════════════════════════════════════
# API 路由
# ═══════════════════════════════════════════════════════════════

@app.post("/api/generate/world")
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
                   "relation_to_plot":n.relation_to_plot,"visibility":n.visibility.to_dict()}
                  for n in world_state.npcs],
        "plot_flags": [{"key":f.key,"status":f.status,"description":f.description}
                       for f in world_state.plot_flags],
        "locations": [{"name":l.name,"description":l.description,"secrets":l.secrets}
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
    except Exception:
        pass

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
                       "relation_to_plot":n.relation_to_plot} for n in world_state.npcs],
            "plot_flags": [{"key":f.key,"status":f.status,"description":f.description}
                           for f in world_state.plot_flags],
            "locations": [{"name":l.name,"description":l.description,"secrets":l.secrets}
                          for l in world_state.locations],
        }, ensure_ascii=False),
    }


@app.post("/api/generate/world/stream")
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
                              "relation_to_plot": n.relation_to_plot, "visibility": n.visibility.to_dict()}
                             for n in world_state.npcs],
                    "plot_flags": [{"key": f.key, "status": f.status, "description": f.description} for f in world_state.plot_flags],
                    "locations": [{"name": l.name, "description": l.description, "secrets": l.secrets} for l in world_state.locations],
                    "world_rules": world_state.world_rules,
                }, ensure_ascii=False)
                from backend.scenario_importer import generate_summary
                from backend.scenario_store import create_scenario
                summary_client = AsyncOpenAI(api_key=api_key, base_url=request.base_url or settings.LLM_BASE_URL)
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
                                  "relation_to_plot": n.relation_to_plot} for n in world_state.npcs],
                        "plot_flags": [{"key": f.key, "status": f.status, "description": f.description} for f in world_state.plot_flags],
                        "locations": [{"name": l.name, "description": l.description, "secrets": l.secrets} for l in world_state.locations],
                    }, ensure_ascii=False),
                }
                yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
                break
            except Exception as e:
                yield f"data: {json.dumps({'type':'error','msg':f'世界生成完成处理失败: {e}'}, ensure_ascii=False)}\n\n"
                break
        await task

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ═══════════════════════════════════════════════════════════════
# 剧本管理 API
# ═══════════════════════════════════════════════════════════════

@app.get("/api/scenarios")
async def list_scenarios(username: str = "default"):
    """列出当前用户可见的剧本（按用户名隔离）。"""
    from backend.scenario_store import list_scenarios as ls
    return {"scenarios": ls(username)}


@app.get("/api/classic-scenarios")
async def classic_scenarios():
    """列出公开/免费的经典剧本参考（仅名称与简介，不包含受版权保护的完整正文）。"""
    from backend.classic_scenarios import list_classic_scenarios
    return {"scenarios": list_classic_scenarios()}


@app.post("/api/scenarios/import")
async def import_scenario(
    file: UploadFile = File(...),
    splitter: str = Form("naive"),
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
    """上传剧本文件（pdf/txt/docx/doc/md）→ 按所选切分器切分 → 生成并保存新剧本。

    支持 splitter=naive（切分器）或 splitter=semantic（语义切分）。
    支持 system=dnd5e/dnd4e/coc/custom；缺省时自动识别。
    返回的剧本包含约400字总结、世界大纲、结构化世界状态和切分片段。
    """
    from backend.scenario_importer import (
        detect_game_system,
        extract_text,
        generate_scenario_from_text,
        split_text,
    )
    from backend.engine.game_systems import SYSTEM_TYPES

    if splitter not in ("naive", "semantic"):
        raise HTTPException(status_code=400, detail="splitter 仅支持 naive 或 semantic")
    if chunk_size < 200 or chunk_size > 4000:
        raise HTTPException(status_code=400, detail="chunk_size 需在 200-4000 之间")

    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件不能超过 20MB")

    try:
        text = extract_text(file.filename or "", data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not text.strip():
        raise HTTPException(status_code=400, detail="文件中没有可用的剧本文本")

    chunks = split_text(text, mode=splitter, chunk_size=chunk_size)
    if not chunks:
        raise HTTPException(status_code=400, detail="切分后没有生成任何片段")

    if not system or system == "auto":
        system = detect_game_system(text, title)
    if system not in SYSTEM_TYPES:
        raise HTTPException(status_code=400, detail=f"未知规则系统: {system}，可选: {', '.join(SYSTEM_TYPES)}")

    import json as _json
    try:
        custom_classes_list = _json.loads(custom_classes or "[]") or []
        custom_skills_list = _json.loads(custom_skills or "[]") or []
        extra_attributes_dict = _json.loads(extra_attributes or "{}") or {}
    except Exception:
        custom_classes_list, custom_skills_list, extra_attributes_dict = [], [], {}

    queue: asyncio.Queue = asyncio.Queue()

    def progress(label: str, percent: int, detail: str = ""):
        queue.put_nowait({"type": "progress", "label": label, "percent": percent, "detail": detail})

    async def run():
        try:
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
            )
            queue.put_nowait({"type": "__complete__", "data": result})
        except Exception as e:
            queue.put_nowait({"type": "__error__", "msg": f"剧本生成失败: {e}"})

    async def event_stream():
        task = asyncio.create_task(run())
        while True:
            item = await queue.get()
            if item["type"] == "progress":
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                continue
            if item["type"] == "__error__":
                yield f"data: {json.dumps({'type':'error','msg':item['msg']}, ensure_ascii=False)}\n\n"
                break
            result = item["data"]
            result["type"] = "complete"
            yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
            break
        await task

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str, username: str = "default"):
    """加载一个已保存的剧本（按用户名隔离）。"""
    from backend.scenario_store import Scenario
    s = Scenario.load(scenario_id, username)
    if s is None:
        raise HTTPException(status_code=404, detail="剧本不存在")
    return {
        "id": s.id,
        "meta": s.meta.to_dict(),
        "world_outline": s.world_outline,
        "world_state_json": s.world_state_json,
        "reference_script": s.reference_script,
        "source_chunks": s.source_chunks,
        "custom_rules": s.custom_rules,
        "custom_classes": s.custom_classes,
        "custom_skills": s.custom_skills,
        "extra_attributes": s.extra_attributes,
        "summary": s.meta.summary,
        "system": s.meta.system,
        "notes": s.notes,
    }


@app.post("/api/scenarios/{scenario_id}/play")
async def record_scenario_play(scenario_id: str, username: str = "default"):
    """记录剧本被游玩一次（按用户名隔离）。"""
    from backend.scenario_store import Scenario
    s = Scenario.load(scenario_id, username)
    if s is None:
        raise HTTPException(status_code=404, detail="剧本不存在")
    s.record_play()
    return {"total_sessions": s.meta.total_sessions}


@app.delete("/api/scenarios/{scenario_id}")
async def delete_scenario_endpoint(scenario_id: str, username: str = "default"):
    """删除一个剧本（按用户名隔离）。"""
    from backend.scenario_store import delete_scenario
    if not delete_scenario(scenario_id, username):
        raise HTTPException(status_code=404, detail="剧本不存在")
    return {"deleted": True}


@app.put("/api/scenarios/{scenario_id}")
async def update_scenario_endpoint(scenario_id: str, payload: dict, username: str = "default"):
    """编辑剧本：更新标题/描述/总结/备注/大纲/自定义内容（按用户名隔离）。"""
    from backend.scenario_store import Scenario
    s = Scenario.load(scenario_id, username)
    if s is None:
        raise HTTPException(status_code=404, detail="剧本不存在")
    if payload.get("title") is not None:
        s.meta.title = str(payload["title"])[:120]
    if payload.get("description") is not None:
        s.meta.description = str(payload["description"])[:500]
    if payload.get("summary") is not None:
        s.meta.summary = str(payload["summary"])
    if payload.get("notes") is not None:
        s.notes = str(payload["notes"])
    if payload.get("world_outline") is not None:
        s.world_outline = str(payload["world_outline"])
    if payload.get("custom_rules") is not None:
        s.custom_rules = str(payload["custom_rules"])
    if payload.get("custom_classes") is not None:
        s.custom_classes = list(payload["custom_classes"]) or []
    if payload.get("custom_skills") is not None:
        s.custom_skills = list(payload["custom_skills"]) or []
    if payload.get("extra_attributes") is not None:
        s.extra_attributes = dict(payload["extra_attributes"]) or {}
    s.save()
    return {"updated": True, "id": s.id}


# ── 角色卡管理 ──

@app.get("/api/characters")
async def list_character_cards_api(username: str = "default"):
    from backend.character_card_manager import list_character_cards
    return {"cards": list_character_cards(username)}


@app.post("/api/characters")
async def save_character_card_api(payload: dict):
    from backend.character_card_manager import save_character_card
    username = str(payload.get("username") or "default")
    card = save_character_card(username, payload.get("card") or {})
    return {"card": card}


@app.get("/api/characters/{card_id}")
async def get_character_card_api(card_id: str, username: str = "default"):
    from backend.character_card_manager import get_character_card
    card = get_character_card(username, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="角色卡不存在")
    return {"card": card}


@app.put("/api/characters/{card_id}")
async def update_character_card_api(card_id: str, payload: dict):
    from backend.character_card_manager import save_character_card
    username = str(payload.get("username") or "default")
    card = save_character_card(username, payload.get("card") or {}, card_id=card_id)
    return {"card": card}


@app.delete("/api/characters/{card_id}")
async def delete_character_card_api(card_id: str, username: str = "default"):
    from backend.character_card_manager import delete_character_card
    if not delete_character_card(username, card_id):
        raise HTTPException(status_code=404, detail="角色卡不存在")
    return {"deleted": True}


@app.delete("/api/saves/{save_id}")
async def delete_save_api(save_id: str, username: str = "default"):
    from backend.save_manager import delete_save
    if not delete_save(username, save_id):
        raise HTTPException(status_code=404, detail="存档不存在")
    return {"deleted": True}


@app.get("/api/knowledge")
async def list_knowledge(username: str = "default"):
    """列出当前用户可见的知识库文档（不含正文片段）。"""
    from backend.knowledge_base import get_knowledge_base
    return {"documents": get_knowledge_base().list_documents(username)}


@app.post("/api/knowledge")
async def add_knowledge(payload: dict):
    """添加知识库文档/备注（JSON，按用户名隔离）。"""
    from backend.knowledge_base import get_knowledge_base
    title = str(payload.get("title") or "未命名知识")
    content = str(payload.get("content") or "")
    system = str(payload.get("system") or "custom")
    source = str(payload.get("source") or "user")
    tags = payload.get("tags") or []
    username = str(payload.get("username") or "default")
    if not content.strip():
        raise HTTPException(status_code=400, detail="内容不能为空")
    doc = get_knowledge_base().add_document(
        title=title, content=content, source=source, system=system, tags=tags,
        username=username,
    )
    return {"doc": doc}


@app.post("/api/knowledge/upload")
async def upload_knowledge(
    file: UploadFile = File(...),
    title: str = Form(""),
    system: str = Form("custom"),
    source: str = Form("user"),
    tags: str = Form(""),
    username: str = Form("default"),
):
    """上传 PDF/DOCX/TXT/MD 到知识库（按用户名隔离）。"""
    from backend.knowledge_base import get_knowledge_base
    from backend.scenario_importer import extract_text

    data = await file.read()
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件不能超过 30MB")
    try:
        content = extract_text(file.filename or "", data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    doc = get_knowledge_base().add_document(
        title=title or file.filename or "上传资料",
        content=content,
        source=source,
        system=system,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        username=username,
    )
    return {"doc": doc}


@app.delete("/api/knowledge/{doc_id}")
async def delete_knowledge(doc_id: str, username: str = "default"):
    from backend.knowledge_base import get_knowledge_base
    if not get_knowledge_base().remove_document(doc_id, username):
        raise HTTPException(status_code=404, detail="知识文档不存在或无权删除")
    return {"deleted": True}


@app.post("/api/knowledge/retrieve")
async def retrieve_knowledge(payload: dict):
    """RAG 检索：按查询返回最相关的知识片段（按用户名隔离）。"""
    from backend.knowledge_base import get_knowledge_base
    query = str(payload.get("query") or "")
    system = payload.get("system")
    top_k = int(payload.get("top_k") or 5)
    username = str(payload.get("username") or "default")
    if not query.strip():
        raise HTTPException(status_code=400, detail="查询不能为空")
    results = get_knowledge_base().retrieve(query, system=system, top_k=top_k, username=username)
    return {"results": results}


@app.post("/api/knowledge/seed")
async def seed_knowledge():
    """重新填充内置规则备注（幂等）。"""
    from backend.knowledge_base import get_knowledge_base
    get_knowledge_base().seed_builtin_rules()
    return {"seeded": True}


@app.get("/api/extensions")
async def list_extensions_api(username: str = "default"):
    from backend.extension_manager import list_extensions
    return {"extensions": list_extensions(username)}


@app.post("/api/extensions")
async def add_extension_api(payload: dict):
    from backend.extension_manager import add_extension
    username = str(payload.get("username") or "default")
    ext = add_extension(
        username=username,
        name=str(payload.get("name") or "未命名扩展包"),
        description=str(payload.get("description") or ""),
        content=str(payload.get("content") or ""),
        system=str(payload.get("system") or "custom"),
        tags=payload.get("tags") or [],
        source=str(payload.get("source") or "user"),
    )
    return {"extension": ext}


@app.post("/api/extensions/generate")
async def generate_extension_api(payload: dict):
    """由 LLM 生成扩展包 JSON。"""
    from backend.extension_manager import add_extension
    username = str(payload.get("username") or "default")
    description = str(payload.get("description") or "")
    system = str(payload.get("system") or "custom")
    api_key = payload.get("api_key") or settings.LLM_API_KEY
    model = payload.get("model_name") or settings.LLM_MODEL_NAME
    base_url = payload.get("base_url") or settings.LLM_BASE_URL
    if not model:
        raise HTTPException(status_code=400, detail="请先选择模型")
    try:
        api_key = ensure_valid_api_key(api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not description.strip():
        raise HTTPException(status_code=400, detail="请描述你想生成的扩展包")

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    prompt = f"""请为一个 TRPG 游戏生成一个扩展包，必须返回合法 JSON，不要 Markdown 代码块，不要其他文本。

规则系统：{system}
扩展包需求：{description}

JSON 格式：
{{
  "name": "扩展包名称",
  "description": "一句话简介",
  "content": "扩展包具体内容：新增规则、职业/调查员能力、物品、NPC、事件、特殊机制等，Markdown 格式，300-800字",
  "tags": ["标签1", "标签2"]
}}"""
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一位TRPG扩展包设计者。只返回合法JSON。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=2000,
            temperature=0.8,
        )
        text = (resp.choices[0].message.content or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        import json as _json
        try:
            data = _json.loads(text)
        except Exception:
            from json_repair import repair_json
            text = repair_json(text, return_objects=False)
            data = _json.loads(text)
        ext = add_extension(
            username=username,
            name=str(data.get("name") or "LLM生成扩展包"),
            description=str(data.get("description") or ""),
            content=str(data.get("content") or ""),
            system=system,
            tags=data.get("tags") or ["LLM生成"],
            source="llm",
        )
        return {"extension": ext}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"扩展包生成失败: {e}") from e


@app.delete("/api/extensions/{ext_id}")
async def delete_extension_api(ext_id: str, username: str = "default"):
    from backend.extension_manager import delete_extension
    if not delete_extension(username, ext_id):
        raise HTTPException(status_code=404, detail="扩展包不存在")
    return {"deleted": True}


@app.get("/api/saves")
async def list_saves_api(username: str = "default"):
    from backend.save_manager import list_saves
    return {"saves": list_saves(username)}


@app.post("/api/game/{session_id}/save")
async def manual_save_api(session_id: str, payload: dict):
    """手动存档当前会话。"""
    from backend.save_manager import create_save
    state = session_manager.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    save = create_save(state, label=str(payload.get("label") or "手动存档"), auto=False)
    return {"save": save}


@app.post("/api/saves/load")
async def load_save_api(payload: dict):
    """载入存档：恢复为新会话并返回 SSE 地址。"""
    from backend.save_manager import load_save, restore_state_from_save
    username = str(payload.get("username") or "default")
    save_id = str(payload.get("save_id") or "")
    save_data = load_save(username, save_id)
    if save_data is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    state, session_id = restore_state_from_save(save_data)
    state.resumed = True
    # 旧存档兼容：按当前规则系统补全职业资源与行动点
    try:
        _ci = state.character_info or {}
        if _ci.get("game_system") == "dnd5e" and not _ci.get("class_resources"):
            from backend.engine.game_systems import get_dnd5_class_resources
            _ci["class_resources"] = get_dnd5_class_resources(
                _ci.get("char_class", ""), _ci.get("attributes", {}), _ci.get("level", 1))
        elif _ci.get("game_system") == "dnd4e":
            _ci.setdefault("action_points", 1)
            _ci.setdefault("class_resources", [])
        _ci.setdefault("known_spells", [])
    except Exception:
        pass
    # 用前端当前配置覆盖/补全存档中的模型配置，避免旧存档缺模型导致无法读档
    if payload.get("model_name"):
        state.model_name = str(payload["model_name"])
    if payload.get("api_key"):
        state.api_key = str(payload["api_key"])
    if payload.get("base_url"):
        state.base_url = str(payload["base_url"])
    if not (state.model_name or settings.LLM_MODEL_NAME):
        raise HTTPException(status_code=400, detail="存档未包含模型配置，请重新开始并选择模型")
    session_manager._sessions[session_id] = state
    # 载入存档后重新激活扩展包，确保 RAG 知识库中有对应内容
    if state.character_info.get("extension_ids"):
        from backend.extension_manager import activate_extensions_into_kb
        activate_extensions_into_kb(username, state.character_info["extension_ids"])
    # 从 SQLite 加载跨存档长期记忆
    try:
        from backend.long_term_memory import load_facts
        for fact in load_facts(username):
            state.memory.add_world_fact(fact)
    except Exception:
        pass
    return {
        "session_id": session_id,
        "character_id": state.character_id,
        "sse_url": f"/api/game/{session_id}/stream",
    }


@app.get("/api/maps")
async def list_maps_api(username: str = "default", scenario_id: str | None = None):
    from backend.media_manager import list_maps
    return {"maps": list_maps(username, scenario_id)}


@app.post("/api/maps")
async def add_map_api(payload: dict):
    from backend.media_manager import add_map
    username = str(payload.get("username") or "default")
    item = add_map(
        username=username,
        name=str(payload.get("name") or "未命名地图"),
        description=str(payload.get("description") or ""),
        image_path=str(payload.get("image_path") or ""),
        locations=payload.get("locations") or [],
        system=str(payload.get("system") or "custom"),
        scenario_id=str(payload.get("scenario_id") or ""),
    )
    return {"map": item}


@app.post("/api/maps/upload")
async def upload_map_api(
    file: UploadFile = File(...),
    username: str = Form("default"),
    name: str = Form("未命名地图"),
    description: str = Form(""),
    system: str = Form("custom"),
    locations: str = Form("[]"),
    scenario_id: str = Form(""),
):
    from backend.media_manager import add_map, save_image
    import json as _json
    data = await file.read()
    image_path = save_image(username, data, file.filename or "map.png")
    try:
        locs = _json.loads(locations) if locations.strip() else []
    except Exception:
        locs = []
    item = add_map(username, name, description, image_path, locs, system, scenario_id=scenario_id)
    return {"map": item}


@app.delete("/api/maps/{map_id}")
async def delete_map_api(map_id: str, username: str = "default"):
    from backend.media_manager import delete_map
    if not delete_map(username, map_id):
        raise HTTPException(status_code=404, detail="地图不存在")
    return {"deleted": True}


@app.get("/api/spells")
async def list_spells_api(username: str = "default", scenario_id: str | None = None):
    from backend.media_manager import list_spells
    return {"spells": list_spells(username, scenario_id)}


@app.post("/api/spells")
async def add_spell_api(payload: dict):
    from backend.media_manager import add_spell
    item = add_spell(
        username=str(payload.get("username") or "default"),
        name=str(payload.get("name") or "未命名法术"),
        system=str(payload.get("system") or "custom"),
        description=str(payload.get("description") or ""),
        level=str(payload.get("level") or "0"),
        school=str(payload.get("school") or ""),
        ritual=bool(payload.get("ritual", False)),
        casting_time=str(payload.get("casting_time") or ""),
        range_=str(payload.get("range") or ""),
        components=str(payload.get("components") or ""),
        duration=str(payload.get("duration") or ""),
        classes=payload.get("classes") or [],
        scenario_id=str(payload.get("scenario_id") or ""),
    )
    return {"spell": item}


@app.delete("/api/spells/{spell_id}")
async def delete_spell_api(spell_id: str, username: str = "default"):
    from backend.media_manager import delete_spell
    if not delete_spell(username, spell_id):
        raise HTTPException(status_code=404, detail="法术不存在")
    return {"deleted": True}


@app.get("/api/bestiary")
async def list_bestiary_api(username: str = "default", scenario_id: str | None = None):
    from backend.media_manager import list_bestiary
    return {"bestiary": list_bestiary(username, scenario_id)}


@app.post("/api/bestiary")
async def add_bestiary_api(payload: dict):
    from backend.media_manager import add_bestiary
    username = str(payload.get("username") or "default")
    item = add_bestiary(
        username=username,
        name=str(payload.get("name") or "未命名生物"),
        system=str(payload.get("system") or "custom"),
        description=str(payload.get("description") or ""),
        stats=payload.get("stats") or {},
        image_path=str(payload.get("image_path") or ""),
        tags=payload.get("tags") or [],
        scenario_id=str(payload.get("scenario_id") or ""),
    )
    return {"bestiary": item}


@app.post("/api/bestiary/upload")
async def upload_bestiary_api(
    file: UploadFile = File(...),
    username: str = Form("default"),
    name: str = Form("未命名生物"),
    system: str = Form("custom"),
    description: str = Form(""),
    stats: str = Form("{}"),
    tags: str = Form(""),
    scenario_id: str = Form(""),
):
    from backend.media_manager import add_bestiary, save_image
    import json as _json
    data = await file.read()
    image_path = save_image(username, data, file.filename or "creature.png")
    try:
        stats_data = _json.loads(stats) if stats.strip() else {}
    except Exception:
        stats_data = {}
    item = add_bestiary(username, name, system, description, stats_data, image_path,
                        [t.strip() for t in tags.split(",") if t.strip()],
                        scenario_id=scenario_id)
    return {"bestiary": item}


@app.delete("/api/bestiary/{beast_id}")
async def delete_bestiary_api(beast_id: str, username: str = "default"):
    from backend.media_manager import delete_bestiary
    if not delete_bestiary(username, beast_id):
        raise HTTPException(status_code=404, detail="生物不存在")
    return {"deleted": True}


@app.post("/api/media/character")
async def upload_character_image_pre(username: str = Form("default"), file: UploadFile = File(...)):
    """创建角色前上传角色图片，返回可用的图片路径。"""
    from backend.media_manager import save_image
    image_path = save_image(username, await file.read(), file.filename or "character.png")
    return {"image_path": image_path}


@app.post("/api/game/{session_id}/image")
async def upload_character_image(session_id: str, file: UploadFile = File(...)):
    """上传当前角色图片。"""
    from backend.media_manager import save_image
    state = session_manager.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    data = await file.read()
    image_path = save_image(state.username, data, file.filename or "character.png")
    state.character_info["character_image"] = image_path
    await push_event(state, "state_update", {"character_image": image_path})
    return {"image_path": image_path}


@app.post("/api/game/{session_id}/npc")
async def add_npc_api(session_id: str, payload: dict):
    """DM 手动为当前剧本新增一个 NPC/角色。"""
    state = session_manager.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    from backend.engine.world_state import NpcEntry, WorldState
    ws = getattr(state, "world_state", None) or WorldState(session_id=session_id)
    npc = NpcEntry(
        name=str(payload.get("name") or "未命名NPC"),
        race=str(payload.get("race") or ""),
        role=str(payload.get("role") or "未知身份"),
        location=str(payload.get("location") or ws.scene.current_location),
        attitude=str(payload.get("attitude") or "中立"),
        hp=int(payload.get("hp") or 10),
        max_hp=int(payload.get("hp") or 10),
        ac=int(payload.get("ac") or 10),
        level=int(payload.get("level") or 1),
        attributes=payload.get("attributes") or {},
        skills=payload.get("skills") or [],
        traits=payload.get("traits") or [],
    )
    ws.add_npc(npc)
    state.world_state = ws
    await push_event(state, "journal_update", ws.to_player_journal())
    return {"npc": {"name": npc.name, "role": npc.role}}


@app.post("/api/game/{session_id}/npc/image")
async def upload_npc_image(session_id: str, npc_name: str = Form(...), file: UploadFile = File(...)):
    """为当前剧本中的 NPC 上传自定义图片。"""
    state = session_manager.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    from backend.media_manager import save_image
    from backend.engine.world_state import WorldState
    ws = getattr(state, "world_state", None) or WorldState(session_id=session_id)
    npc = ws.get_npc(npc_name)
    if npc is None:
        raise HTTPException(status_code=404, detail="NPC 不存在")
    image_path = save_image(state.username, await file.read(), file.filename or "npc.png")
    npc.image_path = image_path
    ws.save()
    state.world_state = ws
    await push_event(state, "journal_update", ws.to_player_journal())
    return {"image_path": image_path}


@app.post("/api/models")
async def fetch_models(payload: dict):
    """从 OpenAI 兼容接口获取模型列表，用于前端下拉菜单。"""
    import httpx
    base_url = str(payload.get("base_url") or settings.LLM_BASE_URL).rstrip("/")
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
        async with httpx.AsyncClient(timeout=20, verify=False) as hc:
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


@app.get("/api/health")
async def health_check():
    """健康检查端点。"""
    return {
        "status": "ok",
        "active_sessions": len(session_manager._sessions),
        "model": settings.MODEL_NAME,
    }


@app.post("/api/generate/character")
async def generate_character(request: GenerateAttributesRequest):
    """AI生成角色属性与背景故事。

    三种模式：
    1. 提供背景故事、无属性 → AI推断属性+润色背景
    2. 提供属性、无背景故事 → AI根据种族/职业/属性生成生动背景
    3. 都不提供 → AI自动生成属性+背景

    返回值含 attributes 和 backstory。
    """
    api_key = request.api_key or settings.LLM_API_KEY
    base_url = request.base_url or settings.LLM_BASE_URL
    model = request.model_name or settings.LLM_MODEL_NAME
    if not model:
        raise HTTPException(status_code=400, detail="请先选择或填写模型名称")
    try:
        api_key = ensure_valid_api_key(request.api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    has_backstory = bool(request.backstory.strip())
    has_attrs = bool(request.attributes and len(request.attributes) >= 6)
    system = request.game_system or "dnd5e"
    scenario_summary = request.scenario_summary or ""
    custom_rules = request.custom_rules or ""

    from backend.engine.game_systems import (
        get_style_directive,
        roll_coc_characteristics,
        roll_coc_luck,
    )
    style_block = get_style_directive(system)
    scenario_block = f"\n\n## 已选剧本总结（必须自然融入角色背景）\n{scenario_summary[:1200]}" if scenario_summary else ""
    custom_block = f"\n\n## 自定义规则（背景须符合）\n{custom_rules[:1500]}" if custom_rules and system == "custom" else ""

    # COC 的数值必须由程序随机生成，不允许 LLM 编造属性
    if system == "coc" and not has_attrs:
        request.attributes = roll_coc_characteristics()
        has_attrs = True

    gender = request.gender or "未指定"
    # 归一化性别值（支持中英文）
    gender_normalized = gender
    if gender.lower() in ("男", "m", "male", "man"):
        gender_normalized = "男"
    elif gender.lower() in ("女", "f", "female", "woman"):
        gender_normalized = "女"
    gender_hint = ""
    gender_pronoun = "ta"
    if gender_normalized == "男":
        gender_hint = "性别: 男\n"
        gender_pronoun = "他"
    elif gender_normalized == "女":
        gender_hint = "性别: 女\n"
        gender_pronoun = "她"

    if has_backstory and not has_attrs:
        # 模式1：有背景故事 → 推断属性（仅 D&D 系）
        user_prompt = f"""请根据以下角色背景故事推断{ 'D&D 六维' if system != 'coc' else 'COC 八维' }属性值。

角色名: {request.character_name}
{gender_hint}种族: {request.race}
职业: {request.char_class}
背景故事: {request.backstory}
{scenario_block}

根据故事中描述的角色特点分配属性。D&D 使用标准数组[15,14,13,12,10,8]范围3-18；COC 使用1-99百分比。
{style_block}

润色后的背景必须保留原故事核心，分段（2-3段，段间空行），结尾留一个未解决的钩子。

只返回JSON：
{{"str": 数字, "dex": 数字, "con": 数字, "int": 数字, "wis": 数字, "cha": 数字, "backstory": "润色后的背景(150-250字)"}}"""
    elif system == "coc" and has_backstory and has_attrs:
        # COC 模式：已有背景故事，但属性必须由程序随机生成（不允许 LLM 编造）
        attrs = request.attributes or {}
        attr_names = [("str","力量"),("con","体质"),("dex","敏捷"),("int","智力"),("pow","意志"),("cha","魅力"),("siz","体型"),("edu","教育")]
        attr_line = " | ".join(f"{label}:{attrs.get(key, 50)}" for key, label in attr_names)
        user_prompt = f"""你是克苏鲁式调查员背景作者。

角色名: {request.character_name}
{gender_hint}职业/身份: {request.char_class}
调查员属性: {attr_line}
已有背景故事（请保留其核心设定，润色扩写为完整人物小传）: {request.backstory}
{scenario_block}

写一段200-350字的人物小传。要求:
1. 保留原背景故事中的关键经历与秘密，并补足具体伤疤、坏习惯、不愿提及的往事
2. 从调查员日常或某个具体时刻切入，不要模板开头
3. 必须与剧本总结中的世界观自然衔接
4. 角色性别是{gender_normalized}，使用"{gender_pronoun}"作为人称代词
5. 分段，2-3个自然段，段间空行；第一段写具体场景，第二段写关键往事，结尾留一个未解决的钩子
6. 文风要求：{style_block}

只返回JSON: {{"backstory": "..."}}"""
    elif has_attrs and not has_backstory:
        # 模式2：有属性 → 根据属性+剧本总结生成沉浸式背景
        attrs = request.attributes or {}
        if system == "coc":
            attr_names = [("str","力量"),("con","体质"),("dex","敏捷"),("int","智力"),("pow","意志"),("cha","魅力"),("siz","体型"),("edu","教育")]
            attr_line = " | ".join(f"{label}:{attrs.get(key, 50)}" for key, label in attr_names)
            role_hint = "调查员"
        else:
            str_val = attrs.get('str', 12)
            dex_val = attrs.get('dex', 12)
            int_val = attrs.get('int', 12)
            cha_val = attrs.get('cha', 12)
            wis_val = attrs.get('wis', 12)
            con_val = attrs.get('con', 12)
            attr_line = f"力{str_val} 敏{dex_val} 体{con_val} 智{int_val} 感{wis_val} 魅{cha_val}"
            role_hint = "冒险者"

        user_prompt = f"""你是沉浸式角色背景作者。这个角色不是填表格——ta是一个活过的人，身上有伤疤、有执念、有不为人知的秘密。

角色名: {request.character_name}
{gender_hint}种族: {request.race}
职业/身份: {request.char_class}
{role_hint}属性: {attr_line}
{scenario_block}
{custom_block}

写一段200-350字的人物小传。必须遵循:
1. 不要写"ta从小就"、"命运的齿轮"、"踏上冒险之路"等模板开头
2. 从一个具体时刻切入——ta正在做什么？手上沾着什么？闻到什么味道？
3. 属性值只是骨架。最重要的数字是ta在哪个时刻做了什么选择——那个选择的后果至今未消
4. 给出一个具体伤疤、一个坏习惯、一个ta对别人撒过的谎（或者别人对ta撒的谎）
5. **必须与已选剧本总结的世界观自然衔接**，让角色看起来属于这个世界
6. 角色的性别是{gender_normalized}，使用"{gender_pronoun}"作为人称代词。性别必须体现在故事中
7. **格式要求**：必须分段。2-3个自然段，段与段之间用空行分隔。不要写成一大坨连在一起的文字
8. **段落结构**：第一段写一个正在进行的具体场景；第二段写导致现状的关键往事/选择；第三段（如有）写一个未解决的钩子或执念
9. **导语钩子**：结尾必须留一个让玩家想知道“接下来会怎样”的悬念或邀请，不要写成总结性结尾
10. 文风要求：{style_block}

只返回JSON: {{"backstory": "..."}}"""
    else:
        # 模式3：自动生成属性+背景（COC 属性已由程序随机生成）
        attrs = request.attributes or {}
        if system == "coc":
            attr_names = [("str","力量"),("con","体质"),("dex","敏捷"),("int","智力"),("pow","意志"),("cha","魅力"),("siz","体型"),("edu","教育")]
            attr_line = " | ".join(f"{label}:{attrs.get(key, 50)}" for key, label in attr_names)
            role_hint = "调查员"
            user_prompt = f"""你是克苏鲁式调查员背景作者。

角色名: {request.character_name}
{gender_hint}职业/身份: {request.char_class}
调查员属性: {attr_line}
{scenario_block}

写一段200-350字的人物小传。要求:
1. 从调查员日常或某个具体时刻切入，不要模板开头
2. 给出一个具体伤疤、一个坏习惯、一个不愿提及的往事
3. 必须与剧本总结中的世界观自然衔接
4. 角色性别是{gender_normalized}，使用"{gender_pronoun}"作为人称代词
5. 分段，2-3个自然段，段间空行；第一段写具体场景，第二段写关键往事，结尾留一个未解决的钩子
6. 文风要求：{style_block}

只返回JSON: {{"backstory": "..."}}"""
        else:
            str_val = attrs.get('str', 12)
            dex_val = attrs.get('dex', 12)
            int_val = attrs.get('int', 12)
            cha_val = attrs.get('cha', 12)
            wis_val = attrs.get('wis', 12)
            con_val = attrs.get('con', 12)
            attr_line = f"力{str_val} 敏{dex_val} 体{con_val} 智{int_val} 感{wis_val} 魅{cha_val}"
            user_prompt = f"""你是一位小说家，正在为你的新主角写人物小传。这个角色不是在填表格——ta是一个活过的人，身上有伤疤、有执念、有不为人知的秘密。

角色名: {request.character_name}
{gender_hint}种族: {request.race}
职业: {request.char_class}
六维: {attr_line}
{scenario_block}
{custom_block}

第一步：根据种族特点和职业需求，分配六维属性（3-18范围）。
第二步：基于这组属性，写一段200-350字的人物小传。要求:
1. 不要写"ta从小就"、"命运的齿轮"、"踏上冒险之路"等模板开头
2. 从一个具体时刻切入——ta正在做什么？手上沾着什么？闻到什么味道？
3. 给出一个具体伤疤、一个坏习惯、一个ta对别人撒过的谎
4. 避免奇幻人物传记高频元素。写一个像《巫师》杰洛特或者《博德之门3》影心的角色——有缺陷，有灰色地带
5. 属性值只是骨架。最重要的数字是ta在哪个时刻做了什么选择
6. 角色的性别是{gender_normalized}，使用"{gender_pronoun}"作为人称代词。性别必须体现在故事中
7. **格式要求**：必须分段。2-3个自然段，段与段之间用空行分隔
8. **段落结构**：第一段写一个正在进行的具体场景；第二段写导致现状的关键往事/选择；结尾留一个未解决的钩子或执念
9. **导语钩子**：结尾必须留一个让玩家想知道“接下来会怎样”的悬念或邀请，不要写成总结性结尾
10. 文风要求：{style_block}

只返回JSON: {{"str":数字,"dex":数字,"con":数字,"int":数字,"wis":数字,"cha":数字,"backstory":"..."}}"""

    try:
        import asyncio as _asyncio
        last_err = None
        text = ""
        for attempt in range(1, 3):
            base_max_tokens = 2000 if request.thinking_strength == "low" else (3000 if request.thinking_strength == "medium" else 5000)
            current_max_tokens = base_max_tokens if attempt == 1 else base_max_tokens * 2
            try:
                resp = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": (
                            f"你是一位沉浸式角色背景设计师。只返回合法JSON，不要Markdown代码块，不要其他文本。"
                            f"角色性别是{gender_normalized}，使用'{gender_pronoun}'作为人称代词。"
                            f"背景故事要有具体伤疤、坏习惯和灰色地带，避免模板化叙事。\n\n{style_block}"
                        )},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=current_max_tokens,
                    temperature=0.9,
                )
                text = (resp.choices[0].message.content or "").strip()
                if text:
                    break
                reasoning = getattr(resp.choices[0].message, "reasoning_content", None)
                print(f"[CharacterGen] 第{attempt}次空响应 (reasoning_len={len(reasoning or '')}, max_tokens={current_max_tokens})")
                raise RuntimeError("空响应")
            except Exception as e:
                last_err = e
                print(f"[CharacterGen] 第{attempt}次调用失败: {e}")
                await _asyncio.sleep(1)
        else:
            raise last_err or RuntimeError("背景生成失败")

        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        try:
            result = json.loads(text)
        except Exception:
            from json_repair import repair_json
            text = repair_json(text, return_objects=False)
            result = json.loads(text)

        # 验证属性
        required = ["str", "dex", "con", "int", "wis", "cha"]
        attrs: dict[str, int] = {}
        if has_attrs:
            attrs = dict(request.attributes)
        else:
            for key in required:
                attrs[key] = max(3, min(18, int(result.get(key, 12))))

        backstory = result.get("backstory", "")
        if not backstory:
            backstory = f"{request.character_name}，一位{request.race}{request.char_class}，踏上了冒险之路。"

        return {"attributes": attrs, "backstory": backstory}

    except Exception as e:
        print(f"[CharacterGen] 背景生成最终失败: {e}")
        default_attrs = {
            "战士": {"str": 16, "dex": 13, "con": 15, "int": 10, "wis": 12, "cha": 8},
            "法师": {"str": 8, "dex": 13, "con": 12, "int": 16, "wis": 14, "cha": 10},
            "游荡者": {"str": 10, "dex": 16, "con": 12, "int": 13, "wis": 10, "cha": 14},
            "牧师": {"str": 13, "dex": 10, "con": 14, "int": 10, "wis": 16, "cha": 12},
            "游侠": {"str": 12, "dex": 16, "con": 13, "int": 10, "wis": 14, "cha": 8},
            "吟游诗人": {"str": 8, "dex": 14, "con": 10, "int": 12, "wis": 10, "cha": 16},
        }.get(request.char_class, {"str": 12, "dex": 12, "con": 12, "int": 12, "wis": 12, "cha": 12})
        return {
            "attributes": request.attributes or default_attrs,
            "backstory": f"{request.character_name}，一位{request.race}{request.char_class}，命运的齿轮开始转动…",
            "fallback": True,
        }


# ── 角色名自动生成（基于种族+性别，D&D 风格，仅在 D&D 系使用） ──
_FIRST_NAMES = {
    "人类": {"男": ["艾伦","雷奥","加雷特","达里安","马库斯","塞德里克"],
             "女": ["艾琳娜","莉亚娜","瑟琳娜","伊莎贝尔","玛格丽特","罗莎琳"],
             "未指定": ["莫甘","瑞文","艾什","凯","奎因","斯凯"]},
    "高等精灵": {"男": ["艾拉希尔","萨里翁","费伦迪斯","洛瑟安"],
                "女": ["艾尔雯","伊瑟拉","莉安德拉","菲奥娜"],
                "未指定": ["艾拉瑞","罗兰","塞林","维里斯"]},
    "木精灵": {"男": ["瑟兰迪尔","莱戈拉斯","芬罗德","加拉德"],
               "女": ["艾尔文","妮缪","洛丝","银叶"],
               "未指定": ["林歌","风语","绿叶","河影"]},
    "山地矮人": {"男": ["索林","巴林","杜瓦林","格罗因","铁拳"],
                "女": ["迪萨","布琳希尔德","赫尔加","格瑞塔"],
                "未指定": ["铁炉","岩心","钢指","山盾"]},
    "半身人": {"男": ["米洛","芬恩","罗洛","托比"],
              "女": ["贝尔","黛西","罗西","皮帕"],
              "未指定": ["轻足","麦酒","烟斗","幸运叶"]},
    "龙裔": {"男": ["阿卡拉斯","托瑞恩","克瑞格","巴哈姆"],
             "女": ["艾莎拉","克丽丝","泽菲拉","雅拉"],
             "未指定": ["焰舌","鳞盾","雷息","霜爪"]},
    "半精灵": {"男": ["艾丹","瑟恩","迦兰","艾瑞克"],
              "女": ["米拉","瑟琳","艾琳诺","薇薇安"],
              "未指定": ["晨歌","旅者","海风","双月"]},
    "半兽人": {"男": ["格鲁姆","塔戈","乌尔祖克","莫格","断骨"],
             "女": ["卡莎","祖拉","娜迦","血牙"],
             "未指定": ["铁颚","碎颅","利爪","灰皮"]},
    "提夫林": {"男": ["莱维","阿兹拉尔","马拉克","阿什莫德"],
              "女": ["莉莉丝","瑟拉菲娜","尼尔","卡丽迪"],
              "未指定": ["灰烬","暗语","苦痛","硫磺"]},
    "侏儒": {"男": ["芬克","吉姆","托里克","克拉格"],
             "女": ["碧普","露娜","丁卡","塞尔达"],
             "未指定": ["齿轮","弹簧","灯芯","镜片"]},
}
_LAST_NAMES = {
    "人类": ["风行者","铁冠","暗河","石拳","红山","渡鸦","白塔","金谷"],
    "高等精灵": ["银叶","星语","月刃","晨曦","暮光","秘纹"],
    "木精灵": ["林行者","绿叶","河影","橡木","轻风","野径"],
    "山地矮人": ["铁炉","岩盾","铜锤","石拳","金须","熔岩","钢斧"],
    "半身人": ["轻足","麦酒","烟斗","蜜饼","桥下","老丘","花园"],
    "龙裔": ["焰舌","鳞盾","雷息","霜爪","钢翼","风暴"],
    "半精灵": ["旅者","双月","海风","远望","林歌","孤影"],
    "半兽人": ["碎骨","铁颚","血牙","利爪","断脊","战吼","刀疤"],
    "提夫林": ["苦痛","灰烬","暗语","硫磺","深渊","血誓"],
    "侏儒": ["发条","齿轮","灯芯","弹簧","镜片","扳手","六分仪"],
}

def _generate_character_name(race: str, gender: str) -> str:
    firsts = _FIRST_NAMES.get(race, _FIRST_NAMES["人类"]).get(gender, _FIRST_NAMES["人类"]["未指定"])
    lasts = _LAST_NAMES.get(race, _LAST_NAMES["人类"])
    first = random.choice(firsts)
    last = random.choice(lasts)
    return f"{first}·{last}"


@app.post("/api/game/new", response_model=NewGameResponse)
async def create_new_game(request: NewGameRequest):
    """创建新游戏——生成角色和会话，返回 SSE 连接地址。

    流程:
    1. 创建用户（如不存在则新建）
    2. 创建角色（若角色名为空，根据种族+性别自动生成D&D风格姓名）
    3. 创建游戏会话
    4. 在内存中注册活跃会话
    5. 返回 session_id + SSE URL
    """
    from backend.database import async_session as db_factory
    from sqlalchemy import select

    if not (request.model_name or settings.LLM_MODEL_NAME):
        raise HTTPException(status_code=400, detail="请先选择或填写模型名称")

    async with db_factory() as db:
        # 1. 获取或创建用户（避免重复用户名的唯一约束冲突）
        result = await db.execute(select(User).where(User.username == request.username))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(username=request.username)
            db.add(user)
            await db.flush()

        # 2. 创建角色（使用传入的属性或默认值）
        default_attrs = {"str": 12, "dex": 12, "con": 12, "int": 12, "wis": 12, "cha": 12}
        attrs = dict(request.attributes) if request.attributes else default_attrs
        # 数值钳制：D&D 系 3-18，COC 系 1-99，自定义仅保证整数
        if request.game_system == "coc":
            coc_keys = {"str", "con", "dex", "int", "pow", "cha", "siz", "edu"}
            attrs = {k: (max(1, min(99, int(v))) if k in coc_keys else int(v)) for k, v in attrs.items()}
        elif request.game_system in ("dnd5e", "dnd4e"):
            dnd_keys = {"str", "dex", "con", "int", "wis", "cha"}
            attrs = {k: (max(3, min(18, int(v))) if k in dnd_keys else int(v)) for k, v in attrs.items()}
        else:
            attrs = {k: int(v) for k, v in attrs.items()}

        # 如果角色名为空或为默认值"冒险者"，根据种族+性别自动生成
        char_name = request.character_name
        if not char_name or char_name.strip() in ("", "冒险者"):
            char_name = _generate_character_name(request.race, request.gender)

        character = Character(
            user_id=user.id,
            name=char_name,
            gender=request.gender,
            race=request.race,
            char_class=request.char_class,
            level=1,
            hp=30, max_hp=30,
            mp=10, max_mp=10,
            attributes=attrs,
        )
        db.add(character)
        await db.flush()

        # 3. 创建游戏会话
        session = GameSession(
            user_id=user.id,
            character_id=character.id,
            status="active",
        )
        db.add(session)
        await db.flush()

        # 4. 在内存中注册活跃会话
        # 计算AC
        attrs_for_ac = character.attributes or {}
        dex_ac = (attrs_for_ac.get("dex", 10) - 10) // 2
        _cc = character.char_class
        if _cc in ('战士', '圣武士'): _ac = 16
        elif _cc == '游侠': _ac = 14 + max(-2, min(2, dex_ac))
        elif _cc == '野蛮人': _ac = 10 + dex_ac + (attrs_for_ac.get("con", 10) - 10) // 2
        elif _cc == '武僧': _ac = 10 + dex_ac + (attrs_for_ac.get("wis", 10) - 10) // 2
        else: _ac = 11 + dex_ac
        if '山地矮人' in character.race: _ac += 1
        _ac = max(8, min(22, _ac))

        character_info = {
            "username": request.username or "default",
            "character_image": request.character_image or "",
            "gender": character.gender,
            "race": character.race,
            "char_class": character.char_class,
            "level": character.level,
            "hp": character.hp,
            "max_hp": character.max_hp,
            "mp": character.mp,
            "max_mp": character.max_mp,
            "xp": character.xp,
            "gold": character.gold,
            "ac": _ac,
            "attributes": character.attributes,
            "inventory": character.inventory,
            "race_traits": request.race_traits or [],
            "class_proficiencies": request.class_proficiencies or [],
            "skill_proficiencies": request.skill_proficiencies or [],
            "skills": request.skills or {},
            "feats": request.feats or [],
            "backstory": request.backstory or "",
            "world_context": request.world_context or "",
            "world_outline": request.world_outline or "",
            "world_state_json": request.world_state_json or "",
            "reference_script": request.reference_script or "",
            "scenario_id": request.scenario_id or "",
            "scenario_summary": "",
            "game_system": request.game_system,
            "custom_rules": request.custom_rules or "",
            "new_world": request.new_world,
            "play_mode": request.play_mode,
            "extension_ids": request.extension_ids,
            "custom_classes": request.custom_classes,
            "custom_skills": request.custom_skills,
            "extra_attributes": request.extra_attributes,
            "known_spells": request.known_spells or [],
        }

        # 根据规则系统预填衍生数值
        if request.game_system == "dnd5e":
            from backend.engine.game_systems import (
                get_dnd5_class_resources,
                get_dnd5_derived,
                get_dnd5_proficiency_bonus,
                get_dnd5_saves,
                get_dnd5_spell_slots,
                get_passive_perception,
            )
            d5 = get_dnd5_derived(character_info.get("char_class", "战士"), character_info.get("attributes", {}), character_info.get("level", 1))
            character_info["hp"] = d5["hp"]
            character_info["max_hp"] = d5["max_hp"]
            character_info["hit_die"] = d5["hit_die"]
            character_info["proficiency_bonus"] = get_dnd5_proficiency_bonus(character_info.get("level", 1))
            character_info["spell_slots"] = get_dnd5_spell_slots(character_info.get("char_class", ""), character_info.get("level", 1))
            character_info["saves"] = get_dnd5_saves(
                character_info.get("char_class", ""), character_info.get("attributes", {}),
                character_info["proficiency_bonus"],
            )
            character_info["passive_perception"] = get_passive_perception(
                character_info.get("attributes", {}), character_info["proficiency_bonus"],
                character_info.get("skill_proficiencies", []),
            )
            character_info["class_resources"] = get_dnd5_class_resources(
                character_info.get("char_class", ""), character_info.get("attributes", {}),
                character_info.get("level", 1),
            )
        elif request.game_system == "coc":
            from backend.engine.game_systems import get_coc_derived
            attrs_coc = character_info.get("attributes", {})
            coc = get_coc_derived(attrs_coc, request.luck or 50)
            character_info["hp"] = coc["hp"]
            character_info["max_hp"] = coc["hp"]
            character_info["mp"] = coc["mp"]
            character_info["max_mp"] = coc["mp"]
            character_info["san"] = coc["san"]
            character_info["max_san"] = coc["san"]
            character_info["luck"] = coc["luck"]
            character_info["damage_bonus"] = coc["damage_bonus"]
            character_info["build"] = coc["build"]
        elif request.game_system == "dnd4e":
            from backend.engine.game_systems import get_dnd4_defenses, get_dnd4_derived
            d4 = get_dnd4_derived(character_info.get("char_class", "战士"), character_info.get("attributes", {}))
            defenses = get_dnd4_defenses(character_info.get("char_class", "战士"), character_info.get("attributes", {}), character_info.get("level", 1))
            character_info["hp"] = d4["hp"]
            character_info["max_hp"] = d4["max_hp"]
            character_info["healing_surges"] = d4["healing_surges"]
            character_info["max_healing_surges"] = d4["max_healing_surges"]
            character_info["surge_value"] = d4["surge_value"]
            character_info["ac"] = defenses["ac"]
            character_info["fortitude"] = defenses["fortitude"]
            character_info["reflex"] = defenses["reflex"]
            character_info["will"] = defenses["will"]
            # 4e 行动点：每次长休重置为 1，里程碑奖励 +1（前端角色卡单独渲染）
            character_info["action_points"] = 1
            character_info["class_resources"] = []

        # 职业资源（dnd4e 已有行动点；coc/自定义无固定职业资源）
        character_info.setdefault("class_resources", [])

        # 初始白板装备：仅当玩家背包为空时按职业发放，不覆盖自定义开局
        if not (character.inventory or {}).get("items"):
            from backend.engine.game_systems import get_starter_equipment
            starter_items = get_starter_equipment(request.game_system, character.char_class)
            character_info["inventory"] = {"items": starter_items}
            character.inventory = character_info["inventory"]

        # 如果指定了已保存剧本ID且不是全新世界——加载剧本
        if request.scenario_id and not request.new_world:
            from backend.scenario_store import Scenario
            saved = Scenario.load(request.scenario_id, request.username)
            if saved:
                character_info["world_outline"] = saved.world_outline or character_info["world_outline"]
                character_info["world_state_json"] = saved.world_state_json or character_info["world_state_json"]
                character_info["scenario_id"] = request.scenario_id
                character_info["scenario_summary"] = saved.meta.summary or character_info.get("scenario_summary", "")
                # 角色规则系统不随剧本绑定；仅当玩家选择自定义且未填写自定义规则时，借用剧本自带规则
                if request.game_system == "custom" and not character_info.get("custom_rules"):
                    character_info["custom_rules"] = saved.custom_rules or ""
                if not character_info.get("custom_classes"):
                    character_info["custom_classes"] = saved.custom_classes
                if not character_info.get("custom_skills"):
                    character_info["custom_skills"] = saved.custom_skills
                if not character_info.get("extra_attributes"):
                    character_info["extra_attributes"] = saved.extra_attributes
                saved.record_play()

        # 如果有剧本URL，尝试抓取
        if request.scenario_url:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10) as hc:
                    r = await hc.get(request.scenario_url)
                    if r.status_code == 200:
                        character_info["world_context"] = r.text[:8000]
            except Exception:
                pass
        s = session_manager.create_session(
            session_id=session.id,
            character_id=character.id,
            character_name=char_name,
            character_info=character_info,
            api_key=request.api_key,
            model_name=request.model_name,
            username=request.username or "default",
        )
        if request.base_url:
            s.base_url = request.base_url
        s.thinking_strength = request.thinking_strength

        # 长短记忆：精简模式保留 5 轮，深度模式保留 10 轮，超出部分触发摘要压缩
        s.memory.max_active_turns = 5 if request.play_mode == "lite" else 10
        s.memory.summary_trigger = s.memory.max_active_turns + 1
        try:
            from backend.long_term_memory import load_facts
            for fact in load_facts(s.username):
                s.memory.add_world_fact(fact)
        except Exception:
            pass

        # 启用扩展包：写入知识库，供 RAG 检索
        if request.extension_ids:
            from backend.extension_manager import activate_extensions_into_kb
            activate_extensions_into_kb(request.username or "default", request.extension_ids)
            character_info["extensions"] = [
                {"id": eid, "name": eid} for eid in request.extension_ids
            ]
            s.character_info["extensions"] = character_info["extensions"]

        # 初始化持久化世界状态（P0-1修复：无条件创建，不再依赖world_state_json）
        import json as _json
        if request.world_state_json:
            try:
                ws_data = _json.loads(request.world_state_json)
                ws = WorldState(session_id=session.id, world_outline=ws_data.get("world_outline", ""),
                                 world_rules=ws_data.get("world_rules", ""))
                from backend.engine.world_state import NpcEntry as NE, PlotFlag as PF, LocationEntry as LE
                for n in ws_data.get("npcs", []):
                    ws.npcs.append(NE(**{k: v for k, v in n.items()
                                         if k in ["name","race","role","location","attitude",
                                                  "alive","personality","motivation","secret",
                                                  "relation_to_plot","notes",
                                                  "level","ac","hp","max_hp","attributes","skills","traits","image_path"]}))
                for p in ws_data.get("plot_flags", []):
                    ws.plot_flags.append(PF(**{k: v for k, v in p.items()
                                               if k in ["key","status","description","consequence"]}))
                for l in ws_data.get("locations", []):
                    ws.locations.append(LE(**{k: v for k, v in l.items()
                                              if k in ["name","description","status","secrets"]}))
                ws.save()
            except Exception:
                ws = WorldState(session_id=session.id)
        else:
            # 即使没有预生成剧本，也创建空的WorldState，确保update_scene能正常工作
            ws = WorldState(session_id=session.id)
            # 预设初始场景——从世界大纲/剧本中推断起始位置，或使用通用描述
            init_loc = "冒险的起点"
            init_weather = ""
            if character_info.get("world_outline"):
                # 尝试从世界大纲中提取第一个地点
                outline = character_info["world_outline"]
                m = re.search(r'(?:地点|场景|位置|起始)[：:]\s*(.+?)(?:\n|$)', outline)
                if m:
                    init_loc = m.group(1)[:30]
                else:
                    init_loc = "世界的入口"
            ws.update_scene(current_location=init_loc, current_time="第1天 · 冒险开始", weather=init_weather)
            ws.save()
        s.world_state = ws

        await db.commit()

    return NewGameResponse(
        session_id=session.id,
        character_id=character.id,
        sse_url=f"/api/game/{session.id}/stream",
    )


@app.post("/api/game/{session_id}/action", response_model=ActionAcceptedResponse)
async def submit_action(session_id: str, request: ActionRequest):
    """提交玩家行动——触发 AI DM 处理并生成叙事。

    处理是异步的：此端点立即返回 accepted:true，
    实际的叙事生成在后台进行，通过 SSE 推送给前端。
    """
    state = session_manager.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="会话不存在或已结束")

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
    except Exception as e:
        await push_event(state, "error", {
            "code": "INTERNAL_ERROR",
            "msg": f"处理失败: {str(e)}",
        })
        await push_event(state, "end_of_turn", {})


@app.get("/api/game/{session_id}/stream")
async def stream_events(session_id: str, last_event_seq: int = 0):
    """SSE 长连接——推送游戏事件流。

    前端通过 EventSource 连接此端点，接收实时叙事、骰子结果、状态更新等事件。
    支持通过 last_event_seq 参数进行断线重连。
    """
    state = session_manager.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="会话不存在或已结束")

    return StreamingResponse(
        sse_event_generator(state),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )


@app.get("/api/game/{session_id}/journal")
async def get_player_journal(session_id: str):
    """获取玩家笔记——侧边栏显示当前场景、NPC(可见信息)、剧情进度。

    这个端点返回仅对玩家可见的信息：
    - 当前场景（位置/时间/天气/氛围）
    - NPC按态度分组（仅可见字段）
    - 剧情旗标
    - 已发现地点
    """
    state = session_manager.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="会话不存在或已结束")

    ws = getattr(state, 'world_state', None)
    if ws is None:
        return {"scene": {"location": "未知", "time": "?", "weather": "", "atmosphere": ""},
                "npcs": {"allies": [], "enemies": [], "neutrals": [], "total": 0},
                "plot_flags": [], "locations": []}

    return ws.to_player_journal()


@app.post("/api/game/{session_id}/abort")
async def abort_generation(session_id: str):
    """中断当前 AI 生成——玩家点击"跳过"按钮时调用。"""
    state = session_manager.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="会话不存在或已结束")

    state.request_abort()
    await push_narrative_flush(state, "[生成已中断]")

    return {"aborted": True}
