"""内置bestiary数据：dnd5e 规则系统 第 3 部分（5 条：巨蜘蛛、强盗、食人魔、狼人、吸血鬼衍体）。

从 `bestiary_dnd5e.py` 按原条目顺序切块：这里只搬数据，改怪物请改对应分片。
拼接与顺序由 `bestiary_dnd5e.py` 负责，`BESTIARY_DND5E` 的内容与顺序保持不变。
"""

BESTIARY_DND5E_PART3 = [
{
    "name": "巨蜘蛛",
    "system": "dnd5e",
    "description": "体型巨大的毒蛛，潜伏在暗处等待猎物。",
    "stats": {
      "HP": "26",
      "AC": "14 (natural armor)",
      "速度": "walk 30、climb 30",
      "力量": "14",
      "敏捷": "16",
      "体质": "12",
      "智力": "2",
      "感知": "11",
      "魅力": "4",
      "技能": "stealth +7",
      "特性": "Spider Climb: The spider can climb difficult surfaces, including upside down on ceilings, without needing to make an ability check.；Web Sense: While in contact with a web, the spider knows the exact location of any other creature in contact with the same web.；Web Walker: The spider ignores movement restrictions caused by webbing.",
      "动作": "Bite: Melee Weapon Attack: +5 to hit, reach 5 ft., one creature. Hit: 7 (1d8+3) piercing damage, and the target must make a DC 11 Constitution saving throw, taking 9 (2d8) poison damage on a failed save, or half as much damage on a successful one. If the poison damage reduces the target to 0 hit points, the target is stable but poisoned for 1 hour, even after regaining hit points, and is paralyzed while poisoned in this way.；Web (Recharge 5—6): Ranged Weapon Attack: +5 to hit, range 30/60 ft., one creature. Hit: The target is restrained by webbing. As an action, the restrained target can make a DC 12 Strength check, bursting the webbing on a success. The webbing can also be attacked and destroyed (AC 10; hp 5; vulnerability to fire damage; immunity to bludgeoning, poison, and psychic damage).",
      "挑战等级": "1"
    },
    "tags": [
      "野兽",
      "经典"
    ],
    "details": {
      "habits": "结网设伏。",
      "habitat": "森林、洞窟、废墟",
      "lore": "毒蜘蛛的毒液足以麻痹中型生物。",
      "weakness": "怕火，网怕火与强酸。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Giant Spider",
      "source": "5etools-SRD"
    }
},
{
    "name": "强盗",
    "system": "dnd5e",
    "description": "埋伏在商道上的劫匪，通常成群出动。",
    "stats": {
      "HP": "11",
      "AC": "12 (leather armor)",
      "速度": "walk 30",
      "力量": "11",
      "敏捷": "12",
      "体质": "12",
      "智力": "10",
      "感知": "10",
      "魅力": "10",
      "技能": "潜行+3",
      "特性": "集群作战",
      "动作": "Scimitar: Melee Weapon Attack: +3 to hit, reach 5 ft., one target. Hit: 4 (1d6+1) slashing damage.；Light Crossbow: Ranged Weapon Attack: +3 to hit, range 80 ft./320 ft., one target. Hit: 5 (1d8+1) piercing damage.",
      "挑战等级": "1/8"
    },
    "tags": [
      "人形生物",
      "经典"
    ],
    "details": {
      "habits": "拦路打劫、收取保护费。",
      "habitat": "商道、荒野、废屋",
      "lore": "有些强盗是被生活逼上绝路的农民。",
      "weakness": "士气不高，首领死亡后容易投降。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Bandit",
      "source": "5etools-SRD"
    }
},
{
    "name": "食人魔",
    "system": "dnd5e",
    "description": "高大愚笨的巨人，用蛮力碾压一切。",
    "stats": {
      "HP": "59",
      "AC": "11 (hide armor)",
      "速度": "walk 40",
      "力量": "19",
      "敏捷": "8",
      "体质": "16",
      "智力": "5",
      "感知": "7",
      "魅力": "7",
      "技能": "—",
      "特性": "黑暗视觉",
      "动作": "Greatclub: Melee Weapon Attack: +6 to hit, reach 5 ft., one target. Hit: 13 (2d8+4) bludgeoning damage.；Javelin: Melee or Ranged Weapon Attack: +6 to hit, reach 5 ft. or range 30/120 ft., one target. Hit: 11 (2d6+4) piercing damage.",
      "挑战等级": "2"
    },
    "tags": [
      "巨人",
      "经典"
    ],
    "details": {
      "habits": "占山为王，抢夺食物。",
      "habitat": "山道、废墟、洞穴",
      "lore": "食人魔会把战利品堆成一堆。",
      "weakness": "智力低下，容易被欺骗。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Ogre",
      "source": "5etools-SRD"
    }
},
{
    "name": "狼人",
    "system": "dnd5e",
    "description": "受月光诅咒的人形狼兽，兼具人类智慧与野兽凶残。",
    "stats": {
      "HP": "58",
      "AC": "11 (in humanoid form, 12 in wolf or hybrid form)",
      "速度": "walk {'number': 30, 'condition': ' (40 ft. in wolf form)'}",
      "力量": "15",
      "敏捷": "13",
      "体质": "14",
      "智力": "10",
      "感知": "11",
      "魅力": "10",
      "技能": "perception +4",
      "特性": "Shapechanger: The werewolf can use its action to polymorph into a wolf-humanoid hybrid or into a wolf, or back into its true form, which is humanoid. Its statistics, other than its AC, are the same in each form. Any equipment it is wearing or carrying isn't transformed. It reverts to its true form if it dies.；Keen Hearing and Smell: The werewolf has advantage on Wisdom (Perception) checks that rely on hearing or smell.",
      "动作": "Multiattack (Humanoid or Hybrid Form Only): The werewolf makes two attacks: one with its bite and one with its claws or spear.；Bite (Wolf or Hybrid Form Only): Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 6 (1d8+2) piercing damage. If the target is a humanoid, it must succeed on a DC 12 Constitution saving throw or be cursed with werewolf lycanthropy.；Claws (Hybrid Form Only): Melee Weapon Attack: +4 to hit, reach 5 ft., one creature. Hit: 7 (2d4+2) slashing damage.；Spear (Humanoid Form Only): Melee or Ranged Weapon Attack: +4 to hit, reach 5 ft. or range 20/60 ft., one creature. Hit: 5 (1d6+2) piercing damage, or 6 (1d8+2) piercing damage if used with two hands to make a melee attack.",
      "挑战等级": "3"
    },
    "tags": [
      "人形生物",
      "怪物",
      "经典"
    ],
    "details": {
      "habits": "满月时变身，狩猎人类。",
      "habitat": "森林、荒野、村庄边缘",
      "lore": "被狼人咬伤者可能感染诅咒。",
      "weakness": "银制武器可造成正常伤害。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Werewolf",
      "source": "5etools-SRD"
    }
},
{
    "name": "吸血鬼衍体",
    "system": "dnd5e",
    "description": "吸血鬼的仆从，无法完全变身但渴望血液。",
    "stats": {
      "HP": "82",
      "AC": "15 (natural armor)",
      "速度": "walk 30",
      "力量": "16",
      "敏捷": "16",
      "体质": "16",
      "智力": "11",
      "感知": "10",
      "魅力": "12",
      "技能": "perception +3、stealth +6",
      "特性": "Regeneration: The vampire regains 10 hit points at the start of its turn if it has at least 1 hit point and isn't in sunlight or running water. If the vampire takes radiant damage or damage from holy water, this trait doesn't function at the start of the vampire's next turn.；Spider Climb: The vampire can climb difficult surfaces, including upside down on ceilings, without needing to make an ability check.；Vampire Weaknesses: The vampire has the following flaws: Forbiddance. The vampire can't enter a residence without an invitation from one of the occupants. Harmed by Running Water. The vampire takes 20 acid damage when it ends its turn in running water. Stake to the Heart. The vampire is destroyed if a piercing weapon made of wood is driven into its heart while it is incapacitated in its resting place. Sunlight Hypersensitivity. The vampire takes 20 radiant damage when it starts its turn in sunlight. While in sunlight, it has disadvantage on attack rolls and ability checks.",
      "动作": "Multiattack: The vampire makes two attacks, only one of which can be a bite attack.；Bite: Melee Weapon Attack: +6 to hit, reach 5 ft., one willing creature, or a creature that is grappled by the vampire, incapacitated, or restrained. Hit: 6 (1d6+3) piercing damage plus 7 (2d6) necrotic damage. The target's hit point maximum is reduced by an amount equal to the necrotic damage taken, and the vampire regains hit points equal to that amount. The reduction lasts until the target finishes a long rest. The target dies if this effect reduces its hit point maximum to 0.；Claws: Melee Weapon Attack: +6 to hit, reach 5 ft., one creature. Hit: 8 (2d4+3) slashing damage. Instead of dealing damage, the vampire can grapple the target (escape DC 13).",
      "挑战等级": "5"
    },
    "tags": [
      "亡灵",
      "怪物",
      "经典"
    ],
    "details": {
      "habits": "夜晚出没，吸食活物血液。",
      "habitat": "古堡、墓穴、暗巷",
      "lore": "吸血鬼衍体服从其创造者。",
      "weakness": "阳光、流动的水、木桩。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Vampire Spawn",
      "source": "5etools-SRD"
    }
},
]
