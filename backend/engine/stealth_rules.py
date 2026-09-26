"""潜行与隐藏：隐匿检定对抗观察者的被动察觉，成功后登记「隐藏」状态。

5e 的隐藏是一步确定性判定——敏捷（隐匿）对抗观察者的被动察觉；成功后你未被看见，
你的攻击有优势、别人打你有劣势，而你一攻击/施法就暴露。
此前这全靠 DM 自己记 DC、自己决定"到底藏没藏住"，也没有任何可查的状态。

模块分工（`stealth_rules` 只留判定流程，并按惯例再导出另外两段）：
- `stealth_modifiers`：隐匿加值、护甲劣势、观察者挑选与被动察觉比对；
- `stealth_state`：隐藏状态的读写与出手暴露；

范围说明：光照逐级惩罚、静默移动、法术增益等未结构化情况，DM 可用 `dc` 直接覆盖，
或传 `advantage`/`advantage_reason` 声明，不会被固定流程封死。
"""
from __future__ import annotations

import random
from typing import Any

from backend.engine.combat_advantage_base import _norm
from backend.engine.session import GameSessionState, push_event
from backend.engine.stealth_modifiers import (  # noqa: F401  再导出
    armor_disadvantage, best_observer, creature_stealth_modifier, observer_passive_perception,
    observers, stealth_modifier,
)
from backend.engine.stealth_state import (  # noqa: F401  再导出
    HIDDEN, break_stealth, break_stealth_after_tool, exposing_actor, is_hidden, set_hidden,
)


def _int_arg(value: Any, default: int = 0) -> int:
    try:
        return int(float(value)) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _modifier(state: Any, target: str) -> int:
    from backend.engine.player_damage import is_player_name

    if is_player_name(state, target):
        return stealth_modifier(state)
    world = getattr(state, "world_state", None)
    return creature_stealth_modifier(world.get_npc(target) if world is not None else None)


def costs_player_action(args: dict, state: Any) -> bool:
    """这次潜行算不算玩家的动作：Hide 是动作，但 DM 让 NPC 藏起来时不该扣玩家的。

    盗贼的狡诈动作把 Hide 变成附赠动作，用 `action_source=bonus_action` 声明即可
    （行动经济账本按来源放行，这里不写死）。
    """
    from backend.engine.player_damage import is_player_name

    target = str((args or {}).get("target") or "").strip()
    return True if not target else is_player_name(state, target)


async def _exec_resolve_stealth(args: dict, state: GameSessionState) -> str:
    from backend.engine.player_damage import is_player_name

    args = args or {}
    action = _norm(args.get("action") or "hide")
    target = str(args.get("target") or "").strip() or str(getattr(state, "character_name", "") or "玩家")
    if action in ("reveal", "expose", "现身", "暴露"):
        if not is_hidden(state, target):
            return f"⚠ {target} 当前没有隐藏，无需现身"
        await set_hidden(state, target, False, reason="主动现身")
        return f"👣 {target} 主动现身，隐藏状态结束。"
    if action not in ("hide", "sneak", "隐藏", "潜行"):
        return "⚠ resolve_stealth 需要 action：hide（藏起来）/ reveal（现身）"

    raw_observers = args.get("observers")
    observer_names = ([raw_observers] if isinstance(raw_observers, str)
                      else list(raw_observers or []))
    declared_dc = _int_arg(args.get("dc"))
    watcher = ""
    if declared_dc > 0:
        dc, source = declared_dc, f"DM 指定 DC {declared_dc}"
    else:
        watcher, dc = best_observer(state, observer_names, target=target)
        source = f"{watcher}的被动察觉 {dc}" if watcher else ""

    if not source:
        # 没有被谁盯着的迹象：直接算藏好（5e：无人看见时才谈得上藏）
        await set_hidden(state, target, True, reason="周围无人看见")
        return f"👻 {target}：周围没有能看穿你的生物，直接进入隐藏状态。"

    # 5e：在黑暗中（对方没有黑暗视觉）本来就看不见你——直接算藏好，不必再掷
    from backend.engine import light_rules

    if light_rules.effective_light(state, target) == light_rules.DARK:
        candidates = observers(state, observer_names, target=target)
        seers = [name for name, _ in candidates
                 if light_rules.vision_kind(state, name) == "darkvision"]
        if not seers:
            await set_hidden(state, target, True, reason="黑暗掩护")
            who = "、".join(name for name, _ in candidates) or "在场者"
            return f"🌑 {target}：一片漆黑，{who}没有黑暗视觉，看不见你——直接进入隐藏状态。"

    mod = _modifier(state, target)
    mode = _norm(args.get("advantage"))
    armor_note = armor_disadvantage(state) if is_player_name(state, target) else ""
    disadvantage = mode == "disadvantage" or bool(armor_note)
    advantage = mode == "advantage"
    if advantage and disadvantage:
        # 5e：优势与劣势互相抵消，回到正常掷骰
        advantage = disadvantage = False
        armor_note = ""
    rolls = [random.randint(1, 20)]
    if advantage or disadvantage:
        rolls.append(random.randint(1, 20))
    roll = (max(rolls) if advantage else min(rolls)) if len(rolls) > 1 else rolls[0]
    total = roll + mod
    success = roll == 20 or (roll != 1 and total >= dc)
    reason_note = str(args.get("advantage_reason") or "").strip()
    if armor_note:
        reason_note = f"{reason_note}；{armor_note}（劣势）" if reason_note else f"{armor_note}（劣势）"
    detail = [f"d20={roll}{'+' if mod >= 0 else ''}{mod}={total}", f"vs {source}"]
    if advantage:
        detail.append("优势")
    if disadvantage:
        detail.append("劣势")
    if reason_note:
        detail.append(reason_note)
    await push_event(state, "dice_roll", {
        "skill": f"{target} 隐匿", "dc": dc, "roll": roll, "modifier": mod,
        "result": "成功" if success else "失败",
    })
    line = f"🥷 {target} 隐匿：{'，'.join(detail)} → "
    if success:
        await set_hidden(state, target, True, reason=f"隐匿成功（{source}）")
        return line + "未被发现，进入隐藏状态（攻击有优势，一出手就暴露）"
    await set_hidden(state, target, False, reason="隐匿失败被察觉")
    watcher_hint = f"，{watcher}察觉到你" if watcher else ""
    return line + f"没能藏住{watcher_hint}"
