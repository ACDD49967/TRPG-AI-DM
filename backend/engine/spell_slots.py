"""法术位写回：把"剩余法术位"收敛到职业/等级的固定表上限。

法术位是一个少见的**完整剩余值**字段（不是增量），DM 的 `update_state`、导入的角色卡、
旧存档都能直接写数组。此前这条路径没有任何上限校验：

- 法术位可以越写越多——`{"spell_slots": [9, 9, 9]}` 会被原样接受，比手动改数值更像外挂；
- 3 级法师也能拿到 4 环位，而 `_exec_cast_spell` 只检查"够不够用"，不会检查"该不该有"。

按 `rules_5e` 的官方表封顶：只收敛**卡上已有**的条目，不补足、不按表长度截断
（恢复是长休的职责）；非 5e 局、以及不在表里的职业（如战士）原样返回，避免误伤自定义规则。
"""
from __future__ import annotations

from typing import Any

from backend.engine.rules_5e import get_dnd5_spell_slots
from backend.engine.tool_shims import _game_system


def _coerce_values(values: Any) -> list[int]:
    """把外部写进来的数组收敛成非负整数；坏值按 0 处理。"""
    if not isinstance(values, list):
        return []
    cleaned: list[int] = []
    for raw in values:
        try:
            cleaned.append(max(0, int(raw)))
        except (TypeError, ValueError):
            cleaned.append(0)
    return cleaned


def _clamp(state: Any, current: dict) -> dict:
    if _game_system(state) != "dnd5e":
        return current
    info = state.character_info
    limits = get_dnd5_spell_slots(
        str(info.get("char_class", "") or ""), int(info.get("level", 1) or 1))
    max_slots = list(limits.get("spell_slots") or [])
    slots = _coerce_values(current.get("spell_slots"))
    if max_slots:
        for index, value in enumerate(slots):
            cap = int(max_slots[index]) if index < len(max_slots) else 0
            slots[index] = min(value, cap)
        current["spell_slots"] = slots
    pact_cap = int(limits.get("pact_slots") or 0)
    if pact_cap:
        current["pact_slots"] = min(_coerce_values([current.get("pact_slots")])[0], pact_cap)
    return current


def apply_spell_slots_change(state: Any, current: Any, value: Any) -> dict:
    """合并一次法术位写回并封顶，返回要存进角色卡的结构。"""
    if not isinstance(current, dict):
        current = {"spell_slots": [], "pact_slots": 0}
    if isinstance(value, list):
        current["spell_slots"] = _coerce_values(value)
    elif isinstance(value, dict):
        if isinstance(value.get("spell_slots"), list):
            current["spell_slots"] = _coerce_values(value["spell_slots"])
        if value.get("pact_slots") is not None:
            current["pact_slots"] = _coerce_values([value["pact_slots"]])[0]
    return _clamp(state, current)


__all__ = ["apply_spell_slots_change"]
