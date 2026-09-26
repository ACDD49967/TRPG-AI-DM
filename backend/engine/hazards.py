"""环境危害：坠落、严寒酷暑、窒息。

这些是"看一眼规则就能算出结果"的确定性结算，此前全靠 DM 估：伤害多少、要不要豁免、
失败什么后果。这里交给后端：DM 只需要说明发生了什么（"她从三层楼高的窗台摔下去"），
数值与豁免由工具给出。

范围说明：
- 坠落按 5e「每 10 尺 1d6、上限 20d6」；
- 严寒酷暑按 XGE 的逐小时体质豁免（DC = 5 + 已经忍受的小时数），失败力竭 +1
  （力竭本身的机械后果由 `exhaustion_effects` 负责）；
- 窒息只做"超过忍耐时间"的那一步（HP 归 0 进入濒死）——本项目的战斗是按回合推进的，
  不逐轮记账呼吸，逐轮留在叙事里由 DM 描述更自然。
"""
from __future__ import annotations

import random
from typing import Any

from backend.engine.session import GameSessionState, push_event

FALLING_PER_DICE_FT = 10
FALLING_MAX_DICE = 20
_ENVIRONMENT_LABELS = {
    "extreme_heat": ("酷暑", "高温"),
    "extreme_cold": ("严寒", "低温"),
}


def falling_damage_dice(distance_ft: Any) -> int:
    """坠落伤害骰数：每 10 尺 1d6，上限 20d6。"""
    try:
        feet = max(0.0, float(distance_ft or 0))
    except (TypeError, ValueError):
        feet = 0.0
    return max(1, min(FALLING_MAX_DICE, int(feet // FALLING_PER_DICE_FT) or 1))


def environment_save_dc(hours: Any) -> int:
    """严寒/酷暑的体质豁免 DC：5 + 已经忍受的小时数（第 1 小时为 5）。"""
    try:
        spent = max(1, int(hours or 1))
    except (TypeError, ValueError):
        spent = 1
    return 5 + (spent - 1)


async def _exec_apply_hazard(args: dict, state: GameSessionState) -> str:
    kind = str(args.get("kind") or "").strip().lower()
    if kind == "falling":
        return await _falling(args, state)
    if kind in _ENVIRONMENT_LABELS:
        return await _environment(kind, args, state)
    if kind == "suffocation":
        return await _suffocation(state)
    return ("⚠ apply_hazard 需要 kind：falling（坠落）/ extreme_heat（酷暑）/ "
            "extreme_cold（严寒）/ suffocation（窒息）")


async def _falling(args: dict, state: GameSessionState) -> str:
    from backend.engine import player_damage

    dice = falling_damage_dice(args.get("distance_ft"))
    rolls = [random.randint(1, 6) for _ in range(dice)]
    damage = sum(rolls)
    outcome = await player_damage.apply(
        state, damage, damage_type="钝击",
        reason=f"坠落 {int(float(args.get('distance_ft') or 10))} 尺", source="坠落")
    detail = f"dice={dice}d6={damage}"
    await push_event(state, "dice_roll", {
        "skill": f"坠落伤害（{dice}d6）", "dc": 0, "roll": damage, "modifier": 0,
        "result": "伤害", "formula": f"{dice}d6={damage}",
        "display": f"坠落：{detail} → 扣血 {outcome['hp_damage']}",
    })
    line = (f"🪂 坠落 {int(float(args.get('distance_ft') or 10))} 尺：{detail}，"
            f"扣血 {outcome['hp_damage']}（HP {outcome['hp_before']}→{outcome['hp_after']}）")
    if outcome["note"]:
        line += f" [{outcome['note']}]"
    return line


async def _environment(kind: str, args: dict, state: GameSessionState) -> str:
    from backend.engine import player_damage
    from backend.engine.character_state import _exec_update_state

    hours = args.get("hours") or 1
    dc = environment_save_dc(hours)
    mod, source = player_damage.save_modifier(state, "con")
    roll = random.randint(1, 20)
    total = roll + mod
    success = roll == 20 or (roll != 1 and total >= dc)
    await push_event(state, "dice_roll", {
        "skill": f"{_ENVIRONMENT_LABELS[kind][0]}·体质豁免", "dc": dc,
        "roll": roll, "modifier": mod, "source": source,
        "result": "成功" if success else "失败",
    })
    label = _ENVIRONMENT_LABELS[kind][0]
    line = f"🌡️ {label}（第 {hours} 小时）：DC{dc} 体质豁免 d20={roll} → {'成功' if success else '失败'}"
    if not success:
        await _exec_update_state(
            {"changes": {"exhaustion": 1}, "reason": f"{label}中坚持 {hours} 小时"}, state)
        level = int(state.character_info.get("exhaustion", 0) or 0)
        line += f"，力竭 +1 → 力竭 {level} 级"
    return line


async def _suffocation(state: GameSessionState) -> str:
    from backend.engine.character_state import _exec_update_state

    current = int(state.character_info.get("hp", 0) or 0)
    if current <= 0:
        return "⚠ 角色已经倒地（HP 0），无需再结算窒息"
    await _exec_update_state(
        {"changes": {"hp": -current}, "reason": "窒息超过忍耐时间"}, state)
    return ("🫁 窒息超过忍耐时间：HP 归 0，进入濒死（接下来每回合掷死亡豁免，"
            "旁人可施救）")
