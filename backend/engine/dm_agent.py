import asyncio, json, random, re



from dataclasses import dataclass
from typing import Any





# ── 角色状态变更已拆分到 backend.engine.character_state ─────
from backend.engine.character_state import (  # noqa: E402
    _ARMOR_AC_BONUS, _equipped_armor_bonus, _exec_update_state, _format_condition,
    _handle_dying_transition, _has_feat_effect, _maybe_auto_death_save,
    _normalize_condition, _normalize_item, _normalize_spell, _recalc_equipment_effects,
    _update_conditions, tick_conditions,
)




from backend.engine.tool_executor import (  # noqa: E402
    execute_tool, primary_action_available,
)




from openai import AsyncOpenAI



from backend.config import ensure_valid_api_key, settings



from backend.telemetry import InstrumentedAsyncOpenAI



from backend.engine.session import (
    GameSessionState, push_event, push_narrative_token,
)



from backend.engine.rules import (
    AdvantageMode, DeathSaves,
    skill_check, combat_attack_roll,
    roll_death_save, short_rest, long_rest,
)



from backend.engine.tools import DM_TOOLS



from backend.engine.background_events import advance_background_plot_if_due



from backend.engine.world_builder import _derive_npc_stats



from backend.engine.world_state import WorldState, NpcEntry, PlotFlag, LocationEntry, NotableEntry



from backend.engine.game_systems import build_system_rule_block, build_stat_glossary, get_system



from backend.engine.focused_subagents import (
    build_dm_brief_tasks, format_dm_brief, get_skill_instruction, delegation_is_complete, delegation_execution_context,
    plan_task_keys, run_tool_subagents,
)



from backend.engine.short_term_memory import build_memory_context



from backend.knowledge_base import get_knowledge_base



from backend.save_manager import auto_save_if_needed



from backend.skills import get_skill



from backend.dm_toolbox import (
    generate_name,
    npc_quirk,
    roll_treasure,
    search_knowledge,
)



from backend.skills.prompts import (
    COC_DECISION_PROMPT,
    COC_SYSTEM_PROMPT,
    CUSTOM_DECISION_PROMPT,
    CUSTOM_SYSTEM_PROMPT,
    DND4E_DECISION_PROMPT,
    DND4E_SYSTEM_PROMPT,
)





# ═══════════════════════════════════════════════════════════════
# System Prompt —— D&D 5e 生动戏剧版
# ═══════════════════════════════════════════════════════════════

# ── 提示词与提示词装配已拆分到 backend.engine.dm_prompts ────
from backend.engine.dm_prompts import (  # noqa: E402
    COC_OPENING_PROMPT, COMPACT_DM_DECISION_PROMPT, COMPACT_DM_PROMPT,
    DM_DECISION_PROMPT, OPENING_PROMPT, SYSTEM_PROMPT, _extract_outline,
    _mode_instructions, build_character_info, build_system_prompt,
)
# 回合消息装配（系统提示词 + 历史 + 系统提示）已拆到 dm_messages
from backend.engine.dm_messages import build_turn_messages  # noqa: E402,F401





# ── 战斗/伤害已拆分到 backend.engine.combat ─────────────────
# 这里再导出，保持既有调用方（DM 主循环、tool_executor、测试）不变。
from backend.engine.combat import (  # noqa: E402
    _NPC_LEVEL_XP, _award_defeat_xp, _build_combat_snapshot, _defeat_xp_for,
    _exec_combat_round, _exec_enemy_attack, _exec_save_damage, _find_bestiary_card,
    _first_dice, _first_int, _persist_combat_damage, _player_attack_bonus,
    _refresh_combat_state, _register_combatant_from_card, _resolve_enemy_from_cards,
    _resolve_npc_hp, _roll_damage_simple, _weapon_dice_from_inventory,
)




# 玩家明确表达了"需要工具结算"的动作意图。分发器偶尔会把这类输入判成叙事模块，
# 而叙事模块的子 Agent 没有结算工具、主 DM 又可能因委派完成而交出工具——
# 结果玩家的攻击/施法/休息被"口述"掉，数值毫无变化。这里做代码级兜底。


















async def process_player_action(state: GameSessionState, player_input: str) -> str:
    """对外入口：串行化同一会话的玩家行动，避免并发修改世界状态。"""
    async with state.action_lock:
        return await _process_player_action_inner(state, player_input)








async def _process_player_action_inner(state: GameSessionState, player_input: str) -> str:
    ctx = await _prepare_turn(state, player_input)
    client = ctx.client
    delegated_tools_executed = ctx.delegated_tools_executed
    delegation_used = ctx.delegation_used
    dispatch_plan = ctx.dispatch_plan
    execution_context = ctx.execution_context
    lite = ctx.lite
    memory_context_override = ctx.memory_context_override
    model = ctx.model
    module = ctx.module
    player_input = ctx.player_input
    retrieved = ctx.retrieved
    settled_tools = ctx.settled_tools
    settlement_group = ctx.settlement_group
    settlement_tools = ctx.settlement_tools
    skill = ctx.skill
    subagent_brief = ctx.subagent_brief
    telemetry = ctx.telemetry

    # 提示词装配已拆到 dm_messages（纯装配，不调模型、不写状态）
    sp, messages = build_turn_messages(
        state=state, player_input=player_input, retrieved=retrieved,
        dispatch_plan=dispatch_plan, subagent_brief=subagent_brief,
        memory_context_override=memory_context_override, module=module, lite=lite,
        delegation_used=delegation_used, execution_context=execution_context, skill=skill,
    )

    module_tools = [] if delegation_used else _module_tools(module, skill.tools)
    if telemetry is not None:
        # prompt 体积归因：中文约 1 字符≈1 token，先量清楚再决定砍哪块
        try:
            telemetry.record_sizes(
                system_prompt_chars=len(sp),
                tool_schema_chars=len(json.dumps(module_tools, ensure_ascii=False)) if module_tools else 0,
                history_chars=sum(len(str(m.get("content") or "")) for m in messages if m.get("role") == "assistant"),
            )
        except Exception:
            pass
    # 兜底初值：循环抛错时下面的 except 会用它返回"[AI暂不可用]"（与拆分前一致）
    full = ""
    suggested = False
    try:
        # 工具循环（流式生成/工具执行/强制结算守卫）拆到 dm_tool_loop；
        # hooks 在这里解析——测试用 patch.object(dm_agent, ...) 替换这三个依赖。
        from backend.engine.dm_tool_loop import ToolLoopHooks, run_tool_loop

        full, suggested = await run_tool_loop(
            state, client=client, model=model, messages=messages, module_tools=module_tools,
            skill=skill, module=module, lite=lite, settlement_group=settlement_group,
            settled_tools=settled_tools, settlement_tools=settlement_tools,
            delegated_tools_executed=delegated_tools_executed, delegation_used=delegation_used,
            telemetry=telemetry,
            hooks=ToolLoopHooks(
                stream_with_tools=_stream_with_tools,
                execute_tool=execute_tool,
                push_event=push_event,
            ),
        )

        # 回合收尾（建议/补叙事/世界维护/记忆/自动存档）拆到 dm_finalize；
        # hooks 在这里解析——测试用 patch.object(dm_agent, ...) 替换这些函数。
        from backend.engine.dm_finalize import FinalizeHooks, finish_turn

        return await finish_turn(
            state, full=full, messages=messages, suggested=suggested,
            delegation_used=delegation_used, telemetry=telemetry,
            client=client, model=model, skill=skill, player_input=player_input,
            hooks=FinalizeHooks(
                generate_suggestions=_generate_suggestions_subagent,
                advance_background=advance_background_plot_if_due,
                compress_memory=compress_memory_if_needed,
                auto_save=auto_save_if_needed,
                stream_with_tools=_stream_with_tools,
                push_event=push_event,
            ),
        )
    except Exception as e:
        if telemetry is not None:
            telemetry.record_failure("turn", e)
            telemetry.end_turn()
        await push_event(state, "error", {"code":"LLM_ERROR","msg":str(e)})
        await push_event(state, "end_of_turn", {})
        return full or "[AI暂不可用]"




# ── 工具处理器按域拆分（session/media/world）─────────────────
# 这里再导出，保持既有调用方（DM 主循环、tool_executor、测试）不变。
from backend.engine.session_tools import (  # noqa: E402
    SHORT_REST_RESOURCE_KEYS, ability_mod_for_skill, _exec_add_memory, _exec_death_save, _exec_dice_roll,
    _exec_equip_item, _exec_record_plot_memory, _exec_rest, _exec_search_memory,
    _exec_suggest_choices,
)


from backend.engine.media_tools import (  # noqa: E402
    _exec_add_scenario_bestiary, _exec_add_scenario_map, _exec_add_scenario_spell,
    _exec_adjust_bestiary, _exec_cast_spell, _exec_forget_spell,
    _exec_get_bestiary_card, _exec_get_location_card, _exec_learn_spell,
    _exec_search_bestiary, _exec_search_locations, _exec_search_spells,
    _exec_update_bestiary, _exec_update_city, _format_bestiary_card,
    _format_location_card, _search_spell_for_entity,
)


from backend.engine.world_tools import (  # noqa: E402
    _exec_adjust_npc, _exec_adjust_resource, _exec_character_note,
    _exec_get_character_state, _exec_promote_npc, _exec_prune_world_state,
    _exec_reveal_info, _exec_search_npcs, _exec_update_scene,
    _exec_update_world_state,
)

from backend.engine.graph_tools import (  # noqa: E402
    KG_AGENT_SYSTEM_PROMPT, KG_AGENT_USER_PROMPT, _call_knowledge_graph_agent,
    _exec_get_entity_graph, _exec_get_graph_path, _exec_update_knowledge_graph,
    _kg_extract_json,
)



# ── 运行期工具已拆分到 backend.engine.dm_runtime ─────────────
# 这里再导出，保持既有调用方（DM 主循环、工具模块、测试）不变。
from backend.engine.dm_turn import TurnContext, _prepare_turn  # noqa: E402
from backend.engine.dm_turn import (  # noqa: E402
    _SETTLEMENT_TOOLS, _build_graph_context_text, required_settlement_group,
)


from backend.engine.dm_runtime import (  # noqa: E402
    CLICHE_PATTERNS, MODULE_TOOL_NAMES, _STREAM_USAGE_UNSUPPORTED, _as_bool,
    _call_thinking_params, _client, _dedupe_fragments, _game_system,
    _is_player_visible_segment, _META_LEAK_PATTERN, _model, _module_tools,
    _play_mode, _safe_error_text, _stream_with_tools, _thinking_extra_body,
    _thinking_params, _TOOL_ECHO_PATTERN, _TOOL_ECHO_SIGNATURE,
    dm_think_mode, sanitize_narrative,
)


# ── 再导出：开场白 / 记忆压缩 / 子 Agent 调度已拆出 ──
from backend.engine.dm_subagents import (  # noqa: E402
    _generate_suggestions_subagent,
    _run_focused_subagent,
)
from backend.engine.dm_memory import (  # noqa: E402
    COMPRESS_SUMMARY_PROMPT,
    compress_memory_if_needed,
)
from backend.engine.dm_opening import (  # noqa: E402
    generate_opening_scene,
)
