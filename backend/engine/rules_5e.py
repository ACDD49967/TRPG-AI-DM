"""D&D 5e 规则数据与派生值：生命骰、豁免、法术位、职业资源、属性提升等级。

从 backend.engine.game_systems 拆出。
"""
from __future__ import annotations

import random
import re
from typing import Any



DND5_CLASS_HD = {
    "战士": 10, "圣武士": 10, "野蛮人": 12, "游侠": 10, "武僧": 8,
    "游荡者": 8, "吟游诗人": 8, "牧师": 8, "德鲁伊": 8, "邪术师": 8,
    "法师": 6, "术士": 6,
}


# D&D 5e 属性提升（ASI，可改为选一项专长）的等级。
# 此前本项目写成"每 2 级送专长"，2 级就给专长会明显超模；
# 官方：大多职业 4/8/12/16/19，战士额外 6/14，游荡者额外 10。
DND5_ASI_DEFAULT = [4, 8, 12, 16, 19]

DND5_ASI_BY_CLASS = {
    "战士": [4, 6, 8, 12, 14, 16, 19],
    "游荡者": [4, 8, 10, 12, 16, 19],
}



def get_dnd5_asi_levels(char_class: str) -> list[int]:
    """返回该职业获得属性提升/专长的等级列表。"""
    return list(DND5_ASI_BY_CLASS.get(str(char_class or ""), DND5_ASI_DEFAULT))



def get_dnd5_proficiency_bonus(level: int) -> int:
    """D&D 5e 熟练加值表。"""
    if level <= 4:
        return 2
    if level <= 8:
        return 3
    if level <= 12:
        return 4
    if level <= 16:
        return 5
    return 6



DND5_CLASS_SAVES = {
    "战士": ("str", "con"), "圣武士": ("wis", "cha"), "野蛮人": ("str", "con"),
    "游侠": ("str", "dex"), "武僧": ("str", "dex"), "游荡者": ("dex", "int"),
    "吟游诗人": ("dex", "cha"), "牧师": ("wis", "cha"), "德鲁伊": ("int", "wis"),
    "邪术师": ("wis", "cha"), "法师": ("int", "wis"), "术士": ("con", "cha"),
}



def get_dnd5_saves(char_class: str, attributes: dict, prof_bonus: int) -> dict:
    """D&D 5e 豁免：基础属性调整 + 职业熟练豁免。"""
    keys = ["str", "dex", "con", "int", "wis", "cha"]
    proficient = set(DND5_CLASS_SAVES.get(char_class, ()))
    out = {}
    for k in keys:
        v = int(attributes.get(k, 10) or 10)
        mod = (v - 10) // 2
        out[k] = {"value": mod + prof_bonus if k in proficient else mod, "proficient": k in proficient}
    return out



def get_passive_perception(attributes: dict, prof_bonus: int, skill_proficiencies: list[str]) -> int:
    """D&D 5e 被动感知：10 + 感知调整 + (察觉熟练时熟练加值)。"""
    wis = int(attributes.get("wis", 10) or 10)
    wis_mod = (wis - 10) // 2
    proficient = any("察觉" in s for s in (skill_proficiencies or []))
    return 10 + wis_mod + (prof_bonus if proficient else 0)



# 法术位表：仅包含本项目职业列表中的施法职业（官方 5e 表）
_FULL_CASTER_SLOTS = {
    1: (2, 0, 0, 0, 0), 2: (3, 0, 0, 0, 0), 3: (4, 2, 0, 0, 0),
    4: (4, 3, 0, 0, 0), 5: (4, 3, 2, 0, 0), 6: (4, 3, 3, 0, 0),
    7: (4, 3, 3, 1, 0), 8: (4, 3, 3, 2, 0), 9: (4, 3, 3, 3, 1),
    10: (4, 3, 3, 3, 2), 11: (4, 3, 3, 3, 2, 1), 12: (4, 3, 3, 3, 2, 1),
    13: (4, 3, 3, 3, 2, 1, 1), 14: (4, 3, 3, 3, 2, 1, 1),
    15: (4, 3, 3, 3, 2, 1, 1, 1), 16: (4, 3, 3, 3, 2, 1, 1, 1),
    17: (4, 3, 3, 3, 2, 1, 1, 1, 1), 18: (4, 3, 3, 3, 3, 1, 1, 1, 1),
    19: (4, 3, 3, 3, 3, 2, 1, 1, 1), 20: (4, 3, 3, 3, 3, 2, 2, 1, 1),
}

_HALF_CASTER_SLOTS = {
    1: (0, 0, 0, 0, 0), 2: (2, 0, 0, 0, 0), 3: (3, 0, 0, 0, 0),
    4: (3, 0, 0, 0, 0), 5: (4, 2, 0, 0, 0), 6: (4, 2, 0, 0, 0),
    7: (4, 3, 0, 0, 0), 8: (4, 3, 0, 0, 0), 9: (4, 3, 2, 0, 0),
    10: (4, 3, 2, 0, 0), 11: (4, 3, 3, 0, 0), 12: (4, 3, 3, 0, 0),
    13: (4, 3, 3, 1, 0), 14: (4, 3, 3, 1, 0), 15: (4, 3, 3, 2, 0),
    16: (4, 3, 3, 2, 0), 17: (4, 3, 3, 3, 1), 18: (4, 3, 3, 3, 1),
    19: (4, 3, 3, 3, 2), 20: (4, 3, 3, 3, 2),
}

_WARLOCK_SLOTS = {  # 邪术师契约法术位数量
    1: 1, 2: 2, 3: 2, 4: 2, 5: 2, 6: 2, 7: 2, 8: 2, 9: 2, 10: 2,
    11: 3, 12: 3, 13: 3, 14: 3, 15: 3, 16: 3, 17: 4, 18: 4, 19: 4, 20: 4,
}

_WARLOCK_PACT_LEVEL = {  # 契约法术位环级
    1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3, 7: 4, 8: 4, 9: 5, 10: 5,
    11: 5, 12: 5, 13: 5, 14: 5, 15: 5, 16: 5, 17: 5, 18: 5, 19: 5, 20: 5,
}



def get_dnd5_spell_slots(char_class: str, level: int) -> dict:
    """返回 D&D 5e 施法职业在指定等级的法术位数量（固定表，不用 LLM 计算）。"""
    level = max(1, min(20, level))
    if char_class == "邪术师":
        return {
            "pact_slots": _WARLOCK_SLOTS.get(level, 2),
            "pact_slot_level": _WARLOCK_PACT_LEVEL.get(level, 1),
            "spell_slots": [],
        }
    if char_class in ("圣武士", "游侠"):
        table = _HALF_CASTER_SLOTS
    elif char_class in ("法师", "牧师", "吟游诗人", "德鲁伊", "术士"):
        table = _FULL_CASTER_SLOTS
    else:
        return {"spell_slots": [], "pact_slots": 0}
    slots = table.get(level, (0, 0, 0, 0, 0))
    return {
        "spell_slots": [int(x) for x in slots],
        "pact_slots": 0,
    }



DND5_RAGE_USES = {1: 2, 2: 2, 3: 3, 4: 3, 5: 3, 6: 4, 7: 4, 8: 4, 9: 4,
                  10: 4, 11: 4, 12: 5, 13: 5, 14: 5, 15: 5, 16: 5, 17: 6,
                  18: 6, 19: 6, 20: 6}

DND5_CHANNEL_DIVINITY = {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 2, 7: 2, 8: 2,
                         9: 2, 10: 2, 11: 2, 12: 2, 13: 2, 14: 2, 15: 2,
                         16: 2, 17: 2, 18: 3, 19: 3, 20: 3}






def get_dnd5_class_resources(char_class: str, attributes: dict, level: int = 1) -> list[dict]:
    """D&D 5e 职业专属资源（按职业分离，只返回该职业实际拥有的资源）。"""
    level = max(1, min(20, level))
    cha = int(attributes.get("cha", 10) or 10)
    resources = []
    if char_class == "术士":
        resources.append({"key": "sorcery_points", "name": "术法点", "current": level, "max": level, "desc": "用于超魔法术；长休恢复"})
    elif char_class == "武僧":
        resources.append({"key": "ki_points", "name": "气", "current": level, "max": level, "desc": "用于疾风连击等武僧能力；短休恢复"})
    elif char_class == "野蛮人":
        uses = DND5_RAGE_USES.get(level, 2)
        resources.append({"key": "rage", "name": "狂暴", "current": uses, "max": uses, "desc": "狂暴次数；长休恢复"})
    elif char_class == "吟游诗人":
        uses = max(1, (cha - 10) // 2)
        resources.append({"key": "bardic_inspiration", "name": "诗人激励", "current": uses, "max": uses, "desc": "诗人激励次数；长休恢复"})
    elif char_class == "圣武士":
        resources.append({"key": "lay_on_hands", "name": "圣疗", "current": level * 5, "max": level * 5, "desc": "圣疗点数；长休恢复"})
        if level >= 3:
            resources.append({"key": "channel_divinity", "name": "引导神力", "current": 1, "max": 1, "desc": "圣誓引导神力次数；短休或长休恢复"})
    elif char_class == "牧师":
        uses = DND5_CHANNEL_DIVINITY.get(level, 1)
        resources.append({"key": "channel_divinity", "name": "引导神力", "current": uses, "max": uses, "desc": "引导神力次数；短休或长休恢复"})
    elif char_class == "德鲁伊":
        resources.append({"key": "wild_shape", "name": "荒野形态", "current": 2, "max": 2, "desc": "荒野形态次数；短休或长休恢复"})
    elif char_class == "战士":
        resources.append({"key": "second_wind", "name": "回气", "current": 1, "max": 1, "desc": "附赠动作恢复 1d10+战士等级 HP；短休或长休恢复"})
        resources.append({"key": "action_surge", "name": "动作如潮", "current": 2 if level >= 17 else 1,
                          "max": 2 if level >= 17 else 1, "desc": "本回合额外获得一个动作；短休或长休恢复"})
    elif char_class == "法师":
        recovered = (level + 1) // 2
        resources.append({"key": "arcane_recovery", "name": "奥术回想", "current": recovered, "max": recovered,
                          "desc": "短休恢复合计不超过该值的法术位环级（每日一次）"})
    # 游荡者/游侠无固定次数资源：游侠有法术位，游荡者资源由叙事判定
    return resources



def get_dnd5_derived(char_class: str, attributes: dict, level: int = 1) -> dict:
    """按 D&D 5e 常用公式计算 1 级及升级后的 HP（取生命骰平均值）。

    - 1级 HP = 生命骰最大值 + 体质调整值
    - 之后每级增加 = 生命骰平均值 + 体质调整值
    """
    con = max(1, min(30, int(attributes.get("con", 10) or 10)))
    con_mod = (con - 10) // 2
    hd = DND5_CLASS_HD.get(char_class, 8)
    avg_hd = hd // 2 + 1
    max_hp = hd + con_mod + max(0, level - 1) * (avg_hd + con_mod)
    return {
        "max_hp": max_hp,
        "hp": max_hp,
        "hit_die": f"1d{hd}",
    }
