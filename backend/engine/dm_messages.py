"""回合消息装配：系统提示词 + 历史轮次 + 本轮系统提示。

从 dm_agent 主循环拆出：这段是纯装配（不调模型、不写状态），
放在单独模块后主循环只剩"跑流式 + 收尾"。
"""
from __future__ import annotations

import re
from typing import Any

from backend.engine.dm_prompts import build_system_prompt
from backend.engine.prompt_guard import sanitize_user_text

# 感知类动词：命中就要提醒主 DM 走检定，不能只靠叙事
PERCEPTION_VERBS = r'观察|聆听|嗅\b|摸\b|翻找|侦查|张望|偷看|检查|搜索|细看|倾听|嗅探|听\b|看\b|闻\b'

_HISTORY_LIMITS = {
    "rules": 5, "combat": 4, "scene": 4, "social": 5,
    "memory": 8, "graph": 5,
}


def build_turn_messages(
    *,
    state: Any,
    player_input: str,
    retrieved: list | None,
    dispatch_plan: dict | None,
    subagent_brief: str,
    memory_context_override: str | None,
    module: str,
    lite: bool,
    delegation_used: bool,
    execution_context: str,
    skill: Any,
) -> tuple[str, list[dict]]:
    """返回 (system_prompt, messages)；不产生副作用，除了消费 pending_system_hints。"""
    sp = build_system_prompt(
        state, retrieved_chunks=retrieved, dispatch_plan=dispatch_plan,
        subagent_brief=subagent_brief,
        memory_context_override=memory_context_override or None,
    )

    messages: list[dict] = [{"role": "system", "content": sp}]
    base_history = 5 if lite else skill.history_rounds
    history_limit = _HISTORY_LIMITS.get(module, base_history)
    if delegation_used:
        # 专家简报已覆盖长期记忆/世界状态，但主 DM 仍保留最近 3 轮用于扮演连续性
        history_limit = min(history_limit, 3)
    for turn in state.memory.turns[-history_limit:]:
        messages.append({"role": "user",
                         "content": sanitize_user_text(turn.player_input) or turn.player_input})
        if turn.dm_response:
            # 历史回复统一截断：长期事实已在专家简报/记忆里，完整旧文只是重复付费
            messages.append({
                "role": "assistant",
                "content": turn.dm_response[:400] if delegation_used else turn.dm_response[:600],
            })
    messages.append({"role": "user", "content": player_input})

    if state.pending_system_hints:
        # 安全网提示（濒死等）在下一轮注入给 DM，不推向玩家
        for hint in list(state.pending_system_hints):
            messages.append({"role": "system", "content": hint})
        state.pending_system_hints.clear()

    if execution_context:
        messages.append({"role": "system", "content":
            "[执行记录] 以下记录可能包含部分完成的动作。已成功的动作不得重复执行；"
            "执行中/结果不明的动作先查询当前状态，仅补全未完成部分。\n" + execution_context})
    if delegation_used:
        messages.append({"role": "system", "content":
            "[系统] 本回合的规则/战斗/世界/记忆/图谱工具已由后台专业子Agent结算完成，结果见专家简报。"
            "你不再拥有工具调用权限，请直接输出玩家可见的剧情叙事；"
            "不要提及子Agent、工具、后台、简报，也不要复述数值。"})

    # 战斗模块强制：仅在主 DM 仍持有工具时要求它走工具
    if module == "combat" and not delegation_used:
        messages.append({"role": "system", "content":
            "[系统强制战斗执行] 本回合必须调用 dice_roll / search_npcs / search_bestiary / combat_round 等工具完成玩家行动结算。"
            "禁止只输出“我先确认”“让我看看”“我打算”等计划性独白而不调用工具；"
            "若需要先查敌人状态，可先 search_npcs / search_bestiary，随后仍必须用工具推进本回合。"})

    # P1-4修复：感知行为自动提醒——扫描玩家输入中的感知动词
    if not delegation_used and re.search(PERCEPTION_VERBS, player_input):
        messages.append({"role": "system", "content":
            "[系统提醒] B4规则：玩家正在进行感知行为。你必须判断DC和对应属性(WIS/Perception)，"
            "调用dice_roll。不允许仅用叙事代替检定。B5节查阅属性映射。"})

    return sp, messages


__all__ = ["build_turn_messages", "PERCEPTION_VERBS"]
