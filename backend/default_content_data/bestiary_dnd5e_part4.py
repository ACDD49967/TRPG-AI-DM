"""内置bestiary数据：dnd5e 规则系统 第 4 部分（5 条：幽灵、熊地精、鹰马、火元素、石魔像）。

从 `bestiary_dnd5e.py` 按原条目顺序切块：这里只搬数据，改怪物请改对应分片。
拼接与顺序由 `bestiary_dnd5e.py` 负责，`BESTIARY_DND5E` 的内容与顺序保持不变。
"""

BESTIARY_DND5E_PART4 = [
{
    "name": "幽灵",
    "system": "dnd5e",
    "description": "充满怨恨的虚体亡灵，能吸取生命能量。",
    "stats": {
      "HP": "22",
      "AC": "12",
      "速度": "walk 0、fly {'number': 50, 'condition': ' (hover)'}",
      "力量": "1",
      "敏捷": "14",
      "体质": "11",
      "智力": "10",
      "感知": "10",
      "魅力": "11",
      "技能": "—",
      "特性": "Incorporeal Movement: The specter can move through other creatures and objects as if they were difficult terrain. It takes 5 (1d10) force damage if it ends its turn inside an object.；Sunlight Sensitivity: While in sunlight, the specter has disadvantage on attack rolls, as well as on Wisdom (Perception) checks that rely on sight.",
      "动作": "Life Drain: Melee Spell Attack: +4 to hit, reach 5 ft., one creature. Hit: 10 (3d6) necrotic damage. The target must succeed on a DC 10 Constitution saving throw or its hit point maximum is reduced by an amount equal to the damage taken. This reduction lasts until the creature finishes a long rest. The target dies if this effect reduces its hit point maximum to 0.",
      "挑战等级": "1"
    },
    "tags": [
      "亡灵",
      "经典"
    ],
    "details": {
      "habits": "徘徊在死地，寻找仇恨目标。",
      "habitat": "凶宅、墓园、战场",
      "lore": "幽灵是未竟之愿的残响。",
      "weakness": "光亮与神圣力量。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Specter",
      "source": "5etools-SRD"
    }
},
{
    "name": "熊地精",
    "system": "dnd5e",
    "description": "高大毛茸茸的类人掠食者，擅长伏击与擒抱。",
    "stats": {
      "HP": "27",
      "AC": "16 (hide armor, shield)",
      "速度": "walk 30",
      "力量": "15",
      "敏捷": "14",
      "体质": "13",
      "智力": "8",
      "感知": "11",
      "魅力": "9",
      "技能": "stealth +6、survival +2",
      "特性": "Brute: A melee weapon deals one extra die of its damage when the bugbear hits with it (included in the attack).；Surprise Attack: If the bugbear surprises a creature and hits it with an attack during the first round of combat, the target takes an extra 7 (2d6) damage from the attack.",
      "动作": "Morningstar: Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 11 (2d8+2) piercing damage.；Javelin: Melee or Ranged Weapon Attack: +4 to hit, reach 5 ft. or range 30/120 ft., one target. Hit: 9 (2d6+2) piercing damage in melee or 5 (1d6+2) piercing damage at range.",
      "挑战等级": "1"
    },
    "tags": [
      "人形生物",
      "怪物",
      "经典"
    ],
    "details": {
      "habits": "夜间伏击，绑架旅人。",
      "habitat": "森林、洞窟、荒野",
      "lore": "熊地精会收集受害者的武器。",
      "weakness": "独行时较谨慎，群居时易内讧。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Bugbear",
      "source": "5etools-SRD"
    }
},
{
    "name": "鹰马",
    "system": "dnd5e",
    "description": "鹰首马身的猛兽，桀骜但可被驯化为坐骑。",
    "stats": {
      "HP": "19",
      "AC": "11",
      "速度": "walk 40、fly 60",
      "力量": "17",
      "敏捷": "13",
      "体质": "13",
      "智力": "2",
      "感知": "12",
      "魅力": "8",
      "技能": "perception +5",
      "特性": "Keen Sight: The hippogriff has advantage on Wisdom (Perception) checks that rely on sight.",
      "动作": "Multiattack: The hippogriff makes two attacks: one with its beak and one with its claws.；Beak: Melee Weapon Attack: +5 to hit, reach 5 ft., one target. Hit: 8 (1d10+3) piercing damage.；Claws: Melee Weapon Attack: +5 to hit, reach 5 ft., one target. Hit: 10 (2d6+3) slashing damage.",
      "挑战等级": "1"
    },
    "tags": [
      "野兽",
      "经典"
    ],
    "details": {
      "habits": "高山筑巢，捕食马匹。",
      "habitat": "高山、悬崖、草原",
      "lore": "鹰马与狮鹫是近亲。",
      "weakness": "被擒后难以驯服。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Hippogriff",
      "source": "5etools-SRD"
    }
},
{
    "name": "火元素",
    "system": "dnd5e",
    "description": "纯粹火焰构成的原生元素，所经之处化为灰烬。",
    "stats": {
      "HP": "102",
      "AC": "13",
      "速度": "walk 50",
      "力量": "10",
      "敏捷": "17",
      "体质": "16",
      "智力": "6",
      "感知": "10",
      "魅力": "7",
      "技能": "—",
      "特性": "Fire Form: The elemental can move through a space as narrow as 1 inch wide without squeezing. A creature that touches the elemental or hits it with a melee attack while within 5 ft. of it takes 5 (1d10) fire damage. In addition, the elemental can enter a hostile creature's space and stop there. The first time it enters a creature's space on a turn, that creature takes 5 (1d10) fire damage and catches fire; until someone takes an action to douse the fire, the creature takes 5 (1d10) fire damage at the start of each of its turns.；Illumination: The elemental sheds bright light in a 30-foot radius and dim light in an additional 30 ft..；Water Susceptibility: For every 5 ft. the elemental moves in water, or for every gallon of water splashed on it, it takes 1 cold damage.",
      "动作": "Multiattack: The elemental makes two touch attacks.；Touch: Melee Weapon Attack: +6 to hit, reach 5 ft., one target. Hit: 10 (2d6+3) fire damage. If the target is a creature or a flammable object, it ignites. Until a creature takes an action to douse the fire, the target takes 5 (1d10) fire damage at the start of each of its turns.",
      "挑战等级": "5"
    },
    "tags": [
      "元素",
      "经典"
    ],
    "details": {
      "habits": "燃烧一切可燃物。",
      "habitat": "火元素位面、火山、火场",
      "lore": "火元素没有固定形态。",
      "weakness": "水与寒冷伤害。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Fire Elemental",
      "source": "5etools-SRD"
    }
},
{
    "name": "石魔像",
    "system": "dnd5e",
    "description": "由魔法驱动的石制守卫，几乎不可摧毁。",
    "stats": {
      "HP": "178",
      "AC": "17 (natural armor)",
      "速度": "walk 30",
      "力量": "22",
      "敏捷": "9",
      "体质": "20",
      "智力": "3",
      "感知": "11",
      "魅力": "1",
      "技能": "—",
      "特性": "Immutable Form: The golem is immune to any spell or effect that would alter its form.；Magic Resistance: The golem has advantage on saving throws against spells and other magical effects.；Magic Weapons: The golem's weapon attacks are magical.",
      "动作": "Multiattack: The golem makes two slam attacks.；Slam: Melee Weapon Attack: +10 to hit, reach 5 ft., one target. Hit: 19 (3d8+6) bludgeoning damage.；Slow (Recharge 5—6): The golem targets one or more creatures it can see within 10 ft. of it. Each target must make a DC 17 Wisdom saving throw against this magic. On a failed save, a target can't use reactions, its speed is halved, and it can't make more than one attack on its turn. In addition, the target can take either an action or a bonus action on its turn, not both. These effects last for 1 minute. A target can repeat the saving throw at the end of each of its turns, ending the effect on itself on a success.",
      "挑战等级": "10"
    },
    "tags": [
      "构装体",
      "经典"
    ],
    "details": {
      "habits": "守卫重要区域，按指令行动。",
      "habitat": "法师塔、神殿、陵墓",
      "lore": "石魔像不知疲倦、没有情感。",
      "weakness": "需要魔法武器或特定法术才能有效伤害。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Stone Golem",
      "source": "5etools-SRD"
    }
},
]
