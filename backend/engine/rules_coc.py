"""COC 7e 规则数据与派生值：属性掷骰、幸运、派生值。

从 backend.engine.game_systems 拆出。
"""
from __future__ import annotations

import random
import re
from typing import Any



def roll_coc_characteristics() -> dict:
    """COC 7e 官方随机属性：3d6×5 与 (2d6+6)×5。"""
    def d3():
        return sum(random.randint(1, 6) for _ in range(3)) * 5
    def d2_plus_6():
        return (sum(random.randint(1, 6) for _ in range(2)) + 6) * 5
    return {
        "str": d3(),
        "con": d3(),
        "dex": d3(),
        "int": d3(),
        "pow": d3(),
        "cha": d3(),
        "siz": d2_plus_6(),
        "edu": d2_plus_6(),
    }



def roll_coc_luck() -> int:
    """COC 7e 幸运：3d6×5。"""
    return sum(random.randint(1, 6) for _ in range(3)) * 5



def get_coc_derived(attributes: dict, luck: int = 50) -> dict:
    """COC 7e 衍生值固定计算。"""
    con = max(1, min(99, int(attributes.get("con", 50) or 50)))
    siz = max(1, min(99, int(attributes.get("siz", 50) or 50)))
    pow_ = max(1, min(99, int(attributes.get("pow", 50) or 50)))
    str_ = max(1, min(99, int(attributes.get("str", 50) or 50)))
    total = str_ + siz

    if total <= 64:
        damage_bonus, build = "-2", -2
    elif total <= 84:
        damage_bonus, build = "-1", -1
    elif total <= 124:
        damage_bonus, build = "0", 0
    elif total <= 164:
        damage_bonus, build = "+1d4", 1
    elif total <= 204:
        damage_bonus, build = "+1d6", 2
    elif total <= 284:
        damage_bonus, build = "+2d6", 3
    else:
        damage_bonus, build = "+3d6", 4

    return {
        # COC 7e 官方公式：属性已是百分制（3D6×5 / (2D6+6)×5）
        "hp": max(1, (con + siz) // 10),
        "mp": max(1, pow_ // 5),
        "san": max(0, min(99, pow_)),
        "luck": max(1, min(99, luck)),
        "damage_bonus": damage_bonus,
        "build": build,
    }
