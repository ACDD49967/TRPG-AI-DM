"""补给与力竭：口粮/饮水/照明的消耗记账，力竭等级与效果提示。

从 `backend/engine/time_rules.py` 拆出；物品查找走 `character_normalize._normalize_item` 的字段约定。
"""
from __future__ import annotations

from typing import Any, Iterable

from backend.engine.time_clock import MAX_EXHAUSTION


EXHAUSTION_EFFECTS = {
    1: "属性检定具有劣势",
    2: "移动速度减半",
    3: "攻击检定与豁免具有劣势",
    4: "生命值上限减半",
    5: "移动速度降为 0",
    6: "死亡",
}

RATIONS_KEYWORDS = ("口粮", "干粮", "rations", "旅行干粮", "干肉")
WATER_KEYWORDS = ("水袋", "水囊", "清水", "饮水", "water")
LIGHT_KEYWORDS = ("火把", "灯油", "提灯", "油灯", "蜡烛", "torch", "lantern")


def _items(state: Any) -> list:
    inventory = (getattr(state, "character_info", {}) or {}).get("inventory")
    if isinstance(inventory, dict):
        return inventory.setdefault("items", [])
    if isinstance(inventory, list):
        return inventory
    info = getattr(state, "character_info", {})
    info["inventory"] = {"items": []}
    return info["inventory"]["items"]


def _consume_item(state: Any, keywords: Iterable[str], count: int = 1) -> str:
    """按关键词消耗物品（数量 -1，归零移除）。返回被消耗的物品名，没有则空串。"""
    remaining = max(1, int(count))
    consumed = ""
    items = _items(state)
    for item in list(items):
        if remaining <= 0:
            break
        name = item.get("name") if isinstance(item, dict) else str(item)
        if not any(keyword.lower() in str(name).lower() for keyword in keywords):
            continue
        if not isinstance(item, dict):
            existing = items[items.index(name)]
            item = {"name": str(name)}
            items[items.index(existing)] = item
        quantity = int(item.get("quantity", 1) or 1)
        take = min(quantity, remaining)
        quantity -= take
        remaining -= take
        consumed = consumed or str(name)
        if quantity <= 0:
            items.remove(item)
        else:
            item["quantity"] = quantity
    return consumed


def _has_item(state: Any, keywords: Iterable[str]) -> bool:
    for item in _items(state):
        name = item.get("name") if isinstance(item, dict) else str(item)
        if any(keyword.lower() in str(name).lower() for keyword in keywords):
            return True
    return False


def exhaustion_level(state: Any) -> int:
    try:
        return max(0, min(MAX_EXHAUSTION, int((getattr(state, "character_info", {}) or {}).get("exhaustion", 0) or 0)))
    except (TypeError, ValueError):
        return 0


def _item_qty_left(state: Any, name: str) -> int:
    """仅供测试/诊断：查背包里某个物品的剩余数量。"""
    for item in _items(state):
        item_name = item.get("name") if isinstance(item, dict) else str(item)
        if str(item_name) == str(name):
            return int(item.get("quantity", 1) or 1) if isinstance(item, dict) else 1
    return 0


async def _set_exhaustion(state: Any, level: int, reason: str) -> int:
    from backend.engine.character_state import _exec_update_state

    logger_level = max(0, min(MAX_EXHAUSTION, int(level)))
    current = exhaustion_level(state)
    if logger_level == current:
        return current
    await _exec_update_state(
        {"changes": {"exhaustion": logger_level - current}, "reason": reason}, state)
    return logger_level


def exhaustion_note(level: int) -> str:
    effect = EXHAUSTION_EFFECTS.get(int(level or 0))
    return f"力竭 {level} 级（{effect}）" if effect else ""


async def _consume_daily_supplies(state: Any, days: int) -> list[str]:
    """跨天补给结算：口粮/水各 1 份；缺哪样就提醒并累积力竭。"""
    notes: list[str] = []
    for _ in range(max(1, int(days))):
        ate = _consume_item(state, RATIONS_KEYWORDS)
        drank = _consume_item(state, WATER_KEYWORDS)
        if ate:
            notes.append(f"消耗 1 份口粮（{ate}）")
        if drank:
            notes.append(f"消耗 1 份饮水（{drank}）")
        missing = []
        if not ate:
            missing.append("口粮")
        if not drank:
            missing.append("饮水")
        if missing:
            level = await _set_exhaustion(
                state, exhaustion_level(state) + 1, f"缺少{'与'.join(missing)}")
            notes.append(f"⚠ 没有{'与'.join(missing)}：力竭 +1 → {exhaustion_note(level)}")
    return notes
