"""新局创建：角色/会话落库、规则系统衍生数值、世界状态初始化。

从 `backend/routers/game.py` 搬出——那里原来一个 342 行的路由函数同时负责
参数钳制、规则系统衍生值、剧本装载、世界状态初始化与响应组装。

HTTP 语义保持不变：校验失败仍抛 HTTPException（由路由层原样透出）。
"""
from __future__ import annotations

import re

from fastapi import HTTPException

from backend.character_names import generate_character_name as _generate_character_name
from backend.config import settings
from backend.engine.session import session_manager
from backend.game_derived import (
    apply_starter_equipment, apply_system_derived, build_status_payload,
)
from backend.game_world_init import init_world_state
from backend.models import Character, GameSession, User
from backend.schemas import NewGameRequest, NewGameResponse


def normalize_known_spells(spells: list[dict] | None) -> list[dict]:
    """规范化已习得法术，确保 classes 始终是数组，避免前端崩溃。"""
    out: list[dict] = []
    for s in spells or []:
        if isinstance(s, str):
            s = {"name": s}
        if not isinstance(s, dict):
            continue
        classes = s.get("classes") or []
        if isinstance(classes, str):
            classes = [x.strip() for x in re.split(r"[,，、]", classes) if x.strip()]
        elif isinstance(classes, list):
            classes = [str(x) for x in classes if x]
        else:
            classes = []
        out.append({**s, "classes": classes})
    return out


# 兼容历史 import 名（前端/脚本/旧代码曾按这个名字引用）
_normalize_known_spells = normalize_known_spells


def clamp_attributes(game_system: str, attrs: dict) -> dict:
    """数值钳制：D&D 系 3-18，COC 系 1-99，自定义仅保证整数。"""
    if game_system == "coc":
        coc_keys = {"str", "con", "dex", "int", "pow", "cha", "siz", "edu"}
        return {k: (max(1, min(99, int(v))) if k in coc_keys else int(v)) for k, v in attrs.items()}
    if game_system in ("dnd5e", "dnd4e"):
        dnd_keys = {"str", "dex", "con", "int", "wis", "cha"}
        return {k: (max(3, min(18, int(v))) if k in dnd_keys else int(v)) for k, v in attrs.items()}
    return {k: int(v) for k, v in attrs.items()}


def compute_starting_ac(race: str, char_class: str, attributes: dict) -> int:
    """白板角色的初始 AC（按职业/敏捷/种族推导，范围钳制在 8-22）。"""
    attrs = attributes or {}
    dex_ac = (attrs.get("dex", 10) - 10) // 2
    if char_class in ("战士", "圣武士"):
        ac = 16
    elif char_class == "游侠":
        ac = 14 + max(-2, min(2, dex_ac))
    elif char_class == "野蛮人":
        ac = 10 + dex_ac + (attrs.get("con", 10) - 10) // 2
    elif char_class == "武僧":
        ac = 10 + dex_ac + (attrs.get("wis", 10) - 10) // 2
    else:
        ac = 11 + dex_ac
    if "山地矮人" in (race or ""):
        ac += 1
    return max(8, min(22, ac))


async def create_game_session(request: NewGameRequest) -> NewGameResponse:
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
        attrs = clamp_attributes(request.game_system, attrs)

        # 如果角色名为空或为默认值"冒险者"，根据种族+性别自动生成
        char_name = request.character_name
        if not char_name or char_name.strip() in ("", "冒险者"):
            char_name = _generate_character_name(request.race, request.gender)

        starting_gold = request.gold
        if starting_gold is None:
            from backend.engine.starting_gold import generate_starting_gold
            starting_gold = await generate_starting_gold(
                api_key=request.api_key,
                model_name=request.model_name,
                base_url=request.base_url,
                game_system=request.game_system,
                char_class=request.char_class,
                outline=request.world_outline or request.world_context or "",
                backstory=request.backstory or "",
            )
        character = Character(
            user_id=user.id,
            name=char_name,
            gender=request.gender,
            race=request.race,
            char_class=request.char_class,
            level=1,
            hp=30, max_hp=30,
            mp=10, max_mp=10,
            gold=starting_gold,
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
        # 计算AC：职业/敏捷/种族推导，规则细节见 compute_starting_ac
        _ac = compute_starting_ac(character.race, character.char_class,
                                     character.attributes or {})

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
            "known_spells": normalize_known_spells(request.known_spells),
        }

        # 按规则系统预填衍生数值 + 初始白板装备（查表逻辑拆到 game_derived）
        apply_system_derived(request.game_system, character_info, request.luck or 50)
        apply_starter_equipment(request.game_system, character, character_info)

        # 如果指定了已保存剧本ID且不是全新世界——加载剧本
        if request.scenario_id and not request.new_world:
            from backend.scenario_store import Scenario
            saved = Scenario.load(request.scenario_id, request.username)
            if saved:
                # 角色系统绑定剧本系统：5e角色只能用5e剧本，4e角色只能用4e剧本……
                scenario_system = (saved.meta.system or "dnd5e")
                if scenario_system != request.game_system:
                    raise HTTPException(
                        status_code=400,
                        detail=f"剧本系统与角色系统不匹配：剧本为 {scenario_system}，角色为 {request.game_system}。请选择相同系统的剧本。",
                    )
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

        # 初始化持久化世界状态（json 还原或空世界 + 预设场景，拆到 game_world_init）
        s.world_state = init_world_state(session.id, request.world_state_json, character_info)

        await db.commit()

    # 返回可直接用于前端状态恢复的 status（含正确 username 与 camelCase 字段）
    _status = build_status_payload(character_info, request.username, char_name)

    return NewGameResponse(
        session_id=session.id,
        character_id=character.id,
        username=request.username or "default",
        status=_status,
        sse_url=f"/api/game/{session.id}/stream",
    )
