"""陷阱：被动察觉自动发现、主动搜索掷感知、解除失败超过 5 点立即触发。

这三步都是确定性规则，以前全靠 DM 记 DC、比数字、再自己决定"失败多少算踩响"。
伤害不在这里重算——触发时直接走 `save_damage`，抗性/免疫/临时生命值那套管线照旧生效。
"""
from __future__ import annotations

import random
from typing import Any

from backend.engine.session import GameSessionState, push_event
# 熟练加值 / 被动察觉是潜行与陷阱共用的算法，实现在 perception_rules；这里再导出，
# 外部（含测试）继续 `from backend.engine.trap_rules import passive_perception` 不变。
from backend.engine.perception_rules import (  # noqa: F401  再导出
    passive_perception, proficiency_bonus,
)

TRIGGER_MARGIN = 5      # 解除检定失败超过这个差值就触发陷阱


def costs_player_action(args: dict, state: Any) -> bool:
    """这次陷阱判定算不算玩家的动作。

    解除机关、主动搜查都要花一次动作；不传 `searching` 的被动察觉（不掷骰）不算动作，
    所以"路过时顺手发现"不会被行动账本拦下。
    """
    stage = str((args or {}).get("stage") or "detect").strip().lower()
    return stage == "disarm" or _as_bool((args or {}).get("searching"))


def _has_skill(state: Any, *keywords: str) -> bool:
    info = getattr(state, "character_info", {}) or {}
    for skill in (info.get("skill_proficiencies") or []):
        text = str(skill).lower()
        if any(keyword.lower() in text for keyword in keywords):
            return True
    return False


def perception_modifier(state: Any) -> int:
    """主动搜索用的感知（察觉）加值：感知调整值 + 察觉熟练。"""
    from backend.engine.damage_rules import ability_modifier
    info = getattr(state, "character_info", {}) or {}
    mod = ability_modifier((info.get("attributes") or {}).get("wis", 10))
    if _has_skill(state, "察觉", "perception"):
        mod += proficiency_bonus(state)
    return mod


def disarm_modifier(state: Any) -> int:
    """解除陷阱用的敏捷加值：敏捷调整值 + 巧手/盗贼工具熟练。"""
    from backend.engine.damage_rules import ability_modifier
    info = getattr(state, "character_info", {}) or {}
    mod = ability_modifier((info.get("attributes") or {}).get("dex", 10))
    if _has_skill(state, "巧手", "盗贼工具", "sleight", "thieves"):
        mod += proficiency_bonus(state)
    return mod


async def _exec_resolve_trap(args: dict, state: GameSessionState) -> str:
    stage = str(args.get("stage") or "detect").strip().lower()
    name = str(args.get("name") or "陷阱").strip() or "陷阱"
    if stage == "detect":
        return await _detect(name, args, state)
    if stage == "disarm":
        return await _disarm(name, args, state)
    return "⚠ resolve_trap 需要 stage：detect（发现）/ disarm（解除）"


async def _detect(name: str, args: dict, state: GameSessionState) -> str:
    dc = _int_arg(args.get("detect_dc"), 12)
    if not _as_bool(args.get("searching")):
        # 不主动搜索：被动察觉直接跟 DC 比，不用掷骰
        passive = passive_perception(state)
        found = passive >= dc
        return (f"👁️ {name}：被动察觉 {passive} vs 发现 DC{dc} → "
                f"{'你注意到可疑的痕迹' if found else '你没有察觉异常'}")
    mod = perception_modifier(state)
    roll = random.randint(1, 20)
    total = roll + mod
    success = roll == 20 or (roll != 1 and total >= dc)
    await push_event(state, "dice_roll", {
        "skill": f"搜查·察觉（{name}）", "dc": dc,
        "roll": roll, "modifier": mod, "result": "成功" if success else "失败",
    })
    return (f"🔍 {name} 搜查：d20={roll}{'+' if mod >= 0 else ''}{mod}={total} vs 发现 DC{dc} → "
            f"{'发现陷阱' if success else '没有发现'}")


async def _disarm(name: str, args: dict, state: GameSessionState) -> str:
    from backend.engine.combat_save_damage import _exec_save_damage
    from backend.engine.player_damage import is_player_name

    dc = _int_arg(args.get("disarm_dc"), 12)
    mod = disarm_modifier(state)
    roll = random.randint(1, 20)
    total = roll + mod
    margin = total - dc
    success = roll == 20 or (roll != 1 and margin >= 0)
    if not success and roll == 1:
        margin = min(margin, -TRIGGER_MARGIN)      # 自然 1 直接触发
    await push_event(state, "dice_roll", {
        "skill": f"解除（{name}）", "dc": dc,
        "roll": roll, "modifier": mod, "result": "成功" if success else "失败",
    })
    line = (f"🧰 {name} 解除：d20={roll}{'+' if mod >= 0 else ''}{mod}={total} vs 解除 DC{dc} → ")
    if success:
        return line + "成功，机关被拆开"
    if margin > -TRIGGER_MARGIN:
        return line + f"失败（差 {abs(margin)} 点），陷阱尚未触发，可以再试一次"
    # 失败超过 5 点（或自然 1）：陷阱立即触发，伤害走既有管线
    damage = args.get("damage")
    if damage in (None, "", 0, "0"):
        return line + "失败超过 5 点，陷阱触发（未声明 damage，请按陷阱效果结算）"
    target = str(args.get("target") or "")
    if not target or not is_player_name(state, target):
        target = str(getattr(state, "character_name", "") or "玩家")
    detail = await _exec_save_damage({
        "targets": [target], "dc": _int_arg(args.get("dc"), dc), "damage": damage,
        "damage_type": str(args.get("damage_type") or ""),
        "ability": str(args.get("ability") or "dex"),
        "reason": f"{name}触发",
    }, state)
    return line + f"失败超过 5 点，陷阱触发！\n{detail}"


def _int_arg(value: Any, default: int) -> int:
    """模型常把数字写成字符串，这里统一兜底，避免整条工具调用崩掉。"""
    try:
        return int(float(value)) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in ("1", "true", "yes", "y", "是", "真")
