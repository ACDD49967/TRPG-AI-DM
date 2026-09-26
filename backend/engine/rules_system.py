"""规则系统元信息：系统表、识别、风格指令与提示词规则块。

从 backend.engine.game_systems 拆出。
"""
from __future__ import annotations

import random
import re
from typing import Any



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
    """基于加权关键词评分自动识别剧本规则系统。

    使用分数而不是“先命中先返回”，避免“调查员/4e/d20”等弱关键词误判。
    """
    haystack = f"{title}\n{text}".lower()

    groups = {
        "coc": {
            "strong": [
                "克苏鲁", "call of cthulhu", "守秘人", "理智值", "san值",
                "神话生物", "百分骰", "sanity", "san check",
            ],
            "medium": ["调查员", "心理学", "幸运值", "魔法值", "coc"],
        },
        "dnd4e": {
            "strong": [
                "dnd4", "d&d4", "d&d 4", "dd4", "威能", "每日威能",
                "遭遇威能", "healing surge", "bloodied", "回复力",
            ],
            "medium": ["4e", "四版", "第四版", "强韧", "反射", "意志防御"],
        },
        "dnd5e": {
            "strong": [
                "dnd5", "d&d5", "d&d 5", "五版", "第五版", "法术位",
                "熟练加值", "死亡豁免", "hit dice", "spell slot",
            ],
            "medium": ["5e", "d20", "优势", "劣势", "地下城", "龙与地下城", "dungeons", "dragons"],
            "weak": ["法师", "战士", "冒险者", "地城"],
        },
    }

    scores = {"coc": 0, "dnd4e": 0, "dnd5e": 0}
    for system, levels in groups.items():
        for word in levels.get("strong", []):
            if word in haystack:
                scores[system] += 5 * haystack.count(word)
        for word in levels.get("medium", []):
            if word in haystack:
                scores[system] += 2 * haystack.count(word)
        for word in levels.get("weak", []):
            if word in haystack:
                scores[system] += 1 * haystack.count(word)

    best = max(scores, key=scores.get)
    if scores[best] <= 0:
        return "custom"
    # 最高分与其他系统接近时，保守返回 custom，避免误判
    second = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0
    if scores[best] - second < 3 and scores[best] < 8:
        return "custom"
    return best



def get_style_directive(system_id: str) -> str:
    """返回与世界背景相符的叙事文风指令，提升沉浸感与 DM 风范。"""
    if system_id == "coc":
        return """文风与沉浸要求（COC 守密人口吻）：
- 以克苏鲁式恐怖为底色：日常逐渐崩坏、未知令人不安、理智脆弱。
- 使用潮湿、陈旧、昏暗、霉味、远处的汽笛/钟声等感官细节。
- 不要急于抛出怪物；先营造“不对劲”的氛围。
- NPC 说话带时代感与地方感，不滥用现代网络用语。
- 你既是叙述者也是守密人：克制、冷静、带一点宿命感，不主动拯救调查员。"""
    if system_id == "dnd4e":
        return """文风与沉浸要求（D&D 4e DM 口吻）：
- 西幻史诗风格：英雄气概、古老帝国、战场荣光与魔法文明。
- 战斗描写强调“威能”的华丽与力量感，但保持具体物理细节。
- NPC 与地名带有中世纪/奇幻风味，避免现代词汇。
- 你是地下城主：公正、有戏剧张力，让玩家感到自己正身处剑与魔法的世界。"""
    if system_id == "custom":
        return """文风与沉浸要求（自定义世界）：
- 严格贴合玩家提供的自定义规则与世界设定。
- 若剧本包含明确风格（蒸汽朋克/末日废土/东方武侠等），优先使用该风格。
- 保持叙事内部一致，不混入 D&D/COC 的默认设定。"""
    return """文风与沉浸要求（D&D 5e DM 口吻）：
- 西幻史诗风格：酒馆、古堡、龙与地下城、英雄旅程。
- 使用具体感官细节和物理量，避免现代词汇与网络梗。
- 战斗描写兼具动作感与后果，NPC 有符合身份的说话方式。
- 你是地下城主：公正、有戏剧张力，让世界显得真实而危险。"""



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
- HP=(CON+SIZ)//10；归 0 时重伤昏迷，可能死亡。
- MP=意志(POW)//5；施法消耗魔法值。
- SAN=意志(POW)；遭遇神话损失理智，归 0 永久疯狂。
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
- 禁止在调用 dice_roll / combat_round 之前直接宣布成功、失败、伤害、属性改变或检定结果；必须先完成判定工具调用。
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
3. 衍生：HP=(CON+SIZ)//10，MP=POW//5，SAN=POW，幸运(LUCK)初始约 3d6×5。
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
判定骰以本局规则为准：规则规定用什么骰子（如 2d10、3d6）就必须用什么，
调用 dice_roll 时把骰式写进 dice 参数（例如 dice="2d10"），并按规则给目标值；
不要默认使用 d20。规则没写骰式时才用 d20。

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
