"""内置bestiary数据：dnd5e 规则系统 第 1 部分（6 条：地精、兽人、骷髅、僵尸、红龙雏龙、眼魔）。

从 `bestiary_dnd5e.py` 按原条目顺序切块：这里只搬数据，改怪物请改对应分片。
拼接与顺序由 `bestiary_dnd5e.py` 负责，`BESTIARY_DND5E` 的内容与顺序保持不变。
"""

BESTIARY_DND5E_PART1 = [
{
    "name": "地精",
    "system": "dnd5e",
    "description": "矮小、狡诈、成群行动的人形生物，喜欢伏击与逃跑。",
    "stats": {
      "HP": "7",
      "AC": "15 (leather armor, shield)",
      "速度": "walk 30",
      "攻击": "短剑/短弓",
      "挑战等级": "1/4",
      "力量": "8",
      "敏捷": "14",
      "体质": "10",
      "智力": "10",
      "感知": "8",
      "魅力": "8",
      "技能": "stealth +6",
      "特性": "Nimble Escape: The goblin can take the Disengage or Hide action as a bonus action on each of its turns.",
      "动作": "Scimitar: Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 5 (1d6+2) slashing damage.；Shortbow: Ranged Weapon Attack: +4 to hit, range 80/320 ft., one target. Hit: 5 (1d6+2) piercing damage."
    },
    "tags": [
      "人形生物",
      "经典"
    ],
    "details": {
      "habits": "昼伏夜出，喜欢设陷阱、偷窃和以多欺少。",
      "habitat": "洞穴、废墟、森林边缘",
      "lore": "地精往往被更强大的生物驱赶或奴役。",
      "weakness": "士气低落，首领死亡后容易溃散。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Goblin",
      "source": "5etools-SRD"
    }
},
{
    "name": "兽人",
    "system": "dnd5e",
    "description": "强壮野蛮的战士，崇尚力量与战争。",
    "stats": {
      "HP": "15",
      "AC": "13 (hide armor)",
      "速度": "walk 30",
      "攻击": "巨斧",
      "挑战等级": "1/2",
      "力量": "16",
      "敏捷": "12",
      "体质": "16",
      "智力": "7",
      "感知": "11",
      "魅力": "10",
      "技能": "intimidation +2",
      "特性": "Aggressive: As a bonus action, the orc can move up to its speed toward a hostile creature that it can see.",
      "动作": "Greataxe: Melee Weapon Attack: +5 to hit, reach 5 ft., one target. Hit: 9 (1d12+3) slashing damage.；Javelin: Melee or Ranged Weapon Attack: +5 to hit, reach 5 ft. or range 30/120 ft., one target. Hit: 6 (1d6+3) piercing damage."
    },
    "tags": [
      "人形生物",
      "经典"
    ],
    "details": {
      "habits": "崇尚战功，劫掠商队和村庄。",
      "habitat": "山地、荒野、废城",
      "lore": "兽人战士以伤疤为荣耀。",
      "weakness": "容易在失去领袖时陷入内讧。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Orc",
      "source": "5etools-SRD"
    }
},
{
    "name": "骷髅",
    "system": "dnd5e",
    "description": "被亡灵魔法驱动的骸骨，不知疲倦地服从主人。",
    "stats": {
      "HP": "13",
      "AC": "13 (armor scraps)",
      "速度": "walk 30",
      "攻击": "短剑/短弓",
      "挑战等级": "1/4",
      "力量": "10",
      "敏捷": "14",
      "体质": "15",
      "智力": "6",
      "感知": "8",
      "魅力": "5",
      "技能": "—",
      "特性": "黑暗视觉；免疫中毒；不惧恐惧",
      "动作": "Shortsword: Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 5 (1d6+2) piercing damage.；Shortbow: Ranged Weapon Attack: +4 to hit, range 80/320 ft., one target. Hit: 5 (1d6+2) piercing damage."
    },
    "tags": [
      "亡灵",
      "经典"
    ],
    "details": {
      "habits": "按命令巡逻、守卫、攻击一切活物。",
      "habitat": "墓穴、废弃城堡、死灵法师巢穴",
      "lore": "骷髅没有记忆与恐惧，只会执行指令。",
      "weakness": "钝击伤害优势；被神圣力量摧毁。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Skeleton",
      "source": "5etools-SRD"
    }
},
{
    "name": "僵尸",
    "system": "dnd5e",
    "description": "缓慢但顽强的行尸，只有摧毁头部或烧成灰烬才能停止。",
    "stats": {
      "HP": "22",
      "AC": "8",
      "速度": "walk 20",
      "攻击": "挥击",
      "挑战等级": "1/4",
      "力量": "13",
      "敏捷": "6",
      "体质": "16",
      "智力": "3",
      "感知": "6",
      "魅力": "5",
      "技能": "—",
      "特性": "Undead Fortitude: If damage reduces the zombie to 0 hit points, it must make a Constitution saving throw with a DC of 5+the damage taken, unless the damage is radiant or from a critical hit. On a success, the zombie drops to 1 hit point instead.",
      "动作": "Slam: Melee Weapon Attack: +3 to hit, reach 5 ft., one target. Hit: 4 (1d6+1) bludgeoning damage."
    },
    "tags": [
      "亡灵",
      "经典"
    ],
    "details": {
      "habits": "成群漫游，追捕活物。",
      "habitat": "疫病区、墓园、沼泽",
      "lore": "僵尸由死灵法术或瘟疫创造。",
      "weakness": "火焰和光耀伤害；速度极慢。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Zombie",
      "source": "5etools-SRD"
    }
},
{
    "name": "红龙雏龙",
    "system": "dnd5e",
    "description": "暴虐红龙的幼体，已经具备喷吐火焰的危险本能。",
    "stats": {
      "HP": "75",
      "AC": "17 (natural armor)",
      "速度": "walk 30、climb 30、fly 60",
      "攻击": "啃咬/爪击/火焰吐息",
      "挑战等级": "4",
      "力量": "19",
      "敏捷": "10",
      "体质": "17",
      "智力": "12",
      "感知": "11",
      "魅力": "15",
      "技能": "perception +4、stealth +2",
      "特性": "黑暗视觉；免疫对应吐息；飞行",
      "动作": "Bite: Melee Weapon Attack: +6 to hit, reach 5 ft., one target. Hit: 9 (1d10+4) piercing damage plus 3 (1d6) fire damage.；Fire Breath (Recharge 5—6): The dragon exhales fire in a 15-foot cone. Each creature in that area must make a DC 13 Dexterity saving throw, taking 24 (7d6) fire damage on a failed save, or half as much damage on a successful one."
    },
    "tags": [
      "龙",
      "经典"
    ],
    "details": {
      "habits": "贪婪、傲慢，喜欢收集闪亮物品。",
      "habitat": "火山、高山洞窟",
      "lore": "红龙以火焰和暴政闻名。",
      "weakness": "对寒冷伤害较脆弱（相对其他龙）。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Red Dragon Wyrmling",
      "source": "5etools-SRD"
    }
},
{
    "name": "眼魔",
    "system": "dnd5e",
    "description": "漂浮的恐怖球体，中央巨眼与十根眼梗能释放多种魔法射线。",
    "stats": {
      "HP": "189",
      "AC": "18 (natural armor)",
      "速度": "walk 0、fly {'number': 20, 'condition': ' (hover)'}",
      "攻击": "啃咬/射线",
      "挑战等级": "{'cr': '13', 'lair': '14'}",
      "力量": "10",
      "敏捷": "14",
      "体质": "18",
      "智力": "17",
      "感知": "15",
      "魅力": "17",
      "技能": "perception +12",
      "特性": "Antimagic Cone: The beholder's central eye creates an area of antimagic, as in the antimagic field spell, in a 150-foot cone. At the start of each of its turns, the beholder decides which way the cone faces and whether the cone is active. The area works against the beholder's own eye rays.",
      "动作": "Bite: Melee Weapon Attack: +5 to hit, reach 5 ft., one target. Hit: 14 (4d6) piercing damage.；Eye Rays: The beholder shoots three of the following magical eye rays at random (reroll duplicates), choosing one to three targets it can see within 120 ft. of it: 1. Charm Ray. The targeted creature must succeed on a DC 16 Wisdom saving throw or be charmed by the beholder for 1 hour, or until the beholder harms the creature. 2. Paralyzing Ray. The targeted creature must succeed on a DC 16 Constitution saving throw or be paralyzed for 1 minute. The target can repeat the saving throw at the end of each of its turns, ending the effect on itself on a success. 3. Fear Ray. The targeted creature must succeed on a DC 16 Wisdom saving throw or be frightened for 1 minute. The target can repeat the saving throw at the end of each of its turns, ending the effect on itself on a success. 4. Slowing Ray. The targeted creature must succeed on a DC 16 Dexterity saving throw. On a failed save, the target's speed is halved for 1 minute. In addition, the creature can't take reactions, and it can take either an action or a bonus action on its turn, not both. The creature can repeat the saving throw at the end of each of its turns, ending the effect on itself on a success. 5. Enervation Ray. The targeted creature must make a DC 16 Constitution saving throw, taking 36 (8d8) necrotic damage on a failed save, or half as much damage on a successful one. 6. Telekinetic Ray. If the target is a creature, it must succeed on a DC 16 Strength saving throw or the beholder moves it up to 30 ft. in any direction. It is restrained by the ray's telekinetic grip until the start of the beholder's next turn or until the beholder is incapacitated. If the target is an object weighing 300 pounds or less that isn't being worn or carried, it is moved up to 30 ft. in any direction. The beholder can also exert fine control on objects with this ray, such as manipulating a simple tool or opening a door or a container. 7. Sleep Ray. The targeted creature must succeed on a DC 16 Wisdom saving throw or fall asleep and remain unconscious for 1 minute. The target awakens if it takes damage or another creature takes an action to wake it. This ray has no effect on constructs and undead. 8. Petrification Ray. The targeted creature must make a DC 16 Dexterity saving throw. On a failed save, the creature begins to turn to stone and is restrained. It must repeat the saving throw at the end of its next turn. On a success, the effect ends. On a failure, the creature is petrified until freed by the greater restoration spell or other magic. 9. Disintegration Ray. If the target is a creature, it must succeed on a DC 16 Dexterity saving throw or take 45 (10d8) force damage. If this damage reduces the creature to 0 hit points, its body becomes a pile of fine gray dust. If the target is a Large or smaller nonmagical object or creation of magical force, it is disintegrated without a saving throw. If the target is a Huge or larger object or creation of magical force, this ray disintegrates a 10-foot cube of it. 10. Death Ray. The targeted creature must succeed on a DC 16 Dexterity saving throw or take 55 (10d10) necrotic damage. The target dies if the ray reduces it to 0 hit points."
    },
    "tags": [
      "异怪",
      "经典"
    ],
    "details": {
      "habits": "极端自恋，建立地下巢穴奴役仆从。",
      "habitat": "幽暗地域、漂浮城堡",
      "lore": "眼魔认为自己是宇宙中心。",
      "weakness": "反魔法力场能压制其射线。",
      "related_locations": [],
      "related_npcs": [],
      "related_creatures": [],
      "name_en": "Beholder",
      "source": "5etools-SRD"
    }
},
]
