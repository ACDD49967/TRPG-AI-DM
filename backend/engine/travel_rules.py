"""旅行节奏与强行军：每天超过 8 小时的赶路要掷体质豁免，失败力竭 +1。

5e 的旅行规则里有两件纯粹由数值决定的事，此前都靠 DM 记：

- **强行军**：一天走超过 8 小时，之后每多 1 小时掷一次体质豁免
  （DC = 10 + 已经超出的第几个小时），失败力竭 +1；
- **节奏**：急行军被动察觉 −5，慢行可以尝试隐蔽行进。

计数按"游戏内日期 + 当天已旅行小时"记在 `character_info` 里，跨天自动清零，
所以分多次 `advance_time` 也不会把上限算漏。力竭本身的后果由 `exhaustion_effects` 负责。
"""
from __future__ import annotations

import random
from typing import Any

FORCED_MARCH_FREE_HOURS = 8
PACE_NOTES = {
    "fast": "急行军：被动察觉 −5",
    "slow": "慢行：可以尝试隐蔽行进",
}
TRAVEL_KEY = "_travel_today"


def forced_march_dc(hour_index: int) -> int:
    """第 hour_index 小时（1 起算）的强行军 DC：10 + 超出的小时数。"""
    extra = max(1, int(hour_index) - FORCED_MARCH_FREE_HOURS)
    return 10 + extra - 1


def _today(state: Any) -> int:
    ws = getattr(state, "world_state", None)
    scene = getattr(ws, "scene", None)
    try:
        return int(getattr(scene, "day_count", 1) or 1)
    except (TypeError, ValueError):
        return 1


def _load(state: Any) -> dict:
    info = getattr(state, "character_info", {}) or {}
    entry = info.get(TRAVEL_KEY)
    if not isinstance(entry, dict) or int(entry.get("day") or 0) != _today(state):
        entry = {"day": _today(state), "hours": 0}
        info[TRAVEL_KEY] = entry
    return entry


async def apply_travel(state: Any, hours: float, pace: str = "") -> list[str]:
    """登记本次旅行时长并结算强行军；返回要追加到时间摘要里的说明。"""
    notes: list[str] = []
    pace = str(pace or "").strip().lower()
    if pace in PACE_NOTES:
        notes.append(PACE_NOTES[pace])
    try:
        spent = int(round(float(hours or 0)))
    except (TypeError, ValueError):
        spent = 0
    if spent <= 0:
        return notes

    entry = _load(state)
    before = int(entry.get("hours") or 0)
    after = before + spent
    entry["hours"] = after

    from backend.engine.character_state import _exec_update_state
    from backend.engine.player_damage import save_modifier

    for hour_index in range(before + 1, after + 1):
        if hour_index <= FORCED_MARCH_FREE_HOURS:
            continue
        dc = forced_march_dc(hour_index)
        mod, _source = save_modifier(state, "con")
        roll = random.randint(1, 20)
        success = roll == 20 or (roll != 1 and roll + mod >= dc)
        if success:
            notes.append(f"强行军第 {hour_index} 小时：DC{dc} 体质豁免 d20={roll} → 成功")
            continue
        await _exec_update_state(
            {"changes": {"exhaustion": 1}, "reason": f"强行军第 {hour_index} 小时"},
            state)
        level = int(state.character_info.get("exhaustion", 0) or 0)
        notes.append(f"⚠ 强行军第 {hour_index} 小时：DC{dc} 体质豁免 d20={roll} → 失败，"
                     f"力竭 +1（现 {level} 级）")
    return notes
