"""同回合重复调用保护：结算类工具用相同参数再调时复用上次结果。

两类问题一起拦：
- 并发的多个专业子 Agent 对同一目标重复扣血/扣资源；
- 同一个回合里用完全相同的参数重掷一次失败的检定（等于白送机会）。

声明了额外行动来源时（多段攻击/传奇动作/时间暂停……），同样的参数会被合法地重复调用，
那时交给行动经济账本按配额管控，这里不拦——所以合法多动不会被固定流程封死。
"""
from __future__ import annotations

import json
from typing import Any

# 结算类工具：同回合内参数完全相同的调用视为重复
DEDUPE_TOOLS = {
    "combat_round", "enemy_attack", "death_saving_throw", "cast_spell",
    "take_rest", "update_state", "adjust_resource",
    # 解除失败 5 点以内可以再试，但"再试"是下一回合的事：同回合同参数重掷等于白送一次机会
    "resolve_trap",
    # 同回合同参数重掷同样等于白送一次机会
    "resolve_stealth",
    # 对抗动作同理：同回合同参数重掷等于把失败的擒抱白送一次机会
    "resolve_contest",
    # 同一次中毒不该掷两遍豁免
    "apply_poison",
    # 同回合同参数重复"冲刺"等于白送一次免费冲刺
    "resolve_chase",
}

# 这些工具在声明 action_source 后允许"同样参数再调一次"（多段攻击等）
ACTION_SOURCE_LIFTS_DEDUPE = ("combat_round", "enemy_attack")


def call_key(name: str, args: dict) -> str:
    """去重键：工具名 + 参数（排序后的 JSON，参数顺序不同也视为同一次调用）。"""
    try:
        payload = json.dumps(args or {}, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        payload = str(args)
    return f"{name}:{payload}"


def duplicate_result(state: Any, name: str, args: dict) -> str:
    """本回合已用相同参数调用过就返回"沿用上次结果"的文本；否则空串。"""
    if name not in DEDUPE_TOOLS:
        return ""
    cache = getattr(state, "turn_tool_results", None)
    if not isinstance(cache, dict):
        return ""
    previous = cache.get(call_key(name, args))
    if previous is None:
        return ""
    return (f"[重复调用已跳过] 本回合已执行过相同的 {name}，沿用上次结果"
            f"（不要重复扣血/扣资源）：{str(previous)[:400]}")


def remember_result(state: Any, name: str, args: dict, result: Any) -> None:
    """记下这次结算结果，供本回合后续的相同调用复用。"""
    if name not in DEDUPE_TOOLS:
        return
    cache = getattr(state, "turn_tool_results", None)
    if isinstance(cache, dict):
        cache[call_key(name, args)] = str(result)
