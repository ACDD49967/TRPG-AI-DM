"""玩家回合的准备阶段：清理账本 → 先攻提示 → 模块分发与知识检索 → 记忆装配 → 子 Agent 委派。

从 backend.engine.dm_agent 拆出；`_process_player_action_inner` 仍负责提示词装配与流式循环，
这里只产出一次回合所需的上下文（TurnContext）。
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any

from backend.config import settings
from backend.engine.dm_prompts import build_character_info
# 简报层归属 dm_brief；`_build_graph_context_text` 从这里再导出，dm_agent 的旧 import 不变
from backend.engine.dm_brief import (  # noqa: F401
    _build_graph_context_text, assemble_brief_context,
)
from backend.engine.dm_runtime import (
    MODULE_TOOL_NAMES, _client, _game_system, _model, _module_tools, _play_mode,
)
from backend.engine.focused_subagents import (
    build_dm_brief_tasks, delegation_execution_context, delegation_is_complete,
    format_dm_brief, get_skill_instruction, plan_task_keys, run_tool_subagents,
    MAX_DELEGATED_TASKS,
)
from backend.engine.game_systems import get_system
from backend.engine.prompt_guard import sanitize_user_text
from backend.engine.session import GameSessionState, push_event
from backend.engine.short_term_memory import build_memory_context
from backend.engine.world_builder import build_world  # noqa: F401  (保持与原模块一致的可用面)
from backend.engine.world_state import WorldState
from backend.knowledge_base import get_knowledge_base
from backend.skills import get_skill


from backend.engine.combat import _refresh_combat_state  # noqa: E402


_SETTLEMENT_INTENT_PATTERNS = {
    "enemy_action": re.compile(
        r"(逼|引诱|诱使|挑衅|激怒|逗弄|等它|让它|引它)[^。\n]{0,12}"
        r"(吐|喷|攻击|出手|扑|咬|抓|射|施法|打|冲锋)"),
    "attack": re.compile(r"攻击|砍|劈|刺|捅|抡|砸|射击|放箭|射他|射它|突袭|偷袭|追击|追杀|"
                         r"干掉|击倒|打倒|杀死|击杀|迎战|交战|对付|挥剑|拔剑|拔刀|冲上去|扑上去"),
    "cast": re.compile(r"施法|施放|施展|念咒|祷念|吟唱法术|使用法术|放出法术"),
    "rest": re.compile(r"短休|长休|休息|扎营|睡一觉|睡下|包扎|恢复体力|喘口气"),
}


_SETTLEMENT_TOOLS = {
    "enemy_action": {"enemy_attack"},
    "attack": {"combat_round"},
    "cast": {"cast_spell"},
    "rest": {"take_rest"},
}


def required_settlement_group(player_input: str) -> str:
    """返回本回合玩家声明动作所需的结算类别：attack / cast / rest / ""。"""
    text = str(player_input or "")
    for group in ("enemy_action", "attack", "cast", "rest"):
        if _SETTLEMENT_INTENT_PATTERNS[group].search(text):
            return group
    return ""




@dataclass
class TurnContext:
    """一次玩家回合的准备阶段产物（检索/记忆/委派/结算意图）。"""

    player_input: str = ""
    client: Any = None
    delegated_tools_executed: Any = None
    delegation_used: Any = None
    dispatch_plan: Any = None
    execution_context: Any = None
    lite: Any = None
    memory_context_override: Any = None
    model: Any = None
    module: Any = None
    retrieved: Any = None
    sanitize_user_text: Any = None
    settled_tools: Any = None
    settlement_group: Any = None
    settlement_tools: Any = None
    skill: Any = None
    subagent_brief: Any = None
    telemetry: Any = None


async def _prepare_turn(state: GameSessionState, player_input: str) -> TurnContext:
    """回合准备：清理账本 → 先攻提示 → 模块分发与知识检索 → 记忆装配 → 子 Agent 委派。"""
    from backend.engine.prompt_guard import sanitize_user_text
    state.reset_abort()
    # 每轮开始就清空敌人行动记录；子 Agent 会在任务分配后调用 enemy_attack
    state.enemy_attack_log = {}
    # 行动经济账本每轮重置（含多段攻击/传奇动作等额外行动的配额）
    state.turn_action_ledger = {}
    # 4e 里程碑：这里兜住"敌人不是被打死的"收场（撤退/逃跑/世界状态移除）
    was_in_combat = bool(getattr(state, "in_combat", False))
    _refresh_combat_state(state)
    from backend.engine.milestones import record_encounter_end
    await record_encounter_end(state, was_in_combat)
    # 先攻：玩家的新一次行动 = 新的战斗轮；把顺序与"谁还没动"作为系统提示交给 DM，
    # 避免敌人多动/漏动（顺序与回合余额由后端维护，DM 只负责叙事）。
    from backend.engine import initiative
    initiative.replace_hint(state, initiative.begin_player_turn(state))
    # 回合开始效果按轮结算；新的玩家行动代表进入新轮，重新允许触发
    state.turn_start_effects_applied = set()
    # 同回合结算去重记录（tool_executor 使用）
    state.turn_tool_results = {}
    # P0-1修复（双保险）：确保WorldState始终存在，即使create_new_game漏初始化
    if getattr(state, 'world_state', None) is None:
        state.world_state = WorldState(session_id=state.session_id)
    telemetry = getattr(state, "telemetry", None)
    if telemetry is not None:
        telemetry.begin_turn(int(getattr(state.world_state, "turn_count", 0)) + 1)
    # 玩家声明的动作必须由工具结算（分发器可能把攻击误判成叙事模块）
    settlement_group = required_settlement_group(player_input)
    settlement_tools = _SETTLEMENT_TOOLS.get(settlement_group, set())
    lite = _play_mode(state) == "lite"
    skill = get_skill(_game_system(state))
    # 精简模式保留 5 轮活跃记忆（深度用 skill.history_rounds=10）。试过把 lite 也调到 10：
    # 3 run 中位 tokens 反而 114,414 → 156,182，说明 lite 的额外开销不是"上下文给少了"，
    # 而是紧凑提示让主 DM 自己多绕几轮；多给上下文只加 token，不减轮次。
    state.memory.max_active_turns = 5 if lite else skill.history_rounds
    state.memory.summary_trigger = state.memory.max_active_turns + 1

    # 提示注入防护：先清洗玩家输入，再进入缓存/检索/LLM
    sanitized = sanitize_user_text(player_input)
    if sanitized != player_input.strip():
        await push_event(state, "game_event", {"description": "已拦截输入中的提示注入尝试"})
    player_input = sanitized or "[系统已拦截可疑指令]"

    client = _client(state); model = _model(state)
    scenario_id = getattr(state, "scenario_id", None) or (state.character_info or {}).get("scenario_id") or None
    # 知识库检索放到线程中，并与模块分发并行，避免阻塞事件循环
    if telemetry is not None:
        telemetry.begin_phase("dispatch_retrieval")
    try:
        _kb = get_knowledge_base()
        retrieve_task = asyncio.create_task(asyncio.to_thread(
            _kb.retrieve, player_input,
            system=_game_system(state),
            # 精简模式用 top_k=3（深度 5）：实测把它提到 5 反而更贵
            # （3 run 中位 114,414 → 147,279），多给的片段没换来更少的主 DM 追问。
            top_k=3 if lite else skill.rag_top_k,
            username=state.username,
            scenario_id=scenario_id,
        ))

        # 主 Agent 模块化调度：LangGraph 分发到规则/战斗/场景/社交/记忆/图谱/叙事模块
        from backend.engine.dm_modules import run_dm_dispatch
        dispatch_plan = await run_dm_dispatch(state, player_input)
        module = str(dispatch_plan.get("module", "narrative"))
        retrieved = await retrieve_task
    finally:
        if telemetry is not None:
            telemetry.end_phase("dispatch_retrieval")
    module_chunk_limits = {
        "rules": 5, "combat": 3, "scene": 2, "social": 2,
        "memory": 2, "graph": 2, "narrative": 5,
    }
    retrieved = retrieved[:module_chunk_limits.get(module, 3)]

    # LangGraph 短期记忆装配 + EverOS 长期记忆检索：
    # 先由记忆图生成 essential/full 上下文与长期记忆简报，供主 DM 与记忆检索子 Agent 使用。
    memory_pack: dict = {}
    memory_context_override = ""
    if telemetry is not None:
        telemetry.begin_phase("memory")
    try:
        memory_pack = await build_memory_context(
            state, player_input, focused=module not in ("narrative", "memory"),
        )
        memory_context_override = str(memory_pack.get("context") or "")
    except Exception as e:
        print(f"[MemoryGraph] 短期记忆装配失败，回退旧版记忆: {e}")
        if telemetry is not None:
            telemetry.record_failure("memory", e)
    finally:
        if telemetry is not None:
            telemetry.end_phase("memory")

    # 多专业子 Agent 并发委派：规则/战斗战术/场景事实/剧情连续性/关系图谱各司其职，
    # 主 DM 只接收聚合后的“专家简报”，专注角色扮演、故事生成与世界操控。
    subagent_brief = ""
    delegation_used = False
    execution_context = ""
    delegated_tools_executed = False
    settled_tools: set[str] = set()
    if telemetry is not None:
        telemetry.begin_phase("delegation")
    try:
        # 子阶段：上下文装配（本地计算）/ 任务分配（一次 LLM）/ 子 Agent 执行（并发 LLM+工具）。
        # 只报一个 delegation 粗粒度看不出钱花在哪；子阶段同时给模型调用打上归属标签。
        if telemetry is not None:
            telemetry.begin_phase("delegation_context")
        # 上下文装配已搬到简报层（dm_brief.assemble_brief_context），这里只做编排
        brief_ctx = assemble_brief_context(
            state, player_input=player_input, module=module,
            memory_override=memory_context_override,
        )
        brief_tasks = build_dm_brief_tasks(
            player_input=player_input,
            module=module,
            lite=lite,
            system=_game_system(state),
            char_info=build_character_info(state),
            retrieved=retrieved,
            **brief_ctx,
        )
        if telemetry is not None:
            telemetry.end_phase("delegation_context")
            telemetry.begin_phase("delegation_plan")
        # 候选不超过并发预算时，"挑 2 个"与"跑满"的墙钟时间相同（都是并发执行），
        # 却要多付一次串行的任务分配 LLM 调用（实测 1.04 秒 / 287 token，占整轮约 10%）。
        # 因此只有候选真正超过并发预算、需要取舍时才请分配器决策。
        if module in ("narrative", "social", "scene") or len(brief_tasks) <= MAX_DELEGATED_TASKS:
            selected_tasks = list(brief_tasks)
            selected_keys = [str(t.get("key")) for t in selected_tasks]
        else:
            selected_keys = await plan_task_keys(
                client, model, player_input, module, brief_tasks, lite=lite,
            )
            selected_set = set(selected_keys)
            selected_tasks = [t for t in brief_tasks if str(t.get("key")) in selected_set] or brief_tasks
        if telemetry is not None:
            telemetry.end_phase("delegation_plan")
            telemetry.begin_phase("delegation_agents")
        # 子 Agent 带工具执行：工具结果只以简报形式返回主 DM，过程对玩家隐藏
        brief_results = await run_tool_subagents(client, model, selected_tasks, state)
        if telemetry is not None:
            telemetry.end_phase("delegation_agents")
        subagent_brief = format_dm_brief(brief_results)
        execution_context = delegation_execution_context(brief_results)
        delegated_tools_executed = any(r.successful_tools for r in brief_results.values())
        settled_tools = {t for r in brief_results.values() for t in r.successful_tools}
        delegation_used = delegation_is_complete(selected_tasks, brief_results, module)
        if settlement_tools and not (settled_tools & settlement_tools):
            # 子 Agent 没能结算玩家声明的动作 → 主 DM 必须保留工具亲自结算
            delegation_used = False
            print(f"[DMSubAgents] 本回合需结算 {settlement_group}，子Agent未结算，主DM保留工具")
        if subagent_brief:
            ok_count = len([
                v for v in brief_results.values()
                if v.completed
            ])
            print(f"[DMSubAgents] module={module} lite={lite} planned={selected_keys} "
                  f"agents={len(selected_tasks)} ok={ok_count} brief={len(subagent_brief)}")
    except Exception as e:
        print(f"[DMSubAgents] 并发子Agent委派失败，回退完整上下文: {e}")
        subagent_brief = ""
        delegation_used = False
        if telemetry is not None:
            telemetry.record_failure("delegation", e)
    finally:
        if telemetry is not None:
            # 子阶段若因异常半途中断，这里兜底收口（end_phase 对未开始的阶段是空操作）
            for _phase in ("delegation_context", "delegation_plan", "delegation_agents"):
                telemetry.end_phase(_phase)
            telemetry.end_phase("delegation")


    return TurnContext(
        client=client,
        delegated_tools_executed=delegated_tools_executed,
        delegation_used=delegation_used,
        dispatch_plan=dispatch_plan,
        execution_context=execution_context,
        lite=lite,
        memory_context_override=memory_context_override,
        model=model,
        module=module,
        player_input=player_input,
        retrieved=retrieved,
        sanitize_user_text=sanitize_user_text,
        settled_tools=settled_tools,
        settlement_group=settlement_group,
        settlement_tools=settlement_tools,
        skill=skill,
        subagent_brief=subagent_brief,
        telemetry=telemetry,
    )
