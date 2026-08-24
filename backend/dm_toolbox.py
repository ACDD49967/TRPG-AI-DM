"""DM 工具箱——固定程序工具，减少 LLM 自由发挥与 token 消耗。

包含：
- 掷骰解析
- NPC 名字生成
- NPC 怪癖生成
- 遭遇难度参考
- 财宝掉落参考
- 知识库检索
"""

from __future__ import annotations

import random
from typing import Any

from backend.knowledge_base import get_knowledge_base


def roll_dice(spec: str) -> int:
    """解析 '2d6+3' 并返回结果。"""
    import re
    m = re.match(r"(\d*)d(\d+)(?:\+(\d+))?", spec.strip().lower())
    if not m:
        return 0
    num = int(m.group(1) or 1)
    sides = int(m.group(2))
    bonus = int(m.group(3) or 0)
    return sum(random.randint(1, sides) for _ in range(num)) + bonus


_RACE_NAMES = {
    "人类": ["艾伦", "雷奥", "加雷特", "艾琳娜", "莉亚娜"],
    "精灵": ["艾拉希尔", "瑟兰迪尔", "艾尔雯", "伊瑟拉"],
    "矮人": ["索林", "巴林", "迪萨", "赫尔加"],
    "半身人": ["米洛", "芬恩", "贝拉", "黛西"],
    "龙裔": ["阿卡拉斯", "托瑞恩", "艾莎拉", "克丽丝"],
    "默认": ["阿莱克斯", "摩根", "凯", "瑞雯"],
}


def generate_name(race: str = "人类") -> str:
    names = _RACE_NAMES.get(race, _RACE_NAMES["默认"])
    first = random.choice(names)
    last = random.choice(["风行者", "铁冠", "暗河", "石拳", "灰烬", "晨星"])
    return f"{first}·{last}"


_QUIRKS = [
    "说话前会先闻一下空气",
    "总是在口袋里拨弄一枚旧硬币",
    "紧张时会用指节敲桌子",
    "拒绝直视他人眼睛",
    "随身带着一本写满无人能懂符号的笔记",
    "对猫/狗/乌鸦异常亲近",
]


def npc_quirk() -> str:
    return random.choice(_QUIRKS)


# 简化遭遇难度表（5e 近似）
_ENCOUNTER_XP = {
    "easy": 0.25,
    "medium": 0.5,
    "hard": 0.75,
    "deadly": 1.0,
}


def encounter_guide(party_level: int, party_size: int, difficulty: str = "medium") -> dict:
    """返回一个粗略的遭遇预算参考。"""
    level_xp = {
        1: 50, 2: 100, 3: 150, 4: 250, 5: 500, 6: 600, 7: 750,
        8: 900, 9: 1100, 10: 1200, 11: 1600, 12: 2000, 13: 2200,
        14: 2500, 15: 2800, 16: 3200, 17: 3900, 18: 4200, 19: 4900, 20: 5700,
    }
    per = level_xp.get(party_level, 1000) * _ENCOUNTER_XP.get(difficulty, 0.5)
    return {
        "party_level": party_level,
        "party_size": party_size,
        "difficulty": difficulty,
        "xp_budget": int(per * party_size),
        "suggestion": "建议使用 1-3 个同 CR 怪物，或 1 个高 CR 首领 + 若干杂兵。",
    }


# 简化财宝表（5e 近似）
_TREASURE = {
    "low": ["1d6×10 金币", "1d4 宝石（10金币）", "普通药剂"],
    "medium": ["2d6×100 金币", "1d4 宝石（50金币）", "+1 武器或护甲"],
    "high": ["3d6×1000 金币", "1d4 宝石（500金币）", "+2 武器或护甲", "卷轴/法术书"],
}


def roll_treasure(cr: int) -> list[str]:
    if cr < 5:
        table = _TREASURE["low"]
    elif cr < 11:
        table = _TREASURE["medium"]
    else:
        table = _TREASURE["high"]
    count = random.randint(1, 3)
    return random.sample(table, min(count, len(table)))


def search_knowledge(query: str, system: str | None = None, top_k: int = 3,
                     username: str | None = None) -> list[dict]:
    return get_knowledge_base().retrieve(query, system=system, top_k=top_k, username=username)
