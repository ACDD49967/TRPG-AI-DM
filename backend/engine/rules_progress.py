"""经验/等级/起始金币：XP 阈值表、等级换算、进度条与起始金币。

从 backend.engine.game_systems 拆出。
"""
from __future__ import annotations

import random
import re
from typing import Any



# D&D 5e 官方升级经验阈值（累计 XP：达到该值即进入对应等级）
DND5_XP_THRESHOLDS = [
    0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
    85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000,
    305000, 355000,
]


# D&D 4e 升级经验阈值（累计 XP）
DND4_XP_THRESHOLDS = [
    0, 1000, 2250, 3750, 5500, 7500, 10000, 13000, 16500, 20500,
    26000, 32000, 39000, 47000, 57000, 69000, 83000, 99000, 119000,
    143000, 175000, 210000, 255000, 310000, 375000, 450000, 550000,
    675000, 825000, 1000000,
]



def get_xp_table(system: str) -> list[int]:
    """返回对应规则系统的官方升级经验表；未知系统返回空表。"""
    if system == "dnd5e":
        return DND5_XP_THRESHOLDS
    if system == "dnd4e":
        return DND4_XP_THRESHOLDS
    return []



def get_level_from_xp(xp: int, system: str = "dnd5e") -> int:
    """根据累计 XP 计算当前等级（1 起始，20/30 封顶）。"""
    table = get_xp_table(system)
    if not table:
        return max(1, int(xp or 0) // 1000 + 1)
    level = 1
    for i, threshold in enumerate(table, start=1):
        if xp >= threshold:
            level = i
        else:
            break
    return level



def get_xp_progress(xp: int, system: str = "dnd5e", level: int | None = None) -> dict | None:
    """返回经验进度信息：当前等级、下一级所需累计 XP、还差多少。"""
    table = get_xp_table(system)
    if not table:
        return None
    if level is None:
        level = get_level_from_xp(xp, system)
    if level >= len(table):
        return {"level": level, "current_xp": int(xp or 0), "next_xp": None, "needed": 0}
    next_xp = table[level]
    return {
        "level": level,
        "current_xp": int(xp or 0),
        "next_xp": next_xp,
        "needed": max(0, next_xp - int(xp or 0)),
    }



DND5_STARTING_GOLD = {
    "战士": 100, "圣武士": 100, "游侠": 100, "野蛮人": 50,
    "武僧": 10, "游荡者": 100, "吟游诗人": 100, "牧师": 50,
    "德鲁伊": 10, "邪术师": 100, "法师": 50, "术士": 50,
}



def get_starting_gold(game_system: str, char_class: str = "战士") -> int:
    """返回新角色的起始金币；优先按职业/规则系统给出合理值，而不是固定 10。"""
    if game_system == "dnd5e":
        return DND5_STARTING_GOLD.get(char_class, 50)
    if game_system == "dnd4e":
        return 100
    if game_system == "coc":
        return 0  # COC 用信用评级而非金币，前端不应显示金币
    return 50
