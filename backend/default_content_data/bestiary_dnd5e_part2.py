"""内置bestiary数据：dnd5e 规则系统 第 2 部分（6 条：狗头人、巨魔、幽影、狮鹫、狼、巨鼠）。

从 `bestiary_dnd5e.py` 按原条目顺序切块：这里只搬数据，改怪物请改对应分片。
拼接与顺序由 `bestiary_dnd5e.py` 负责，`BESTIARY_DND5E` 的内容与顺序保持不变。
"""

BESTIARY_DND5E_PART2 = [
{
    "name": "狗头人",
    "system": "dnd5e",
    "description": "弱小但狡猾的爬虫类人生物，擅长陷阱与集群战术。",
    "stats": {
      "HP": "5",
      "AC": "12",
      "速度": "walk 30",
      "攻击": "匕首/投石索",
      "挑战等级": "1/8",
      "力量": "7",
      "敏捷": "15",
      "体质": "9",
      "智力": "8",
      "感知": "7",
      "魅力": "8",
      "技能": "察觉+2，潜行+3",
      "特性": "Sunlight Sensitivity: While in sunlight, the kobold has disadvantage on attack rolls, as well as on Wisdom (Perception) checks that rely on sight.；Pack Tactics: The kobold has advantage on an attack roll against a creature if at least one of the kobold's allies is within 5 ft. of the creature and the ally isn't incapacitated.",
      "动作": "Dagger: Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 4 (1d4+2) piercing damage.；Sling: Ranged Weapon Attack: +4 to hit, range 30/120 ft., one target. Hit: 4 (1d4+2) bludgeoning damage."
    },
    "tags": [
      "人形生物",
      "经典"
    ],
    "details": {
      "habits": "挖掘隧道、设陷阱、崇拜龙类。",
      "habitat": "矿洞、地下城",
      "lore": "狗头人相信自己是龙的后裔。",
      "weakness": "阳光敏感；单独作战时很脆弱。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Kobold",
      "source": "5etools-SRD"
    }
},
{
    "name": "巨魔",
    "system": "dnd5e",
    "description": "再生能力极强的丑陋巨兽，酸与火才能阻止其恢复。",
    "stats": {
      "HP": "84",
      "AC": "15 (natural armor)",
      "速度": "walk 30",
      "攻击": "啃咬/爪击",
      "挑战等级": "5",
      "力量": "18",
      "敏捷": "13",
      "体质": "20",
      "智力": "7",
      "感知": "9",
      "魅力": "7",
      "技能": "perception +2",
      "特性": "Keen Smell: The troll has advantage on Wisdom (Perception) checks that rely on smell.；Regeneration: The troll regains 10 hit points at the start of its turn. If the troll takes acid or fire damage, this trait doesn't function at the start of the troll's next turn. The troll dies only if it starts its turn with 0 hit points and doesn't regenerate.",
      "动作": "Multiattack: The troll makes three attacks: one with its bite and two with its claws.；Bite: Melee Weapon Attack: +7 to hit, reach 5 ft., one target. Hit: 7 (1d6+4) piercing damage.；Claw: Melee Weapon Attack: +7 to hit, reach 5 ft., one target. Hit: 11 (2d6+4) slashing damage."
    },
    "tags": [
      "巨人",
      "经典"
    ],
    "details": {
      "habits": "独居或小群，捕食一切能抓住的生物。",
      "habitat": "桥下、沼泽、山地",
      "lore": "巨魔被切断的肢体仍会继续攻击。",
      "weakness": "火焰与强酸可抑制再生。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Troll",
      "source": "5etools-SRD"
    }
},
{
    "name": "幽影",
    "system": "dnd5e",
    "description": "由黑暗与负能量构成的虚体亡灵，会吸取力量。",
    "stats": {
      "HP": "16",
      "AC": "12",
      "速度": "walk 40",
      "攻击": "力量吸取",
      "挑战等级": "1/2",
      "力量": "6",
      "敏捷": "14",
      "体质": "13",
      "智力": "6",
      "感知": "10",
      "魅力": "8",
      "技能": "stealth +4",
      "特性": "Amorphous: The shadow can move through a space as narrow as 1 inch wide without squeezing.；Shadow Stealth: While in dim light or darkness, the shadow can take the Hide action as a bonus action. Its stealth bonus is also improved to +6.；Sunlight Weakness: While in sunlight, the shadow has disadvantage on attack rolls, ability checks, and saving throws.",
      "动作": "Strength Drain: Melee Weapon Attack: +4 to hit, reach 5 ft., one creature. Hit: 9 (2d6+2) necrotic damage, and the target's Strength score is reduced by 1d4. The target dies if this reduces its Strength to 0. Otherwise, the reduction lasts until the target finishes a short or long rest. If a non-evil humanoid dies from this attack, a new shadow rises from the corpse 1d4 hours later."
    },
    "tags": [
      "亡灵",
      "经典"
    ],
    "details": {
      "habits": "潜伏在阴影中，袭击落单者。",
      "habitat": "暗巷、地下城、被诅咒之地",
      "lore": "幽影是强烈怨恨的残片。",
      "weakness": "光亮会削弱其隐匿；魔法武器才能有效命中。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Shadow",
      "source": "5etools-SRD"
    }
},
{
    "name": "狮鹫",
    "system": "dnd5e",
    "description": "狮身鹰首的猛兽，常被驯化为坐骑。",
    "stats": {
      "HP": "59",
      "AC": "12",
      "速度": "walk 30、fly 80",
      "攻击": "喙/爪",
      "挑战等级": "2",
      "力量": "18",
      "敏捷": "15",
      "体质": "16",
      "智力": "2",
      "感知": "13",
      "魅力": "8",
      "技能": "perception +5",
      "特性": "Keen Sight: The griffon has advantage on Wisdom (Perception) checks that rely on sight.",
      "动作": "Multiattack: The griffon makes two attacks: one with its beak and one with its claws.；Beak: Melee Weapon Attack: +6 to hit, reach 5 ft., one target. Hit: 8 (1d8+4) piercing damage.；Claws: Melee Weapon Attack: +6 to hit, reach 5 ft., one target. Hit: 11 (2d6+4) slashing damage."
    },
    "tags": [
      "野兽",
      "经典"
    ],
    "details": {
      "habits": "在高山筑巢，捕食马匹和牲畜。",
      "habitat": "高山、悬崖",
      "lore": "狮鹫忠诚但桀骜。",
      "weakness": "对空中机动目标优势明显；被擒获后难以驯服。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Griffon",
      "source": "5etools-SRD"
    }
},
{
    "name": "狼",
    "system": "dnd5e",
    "description": "集群狩猎的灰狼，擅长包夹与撕咬。",
    "stats": {
      "HP": "11",
      "AC": "13 (natural armor)",
      "速度": "walk 40",
      "力量": "12",
      "敏捷": "15",
      "体质": "12",
      "智力": "3",
      "感知": "12",
      "魅力": "6",
      "技能": "perception +3、stealth +4",
      "特性": "Keen Hearing and Smell: The wolf has advantage on Wisdom (Perception) checks that rely on hearing or smell.；Pack Tactics: The wolf has advantage on an attack roll against a creature if at least one of the wolf's allies is within 5 ft. of the creature and the ally isn't incapacitated.",
      "动作": "Bite: Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 7 (2d4+2) piercing damage. If the target is a creature, it must succeed on a DC 11 Strength saving throw or be knocked prone.",
      "挑战等级": "1/4"
    },
    "tags": [
      "野兽",
      "经典"
    ],
    "details": {
      "habits": "群居，夜间狩猎。",
      "habitat": "森林、荒原、山脚",
      "lore": "狼群会记住猎人的气味。",
      "weakness": "惧怕火焰与孤立。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Wolf",
      "source": "5etools-SRD"
    }
},
{
    "name": "巨鼠",
    "system": "dnd5e",
    "description": "变异或受污染的巨型老鼠，成群出没于下水道与废墟。",
    "stats": {
      "HP": "7",
      "AC": "12",
      "速度": "walk 30",
      "力量": "7",
      "敏捷": "15",
      "体质": "11",
      "智力": "2",
      "感知": "10",
      "魅力": "4",
      "技能": "潜行+6",
      "特性": "Keen Smell: The rat has advantage on Wisdom (Perception) checks that rely on smell.；Pack Tactics: The rat has advantage on an attack roll against a creature if at least one of the rat's allies is within 5 ft. of the creature and the ally isn't incapacitated.",
      "动作": "Bite: Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 4 (1d4+2) piercing damage.",
      "挑战等级": "1/8"
    },
    "tags": [
      "野兽",
      "经典"
    ],
    "details": {
      "habits": "夜间活动，传播疫病。",
      "habitat": "下水道、垃圾堆、废墟",
      "lore": "巨鼠常与瘟疫和污染有关。",
      "weakness": "个体脆弱，害怕捕鼠器和猫科。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Giant Rat",
      "source": "5etools-SRD"
    }
},
]
