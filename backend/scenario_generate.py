"""剧本总结与建剧本：summary 生成、结构化剧本落库。

从 backend.scenario_importer 拆出。
"""
from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from backend.config import ensure_valid_api_key, settings
from backend.engine.game_systems import detect_game_system
from backend.logging_utils import get_logger
from backend.scenario_llm_split import llm_split_text
from backend.engine.prompt_guard import sanitize_user_text



# ═══════════════════════════════════════════════════════════════
# LLM 剧本总结
# ═══════════════════════════════════════════════════════════════

async def generate_scenario_from_text(
    source_text: str,
    chunks: list[str],
    title: str = "",
    description: str = "",
    username: str = "default",
    tone: str = "史诗奇幻",
    system: str | None = None,
    custom_rules: str = "",
    character_name: str = "冒险者",
    race: str = "人类",
    char_class: str = "战士",
    character_level: int = 1,
    api_key: str | None = None,
    model_name: str | None = None,
    base_url: str | None = None,
    splitter: str = "naive",
    target_score: int = 80,
    max_revisions: int = 2,
    custom_classes: list[str] | None = None,
    custom_skills: list[str] | None = None,
    extra_attributes: dict | None = None,
    thinking_strength: str = "medium",
    progress_callback=None,
    token_callback=None,
) -> dict[str, Any]:
    """读取文本→切分→多Agent生成新剧本→生成总结→保存到 scenarios/。"""
    from backend.engine.world_builder import build_world
    from backend.scenario_store import create_scenario

    source_text = sanitize_user_text(source_text)
    api_key = api_key or settings.LLM_API_KEY
    base_url = base_url or settings.LLM_BASE_URL
    model = model_name or settings.LLM_MODEL_NAME
    if not model:
        raise ValueError("请提供模型名称")
    api_key = ensure_valid_api_key(api_key)
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    # LLM 切分模式：调用 LLM 智能划分语义片段
    if splitter == "llm" and not chunks:
        chunks = await llm_split_text(
            source_text, api_key, model, base_url,
            thinking_strength=thinking_strength, progress_callback=progress_callback,
        )
    if not chunks:
        raise ValueError("切分后没有生成任何片段")

    if not system or system == "auto":
        system = detect_game_system(source_text, title)

    player_input = (
        f"冒险基调: {tone}\n"
        f"规则系统: {system}\n"
        f"角色: {character_name}, {race} {char_class}, Lv.{character_level}\n"
        f"描述: {description or '根据导入的剧本生成一个完整冒险'}"
    )

    # 将切分后的块交给世界生成器；块之间用分隔符保留语义边界
    # 超长剧本先截断到安全长度，避免超出 LLM 上下文窗口
    reference_script = "\n\n===== 剧本片段 =====\n\n".join(
        f"[片段 {i + 1}/{len(chunks)}]\n{chunk}" for i, chunk in enumerate(chunks)
    ) if chunks else source_text
    if len(reference_script) > 30000:
        reference_script = reference_script[:30000] + "\n\n...[内容过长，已截断用于世界生成]..."
    if progress_callback:
        progress_callback("读取并切分剧本完成", 6, f"共 {len(chunks)} 个片段，开始生成世界")

    outline_text, score, history, world_state = await build_world(
        player_input=player_input,
        reference_script=reference_script,
        api_key=api_key,
        model_name=model_name,
        base_url=base_url,
        game_system=system,
        custom_rules=custom_rules,
        custom_classes=custom_classes,
        custom_skills=custom_skills,
        extra_attributes=extra_attributes,
        target_score=target_score,
        max_revisions=max_revisions,
        thinking_strength=thinking_strength,
        progress_callback=progress_callback,
        token_callback=token_callback,
    )

    if progress_callback:
        progress_callback("生成剧本总结", 88, "正在生成约400字剧本总结...")
    summary = await generate_summary(
        client, model, outline_text, source_text, token_callback=token_callback,
        error_callback=lambda msg: progress_callback("LLM警告", 0, f"总结生成出错: {msg}") if progress_callback else None,
    )
    if progress_callback:
        progress_callback("保存剧本与知识库", 94, "正在保存剧本并写入知识库...")

    ws_json = {
        "world_outline": outline_text,
        "npcs": [
            {
                "name": n.name, "race": n.race, "role": n.role,
                "location": n.location, "attitude": n.attitude,
                "alive": n.alive, "personality": n.personality,
                "motivation": n.motivation, "secret": n.secret,
                "relation_to_plot": n.relation_to_plot,
                "visibility": n.visibility.to_dict() if hasattr(n.visibility, "to_dict") else {},
                "discovered": n.discovered,
            }
            for n in world_state.npcs
        ],
        "plot_flags": [
            {"key": f.key, "status": f.status, "description": f.description, "consequence": f.consequence, "visible": f.visible}
            for f in world_state.plot_flags
        ],
        "locations": [
            {
                "name": l.name, "description": l.description, "status": l.status,
                "type": l.type, "culture": l.culture,
                "notable_figures": l.notable_figures, "dangers": l.dangers,
                "secrets": l.secrets, "secret_revealed": l.secret_revealed,
                "related_locations": l.related_locations,
                "related_npcs": l.related_npcs,
                "related_creatures": l.related_creatures,
                "discovered": l.discovered,
            }
            for l in world_state.locations
        ],
        "world_rules": world_state.world_rules,
    }
    world_state_json = json.dumps(ws_json, ensure_ascii=False)

    saved = create_scenario(
        world_outline=outline_text,
        world_state_json=world_state_json,
        reference_script=source_text,
        source_chunks=chunks,
        custom_rules=custom_rules,
        custom_classes=custom_classes or [],
        custom_skills=custom_skills or [],
        extra_attributes=extra_attributes or {},
        notes=f"导入方式: {splitter} 切分 · 共 {len(chunks)} 个片段",
        title=title or (outline_text.split("\n")[0].replace("#", "").strip()[:60] or "导入冒险"),
        description=description or source_text[:200],
        summary=summary,
        system=system,
        tone=tone,
        character_name=character_name,
        race=race,
        char_class=char_class,
        level=character_level,
        score=score,
        username=username,
    )

    # 把世界状态中的常驻地点同步到该剧本的地点图鉴
    try:
        from backend.media_manager import sync_scenario_bestiary, sync_scenario_maps, sync_scenario_spells
        sync_scenario_maps(username, saved.id, world_state.locations, system)
        sync_scenario_bestiary(username, saved.id, world_state.creatures, system)
        sync_scenario_spells(username, saved.id, world_state.spells, system)
    except Exception as e:
        get_logger("scenario_import").warning("sync_scenario_* 失败（已忽略）: %s", e, exc_info=True)

    # 将剧本细节写入本地知识库（限定到 scenario_id，避免污染总知识库）
    try:
        from backend.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        scenario_source = f"scenario:{saved.id}"
        for d in kb.list_documents(username, include_scenario=True):
            if d.get("source") == scenario_source or d.get("scenario_id") == saved.id:
                kb.remove_document(d["id"], username)
        kb.add_document(
            title=f"剧本：{saved.meta.title}",
            content=source_text,
            source=scenario_source,
            system=system,
            tags=["剧本", system, splitter],
            username=username,
            scenario_id=saved.id,
        )
    except Exception as e:
        print(f"[ScenarioImporter] 知识库写入失败（不影响剧本生成）: {e}")

    npc_summary = [{"name": n.name, "role": n.role, "attitude": n.attitude}
                   for n in world_state.npcs]
    flag_summary = [{"key": f.key, "status": f.status} for f in world_state.plot_flags]

    return {
        "scenario_id": saved.id,
        "title": saved.meta.title,
        "summary": summary,
        "system": saved.meta.system,
        "content": outline_text,
        "score": score,
        "scores_detail": {},
        "revision_history": history,
        "npcs": npc_summary,
        "plot_flags": flag_summary,
        "world_rules": world_state.world_rules,
        "world_state_json": world_state_json,
        "source_chunks": chunks,
        "chunk_count": len(chunks),
        "splitter": splitter,
    }


# 总结相关实现拆到 scenario_summary，这里再导出（scenario_importer 门面不用改）
from backend.scenario_summary import (  # noqa: E402,F401
    SUMMARY_PROMPT, _fallback_summary, generate_summary,
)
