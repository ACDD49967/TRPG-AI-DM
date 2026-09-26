"""伤害类型：规范名归一、文本推断与武器名映射。

从 `damage_rules` 拆出（那边只留抗性/免疫/易伤的文本解析与伤害倍率）。
本模块同时提供 `_collect_text`——它被倍率解析和豁免加值推导共用，
放在这里可以让那两个模块都只依赖本模块，避免互相 import。
"""
from __future__ import annotations

from typing import Any
DAMAGE_TYPES: dict[str, tuple[str, ...]] = {
    "火焰": ("fire", "火焰"),
    "冷冻": ("cold", "frost", "冷冻", "寒冷"),
    "闪电": ("lightning", "闪电"),
    "强酸": ("acid", "强酸", "酸液"),
    "毒素": ("poison", "毒素", "中毒"),
    "雷鸣": ("thunder", "雷鸣"),
    "光耀": ("radiant", "光耀"),
    "黯蚀": ("necrotic", "黯蚀", "暗蚀"),
    "心灵": ("psychic", "心灵"),
    "力场": ("force", "力场"),
    "钝击": ("bludgeoning", "钝击"),
    "穿刺": ("piercing", "穿刺"),
    "挥砍": ("slashing", "挥砍", "斩击"),
}

_TYPE_LOOKUP: dict[str, str] = {}
for _canonical, _aliases in DAMAGE_TYPES.items():
    for _alias in _aliases:
        _TYPE_LOOKUP[_alias.lower()] = _canonical


def canonical_damage_type(value: Any) -> str:
    """把任意写法的伤害类型归一成规范名；未知返回原字符串。"""
    text = str(value or "").strip()
    if not text:
        return ""
    return _TYPE_LOOKUP.get(text.lower(), text)


def infer_damage_type(text: Any) -> str:
    """从描述文本里推断伤害类型（取最先出现的一种）。

    卡面/特性常写成"弯刀 1d6 挥砍"或"咬击 1d4 穿刺 + 1d6 毒素"，
    没有显式 damage_type 时用它兜底，避免"有抗性也永远不生效"。
    """
    lowered = str(text or "").lower()
    if not lowered:
        return ""
    best_at = len(lowered) + 1
    best = ""
    for canonical, aliases in DAMAGE_TYPES.items():
        for alias in aliases:
            index = lowered.find(alias.lower())
            if 0 <= index < best_at:
                best_at, best = index, canonical
    return best


# 武器名 → 伤害类型（玩家攻击常用；命中即返回，未命中视为无类型）
_WEAPON_TYPES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("穿刺", ("匕首", "短剑", "细剑", "长矛", "矛", "戟", "三叉戟", "弓", "弩", "箭",
              "dagger", "rapier", "spear", "bow", "crossbow", "piercing")),
    ("挥砍", ("长剑", "巨剑", "大剑", "弯刀", "战斧", "斧", "镰刀", "剑",
              "scimitar", "longsword", "greatsword", "axe", "sword", "slashing")),
    ("钝击", ("战锤", "巨锤", "锤", "棍", "法杖", "铁拳", "徒手", "拳",
              "mace", "hammer", "club", "quarterstaff", "bludgeoning")),
)


def weapon_damage_type(name: Any) -> str:
    """从武器/动作描述推断物理伤害类型；推断不出返回空串（按无抗性处理）。"""
    text = str(name or "").lower()
    if not text:
        return ""
    for canonical, keywords in _WEAPON_TYPES:
        if any(keyword in text for keyword in keywords):
            return canonical
    return ""



def _collect_text(entity: Any, extra: str = "") -> str:
    """把卡面所有字符串字段拼成一段可搜索文本。"""
    parts: list[str] = [str(extra or "")]
    if isinstance(entity, str):
        # 直接传文本（图鉴描述、特性串）也要能扫到
        parts.append(entity)
    elif isinstance(entity, dict):
        for value in entity.values():
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, dict):
                parts.extend(str(v) for v in value.values() if isinstance(v, (str, int, float)))
            elif isinstance(value, (list, tuple)):
                parts.extend(str(v) for v in value)
    elif entity is not None:
        for field in ("name", "role", "notes", "appearance", "personality", "motivation",
                      "secret", "relation_to_plot", "description"):
            value = getattr(entity, field, "")
            if isinstance(value, str):
                parts.append(value)
        for field in ("traits", "equipment", "skills"):
            for value in getattr(entity, field, []) or []:
                parts.append(str(value))
        for value in (getattr(entity, "attributes", {}) or {}).values():
            parts.append(str(value))
    return " \n ".join(part for part in parts if part)
