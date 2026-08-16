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


def build_system_rule_block(system_id: str, custom_rules: str = "") -> str:
    """返回追加到系统提示中的固定规则块。

    对 dnd5e 不需要覆盖，因为主 SYSTEM_PROMPT 已经是完整 5e 规则；
    对其他系统提供精简但可执行的规则覆盖。
    """
    if system_id == "dnd5e":
        return "本局使用 D&D 5e 规则。请严格遵循上方 SYSTEM_PROMPT 中的全部 5e 规则。"

    if system_id == "dnd4e":
        return """
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
        return """
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
        return f"""
===============================================================================
本局规则：自定义 / 其他（玩家提供规则，覆盖上方所有冲突规则）
===============================================================================
{ custom_rules.strip()[:3000] }
"""

    return """
===============================================================================
本局规则：自定义 / 其他（未提供详细规则）
===============================================================================
- 请根据玩家上传的剧本、备注和后续对话中的规则描述进行主持。
- 当玩家没有给出明确规则时，使用常识与剧本内部一致性推进，不强行套用 D&D 5e 或 COC 规则。
- 保持判定清晰：需要随机性时使用合适的骰子（d20/d100/其他）并在叙事中说明规则依据。
"""
