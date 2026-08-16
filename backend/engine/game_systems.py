"""游戏规则系统定义——D&D 5e / D&D 4e / COC 7e / 自定义。

这些配置是固定的程序化数据，避免每次让 LLM 重新推断规则，从而降低 token 消耗。
"""

from __future__ import annotations

import re


SYSTEM_TYPES = {
    "dnd5e": {
        "id": "dnd5e",
        "label": "D&D 5e",
        "short_label": "DND5e",
        "attributes": ["str", "dex", "con", "int", "wis", "cha"],
        "derived": ["HP", "AC", "熟练加值", "法术位"],
        "description": "第五版龙与地下城：d20 检定、优势/劣势、法术位、死亡豁免。",
    },
    "dnd4e": {
        "id": "dnd4e",
        "label": "D&D 4e",
        "short_label": "DND4e",
        "attributes": ["str", "con", "dex", "int", "wis", "cha"],
        "derived": ["HP", "治愈力/回复力", "AC/强韧/反射/意志", "威能（随意/遭遇/每日）"],
        "description": "第四版龙与地下城：d20 对防御、HP/血涌、威能系统、四类防御。",
    },
    "coc": {
        "id": "coc",
        "label": "克苏鲁的呼唤 7e",
        "short_label": "COC7e",
        "attributes": ["str", "con", "dex", "int", "pow", "cha", "siz", "edu"],
        "derived": ["HP", "MP", "理智(SAN)", "幸运(LUCK)"],
        "description": "克苏鲁的呼唤 7e：d100 百分比检定、理智、魔法、幸运、调查员。",
    },
    "custom": {
        "id": "custom",
        "label": "自定义 / 其他",
        "short_label": "CUSTOM",
        "attributes": ["str", "dex", "con", "int", "wis", "cha"],
        "derived": ["由玩家自定义"],
        "description": "自定义剧本与规则：由玩家提供规则文本，AI DM 按自定义规则主持。",
    },
}


def get_system(system_id: str | None) -> dict:
    """返回规则系统配置，未知时回退到 dnd5e。"""
    if system_id in SYSTEM_TYPES:
        return SYSTEM_TYPES[system_id]
    return SYSTEM_TYPES["dnd5e"]


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


DND5_CLASS_HD = {
    "战士": 10, "圣武士": 10, "野蛮人": 12, "游侠": 10, "武僧": 8,
    "游荡者": 8, "吟游诗人": 8, "牧师": 8, "德鲁伊": 8, "邪术师": 8,
    "法师": 6, "术士": 6,
}


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


def get_dnd5_spell_slots(char_class: str, level: int) -> dict:
    """返回 D&D 5e 施法职业在指定等级的法术位数量（固定表，不用 LLM 计算）。"""
    level = max(1, min(20, level))
    if char_class == "邪术师":
        return {
            "pact_slots": _WARLOCK_SLOTS.get(level, 2),
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


def get_dnd5_derived(char_class: str, attributes: dict, level: int = 1) -> dict:
    """按 D&D 5e 常用公式计算 1 级及升级后的 HP（取生命骰平均值）。

    - 1级 HP = 生命骰最大值 + 体质调整值
    - 之后每级增加 = 生命骰平均值 + 体质调整值
    """
    con = int(attributes.get("con", 10) or 10)
    con_mod = (con - 10) // 2
    hd = DND5_CLASS_HD.get(char_class, 8)
    avg_hd = hd // 2 + 1
    max_hp = hd + con_mod + max(0, level - 1) * (avg_hd + con_mod)
    return {
        "max_hp": max_hp,
        "hp": max_hp,
        "hit_die": f"1d{hd}",
    }


def get_dnd4_derived(char_class: str, attributes: dict) -> dict:
    """按 D&D 4e 常用公式计算 HP / 回复力。

    - 1级 HP = 职业基础HP + 体质值
    - 每日回复力 = 职业基础回复力 + 体质调整值
    - 单次回复力治疗量 = 最大HP / 4（向下取整）
    """
    con = int(attributes.get("con", 10) or 10)
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


def get_coc_derived(attributes: dict, luck: int = 50) -> dict:
    """COC 7e 衍生值固定计算。"""
    con = int(attributes.get("con", 50) or 50)
    siz = int(attributes.get("siz", 50) or 50)
    pow_ = int(attributes.get("pow", 50) or 50)
    str_ = int(attributes.get("str", 50) or 50)
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
        "hp": max(1, (con + siz) // 2),
        "mp": pow_,
        "san": pow_ * 5,
        "luck": max(1, min(99, luck)),
        "damage_bonus": damage_bonus,
        "build": build,
    }


def detect_game_system(text: str, title: str = "") -> str:
    """自动识别剧本所属规则系统。

    优先使用固定关键词规则（零 token 消耗），无法识别时返回 custom。
    """
    haystack = f"{title}\n{text}".lower()

    # COC / 克苏鲁
    coc_keywords = [
        "克苏鲁", "call of cthulhu", "coc", "调查员", "理智值", "san值",
        "魔法值", "幸运值", "d100", "百分骰", "san check", "sanity",
    ]
    if any(k in haystack for k in coc_keywords):
        return "coc"

    # D&D 4e
    dnd4_keywords = [
        "dnd4", "d&d4", "d&d 4", "dd4", "4e", "四版", "第四版",
        "healing surge", "bloodied", "威能", "每日威能", "遭遇威能",
        "强韧", "反射", "意志防御", "回复力",
    ]
    if any(k in haystack for k in dnd4_keywords):
        return "dnd4e"

    # D&D 5e
    dnd5_keywords = [
        "dnd5", "d&d5", "d&d 5", "5e", "五版", "第五版", "d20",
        "熟练加值", "法术位", "优势", "劣势", "死亡豁免", "hit dice", "spell slot",
    ]
    if any(k in haystack for k in dnd5_keywords):
        return "dnd5e"

    # 明显的奇幻 D&D 风格但未指明版本：默认 5e，更贴近主流
    fantasy_keywords = ["地城", "龙与地下城", "dungeons", "dragons", "法师", "战士", "冒险者", "地下城"]
    if any(k in haystack for k in fantasy_keywords):
        return "dnd5e"

    return "custom"


def build_stat_glossary(system_id: str) -> str:
    """返回当前规则系统的数值语义说明，帮助 DM 理解每个数字代表什么。"""
    if system_id == "dnd5e":
        return """数值含义速查（D&D 5e）：
- 属性 8-20：10 为凡人平均；调整值=(属性-10)//2。
- HP：生命值；归 0 进入濒死并开始死亡豁免。
- AC：护甲等级；敌人攻击 d20+加值 ≥ AC 命中。
- 熟练加值：1-4级+2，5-8级+3，9-12级+4，13-16级+5，17-20级+6。
- 法术位：施法者每日可用法术次数；短休/长休按规则恢复。
- 技能熟练：在对应属性检定上额外加熟练加值。"""
    if system_id == "dnd4e":
        return """数值含义速查（D&D 4e）：
- 属性 8-20：10 为平均；调整值=(属性-10)//2。
- HP：生命值；降到一半以下进入“血竭(Bloodied)”，归 0 进入濒死。
- 回复力(Healing Surge)：每日可用次数；每次使用恢复 1/4 最大 HP。
- AC/强韧/反射/意志：四种防御；攻击 d20+加值 vs 对应防御。
- 威能：随意(at-will)可无限用，遭遇(encounter)每场一次，每日(daily)每日一次。"""
    if system_id == "coc":
        return """数值含义速查（COC 7e）：
- 属性为 1-99 百分比：50 为普通人水平，越高越好。
- HP=(CON+SIZ)//2；归 0 时重伤昏迷，可能死亡。
- MP=意志(POW)；施法消耗魔法值。
- SAN=意志(POW)×5；遭遇神话损失理智，归 0 永久疯狂。
- LUCK=幸运值；可用于重掷或改变处境，由守密人酌情消耗。
- 技能检定：d100 ≤ 技能值=成功；≤技能值/2=困难成功；≤技能值/5=极限成功。"""
    return """数值含义速查（自定义）：
- 属性代表角色在该维度上的基础能力；数值越高通常越有利。
- 具体计算规则以玩家提供的自定义规则文本为准。"""


def build_system_rule_block(system_id: str, custom_rules: str = "") -> str:
    """返回追加到系统提示中的固定规则块。

    对 dnd5e 不需要覆盖，因为主 SYSTEM_PROMPT 已经是完整 5e 规则；
    对其他系统提供精简但可执行的规则覆盖。
    """
    general_numeric_rule = """
===============================================================================
数值权威规则（所有规则系统通用，不可违反）
===============================================================================
- HP/MP/SAN/AC/防御/回复力/熟练加值/法术位等数值一律以角色信息中的程序计算结果为准。
- 技能检定、攻击、伤害、死亡豁免等判定结果必须通过 dice_roll / combat_round / death_saving_throw 工具计算并返回。
- 你不得在叙事中自行编造最终数值；工具返回的数值才是权威。
- 需要修改 HP/金币/物品/理智等状态时，必须调用 update_state，由程序计算并更新。
"""
    if system_id == "dnd5e":
        return general_numeric_rule + "本局使用 D&D 5e 规则。请严格遵循上方 SYSTEM_PROMPT 中的全部 5e 规则。"

    if system_id == "dnd4e":
        return general_numeric_rule + """
===============================================================================
本局规则：D&D 4e（覆盖上方所有与 4e 冲突的规则）
===============================================================================
1. 属性：力量(STR)、体质(CON)、敏捷(DEX)、智力(INT)、感知(WIS)、魅力(CHA)。调整值=(属性-10)//2。
2. 防御：AC、强韧(Fortitude)、反射(Reflex)、意志(Will)。攻击检定 d20+调整值+1/2等级+武器加值 vs 对应防御。
3. 生命：HP 由职业与体质决定；角色降至 0 HP 时进入濒死，不再有负 HP；每回合 d20>=10 死亡豁免，3 成功稳定，3 失败死亡。
4. 回复力（Healing Surge）：短休或使用医疗威能时消耗回复力恢复 HP；每场冒险回复力有限。
5. 威能：角色拥有随意威能(at-will)、遭遇威能(encounter)、每日威能(daily)。遭遇威能每次遭遇一次，每日威能每日一次。
6. 血竭(Bloodied)：HP 降到一半以下时进入“血竭”状态，部分威能与怪物特性会触发。
7. 技能检定仍使用 d20，但难度按 DC 或对防御值判定。
8. 没有 5e 的法术位/专注/优势劣势体系；使用威能次数管理。
"""

    if system_id == "coc":
        return general_numeric_rule + """
===============================================================================
本局规则：克苏鲁的呼唤 7e（覆盖上方所有与 COC 冲突的规则）
===============================================================================
1. 角色是普通调查员，不是英雄。战斗致命、调查优先。
2. 属性：力量(STR)、体质(CON)、敏捷(DEX)、智力(INT)、意志(POW)、魅力(CHA)、体型(SIZ)、教育(EDU)。基础值通常为 3d6×5 或 2d6+6×5 等，最终是 1-99 的百分比。
3. 衍生：HP=(CON+SIZ)//2，MP=POW，SAN=POW×5，幸运(LUCK)初始约 3d6×5。
4. 技能检定：d100 百分比，掷骰 ≤ 技能值=成功；≤技能值/2=困难成功；≤技能值/5=极限成功；96-100 且 >技能值=大失败。
5. 理智(SAN)：遭遇神话时进行 SAN 检定，失败损失理智。SAN 降至 0 永久疯狂。
6. 战斗：使用格斗/射击等技能百分比进行 d100 攻击检定；伤害骰通常为 1d4/1d6/1d8/2d6 等；护甲很少，闪避也可作为回应。
7. 没有职业/种族/等级；使用职业与技能点构建调查员。
8. 魔法是禁忌且危险，通常消耗 MP 和 SAN。
"""

    # custom / other
    if custom_rules and custom_rules.strip():
        return general_numeric_rule + f"""
===============================================================================
本局规则：自定义 / 其他（玩家提供规则，覆盖上方所有冲突规则）
===============================================================================
{ custom_rules.strip()[:3000] }
"""

    return general_numeric_rule + """
===============================================================================
本局规则：自定义 / 其他（未提供详细规则）
===============================================================================
- 请根据玩家上传的剧本、备注和后续对话中的规则描述进行主持。
- 当玩家没有给出明确规则时，使用常识与剧本内部一致性推进，不强行套用 D&D 5e 或 COC 规则。
- 保持判定清晰：需要随机性时使用合适的骰子（d20/d100/其他）并在叙事中说明规则依据。
"""
