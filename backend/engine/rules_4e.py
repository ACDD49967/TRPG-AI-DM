"""D&D 4e 规则数据与派生值：职业 HP/回复力、四类防御、派生属性。

从 backend.engine.game_systems 拆出。
"""
from __future__ import annotations

import random
import re
from typing import Any



# D&D 4e 职业基础数据（近似 SRD/核心书常用值）
DND4_CLASS_HP = {
    "战士": 15, "圣武士": 15, "野蛮人": 15,
    "游侠": 12, "游荡者": 12, "牧师": 12, "邪术师": 12,
    "吟游诗人": 12, "德鲁伊": 12, "武僧": 12, "术士": 12,
    "法师": 10,
}

DND4_CLASS_SURGES = {
    "战士": 9, "圣武士": 9, "野蛮人": 9,
    "游侠": 6, "游荡者": 6, "牧师": 7, "邪术师": 6,
    "吟游诗人": 7, "德鲁伊": 7, "武僧": 7, "术士": 6,
    "法师": 6,
}



def get_dnd4_derived(char_class: str, attributes: dict) -> dict:
    """按 D&D 4e 常用公式计算 HP / 回复力。

    - 1级 HP = 职业基础HP + 体质值
    - 每日回复力 = 职业基础回复力 + 体质调整值
    - 单次回复力治疗量 = 最大HP / 4（向下取整）
    """
    con = max(1, min(30, int(attributes.get("con", 10) or 10)))
    con_mod = (con - 10) // 2
    base_hp = DND4_CLASS_HP.get(char_class, 12)
    base_surges = DND4_CLASS_SURGES.get(char_class, 6)
    max_hp = base_hp + con
    healing_surges = max(1, base_surges + con_mod)
    surge_value = max(1, max_hp // 4)
    return {
        "max_hp": max_hp,
        "hp": max_hp,
        "healing_surges": healing_surges,
        "max_healing_surges": healing_surges,
        "surge_value": surge_value,
    }



# D&D 4e 职业防御加值（近似核心书常用值）
DND4_DEFENSE_BONUS = {
    "战士": {"fort": 2, "ref": 0, "will": 0},
    "圣武士": {"fort": 1, "ref": 0, "will": 1},
    "野蛮人": {"fort": 2, "ref": 0, "will": 0},
    "游侠": {"fort": 0, "ref": 2, "will": 0},
    "游荡者": {"fort": 0, "ref": 2, "will": 0},
    "牧师": {"fort": 0, "ref": 0, "will": 2},
    "邪术师": {"fort": 0, "ref": 1, "will": 1},
    "吟游诗人": {"fort": 0, "ref": 0, "will": 2},
    "德鲁伊": {"fort": 1, "ref": 0, "will": 1},
    "武僧": {"fort": 0, "ref": 2, "will": 1},
    "术士": {"fort": 0, "ref": 1, "will": 1},
    "法师": {"fort": 0, "ref": 1, "will": 2},
}



def get_dnd4_defenses(char_class: str, attributes: dict, level: int = 1,
                      armor_bonus: int = 0, shield_bonus: int = 0) -> dict:
    """D&D 4e 四类防御固定计算。

    基础规则：10 + 1/2等级 + 对应属性调整 + 职业加值 + 护甲/盾牌等。
    AC 额外使用敏捷调整（中甲上限 +2，重甲不加重）。
    """
    half_level = level // 2
    attrs = {k: int(v or 10) for k, v in attributes.items()}
    dex_mod = (attrs.get("dex", 10) - 10) // 2
    str_mod = (attrs.get("str", 10) - 10) // 2
    con_mod = (attrs.get("con", 10) - 10) // 2
    int_mod = (attrs.get("int", 10) - 10) // 2
    wis_mod = (attrs.get("wis", 10) - 10) // 2
    cha_mod = (attrs.get("cha", 10) - 10) // 2
    bonus = DND4_DEFENSE_BONUS.get(char_class, {"fort": 0, "ref": 0, "will": 0})
    return {
        "ac": 10 + half_level + dex_mod + armor_bonus + shield_bonus,
        "fortitude": 10 + half_level + max(str_mod, con_mod) + bonus.get("fort", 0),
        "reflex": 10 + half_level + max(dex_mod, int_mod) + bonus.get("ref", 0),
        "will": 10 + half_level + max(wis_mod, cha_mod) + bonus.get("will", 0),
    }
