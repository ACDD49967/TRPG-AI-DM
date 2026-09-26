"""行动经济：一单位一主行动，额外行动必须声明来源且受配额限制。

从 tool_executor 拆出：它只依赖会话状态与世界状态，和工具分发没有耦合；
4e 的行动点消耗也记在这里（spend_action_point）。
"""
from __future__ import annotations

import re
from typing import Any


def normalize_actor(state: Any, name: str) -> str:
    """把行动者名字归一成账本键（去注解、按已有 NPC 归名、忽略大小写/空白）。"""
    raw = re.sub(r"\s+", "", str(name or ""))
    world = getattr(state, "world_state", None)
    if world is not None:
        try:
            raw = world.canonical_npc_name(raw)
        except Exception:
            pass
    return (raw or "未知").lower()




def _ledger(state: Any) -> dict[str, dict[str, int]]:
    ledger = getattr(state, "turn_action_ledger", None)
    if not isinstance(ledger, dict):
        ledger = {}
        try:
            state.turn_action_ledger = ledger
        except Exception:
            pass
    return ledger




def _tracker(state: Any):
    """当前会话的先攻表（未在战斗中时为 None）。"""
    from backend.engine import initiative
    return initiative.tracker_for(state)




def primary_action_available(state: Any, actor: str) -> bool:
    # 先攻表存在时以它为准：本轮回合用尽的单位不再"可行动"
    tracker = _tracker(state)
    if tracker is not None:
        combatant = tracker.find(actor)
        if combatant is not None:
            return combatant.turns_left > 0
    return _ledger(state).get(normalize_actor(state, actor), {}).get("primary", 0) < 1




def consume_action(state: Any, actor: str, source: str = "", requested: int = 0) -> tuple[bool, str]:
    """登记一次行动。返回 (是否允许, 拒绝原因)。"""
    # 先攻表负责"回合归属"：本轮回合用尽即拒绝；开启新回合时清空该单位的账本，
    # 让新回合重新拥有一次主行动（多重回合/时间暂停因此天然可用）。
    tracker = _tracker(state)
    if tracker is not None:
        allowed, reason, new_turn = tracker.consume(actor, source, requested)
        if not allowed:
            return False, reason
        if new_turn:
            _ledger(state).pop(normalize_actor(state, actor), None)
    ledger = _ledger(state)
    key = normalize_actor(state, actor)
    entry = ledger.setdefault(key, {})
    if not source:
        if entry.get("primary", 0) >= 1:
            return False, (
                f"{actor} 本回合的主行动已经结算过。若这是合法的额外行动"
                f"（多段攻击/动作如潮/传奇动作/加速术/时间暂停等），"
                f"请用 action_source 声明来源后重新调用；"
                f"不要为了重掷失败的结果而声明额外行动。"
            )
        entry["primary"] = 1
        return True, ""
    # 显式声明次数时以声明为准（如 multiattack attacks=3 就是 3 段），
    # 未声明时用该来源的默认上限；再做一次 1-8 的合理区间兜底。
    default_quota = ACTION_SOURCE_QUOTA.get(source, DEFAULT_EXTRA_ACTION_QUOTA)
    quota = requested if requested > 0 else default_quota
    quota = max(1, min(quota, 8))
    used = entry.get(source, 0)
    if used >= quota:
        return False, (
            f"{actor} 本回合的「{source}」已用完（上限 {quota} 次）。"
            f"请结束本回合，或在叙事中体现，不要重复结算。"
        )
    entry[source] = used + 1
    return True, ""



async def spend_action_point(state: Any) -> tuple[bool, str]:
    """D&D4e：花 1 点行动点换一次额外行动；没有点数就拒绝。

    行动经济只按 `action_source` 配额放行，不会自己扣资源——所以这里单独记账，
    否则行动点会变成面板上只涨不跌的摆设（和回复力那次的毛病一样）。
    """
    from backend.engine.character_state import _exec_update_state

    info = getattr(state, "character_info", {}) or {}
    have = int(info.get("action_points", 0) or 0)
    if have <= 0:
        return False, ("行动点不足：4e 每达成里程碑 +1、长休重置为 1，"
                       "本回合无法再用行动点换额外行动")
    await _exec_update_state(
        {"changes": {"action_points": -1}, "reason": "消耗行动点（额外行动）"}, state)
    return True, ""


async def deny_extra_action_without_action_point(
    state: Any, system: str, args: dict,
) -> str | None:
    """4e：声明用行动点换额外行动时扣点；点数不足返回拒绝原因，放行返回 None。

    放在这里而不是塞进 combat_round 里，是为了让"行动经济 + 资源记账"留在一个模块。
    """
    if system != "dnd4e":
        return None
    source, _requested = declared_action_source(args)
    if source != "action_point":
        return None
    ok, why = await spend_action_point(state)
    return None if ok else f"⚠ {why}"




def declared_action_source(args: dict) -> tuple[str, int]:
    """读取 DM 声明的额外行动来源与次数。"""
    source = str(args.get("action_source") or "").strip().lower()
    if not source and args.get("extra_action"):
        source = "extra_action"
    try:
        requested = max(0, int(args.get("attacks") or args.get("action_count") or 0))
    except (TypeError, ValueError):
        requested = 0
    return source, requested




ACTION_SOURCE_QUOTA = {
    "multiattack": 4,          # 多段攻击（5e 额外攻击最多 4 次）
    "extra_attack": 1,
    "two_weapon": 1,           # 双持附赠攻击
    "bonus_action": 1,
    "action_surge": 1,         # 5e 战士：每回合额外 1 次动作
    "haste": 1,                # 加速术：额外 1 次受限动作
    "legendary_action": 3,     # 传奇生物：每轮 3 次
    "lair_action": 1,
    "reaction": 1,
    "opportunity_attack": 1,
    "time_stop": 4,            # 时间暂停：1d4+1 个额外回合
    "surprise_round": 1,
    "action_point": 1,         # 4e：花 1 点行动点换一次额外行动（点数由 spend_action_point 记账）
}


DEFAULT_EXTRA_ACTION_QUOTA = 1


