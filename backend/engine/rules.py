"""D&D 5e 规则引擎——d20检定、死亡豁免、休息、法术位。"""

import random
import re
from dataclasses import dataclass
from enum import Enum


class RollResult(Enum):
    CRITICAL_SUCCESS = "大成功"   # 自然20
    SUCCESS = "成功"
    FAILURE = "失败"
    CRITICAL_FAILURE = "大失败"   # 自然1


class AdvantageMode(Enum):
    NORMAL = "normal"
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"


@dataclass
class DiceRoll:
    skill_name: str
    dc: int
    roll: int
    modifier: int
    total: int
    result: RollResult
    advantage: AdvantageMode = AdvantageMode.NORMAL
    second_roll: int | None = None

    def to_event_data(self) -> dict:
        return {
            "skill": self.skill_name,
            "dc": self.dc,
            "roll": self.roll,
            "modifier": self.modifier,
            "result": self.result.value,
        }


def roll_d20() -> int:
    return random.randint(1, 20)


def parse_dice_expression(text: str) -> tuple[int, int] | None:
    """解析骰式：`d20` / `2d10` / `3d6` → (个数, 面数)；不合法返回 None。

    自定义规则系统的玩家可以自己规定判定骰（例如 2d10 取和对抗目标值），
    但骰式必须由后端解析与投掷，不能让模型在叙事里自己编。
    """
    value = str(text or "").strip().lower().replace(" ", "")
    match = re.fullmatch(r"(\d{0,2})d(\d{1,4})", value)
    if match is None:
        return None
    count = int(match.group(1) or 1)
    faces = int(match.group(2))
    if not (1 <= count <= 10) or not (2 <= faces <= 1000):
        return None
    return count, faces


def _determine_result(total: int, natural_roll: int, dc: int) -> RollResult:
    if natural_roll == 20:
        return RollResult.CRITICAL_SUCCESS
    if natural_roll == 1:
        return RollResult.CRITICAL_FAILURE
    if total >= dc:
        return RollResult.SUCCESS
    return RollResult.FAILURE


def ability_mod_for_skill(skill_name: str, attrs: dict) -> int:
    skill_lower = skill_name.lower()
    if any(w in skill_lower for w in ["潜行","躲藏","开锁","巧手","扒窃","特技","stealth","acrobatics","lockpick","远程","弓","弩"]):
        return (attrs.get("dex", 10) - 10) // 2
    if any(w in skill_lower for w in ["抗毒","毒素","疾病","屏息","耐力","长跑"]):
        return (attrs.get("con", 10) - 10) // 2
    if any(w in skill_lower for w in ["奥秘","历史","调查","自然","宗教","解读","arcana","history","investigation","nature","religion"]):
        return (attrs.get("int", 10) - 10) // 2
    if any(w in skill_lower for w in ["侦查","察觉","聆听","洞察","追踪","生存","医疗","驯兽","perception","insight","survival","medicine"]):
        return (attrs.get("wis", 10) - 10) // 2
    if any(w in skill_lower for w in ["说服","欺骗","威吓","表演","交涉","游说","persuasion","deception","intimidation","performance"]):
        return (attrs.get("cha", 10) - 10) // 2
    return (attrs.get("str", 10) - 10) // 2

def skill_check(
    skill_name: str, dc: int, modifier: int = 0,
    advantage: AdvantageMode = AdvantageMode.NORMAL,
) -> DiceRoll:
    roll1 = roll_d20()
    if advantage == AdvantageMode.NORMAL:
        total = roll1 + modifier
        return DiceRoll(skill_name=skill_name, dc=dc, roll=roll1,
                        modifier=modifier, total=total,
                        result=_determine_result(total, roll1, dc))
    roll2 = roll_d20()
    if advantage == AdvantageMode.ADVANTAGE:
        chosen = max(roll1, roll2)
    else:
        chosen = min(roll1, roll2)
    total = chosen + modifier
    return DiceRoll(skill_name=skill_name, dc=dc, roll=chosen,
                    modifier=modifier, total=total,
                    result=_determine_result(total, chosen, dc),
                    advantage=advantage,
                    second_roll=roll2 if roll2 != chosen else roll1)


def combat_attack_roll(
    attacker_name: str, target_ac: int, attack_modifier: int = 0,
    damage_dice: str = "1d6",
    advantage: AdvantageMode = AdvantageMode.NORMAL,
) -> tuple[DiceRoll, int]:
    hit = skill_check(f"{attacker_name} 攻击", target_ac, attack_modifier, advantage)
    if hit.result in (RollResult.SUCCESS, RollResult.CRITICAL_SUCCESS):
        dmg = _roll_damage(damage_dice)
        if hit.result == RollResult.CRITICAL_SUCCESS:
            dmg *= 2
        return hit, dmg
    return hit, 0


def _roll_damage(spec: str) -> int:
    """解析如 '2d8+3' 的伤害骰。"""
    parts = spec.split("+")
    dice_part = parts[0].strip()
    bonus = int(parts[1].strip()) if len(parts) > 1 else 0
    num, sides = dice_part.split("d")
    return sum(random.randint(1, int(sides)) for _ in range(int(num))) + bonus


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


# ═══════════════════════════════════════════════════════════════
# 死亡豁免 (Death Saving Throws)
# ═══════════════════════════════════════════════════════════════

@dataclass
class DeathSaves:
    """D&D 5e 死亡豁免追踪。HP降到0时进入濒死状态。"""
    successes: int = 0
    failures: int = 0

    @property
    def is_dead(self) -> bool:
        return self.failures >= 3

    @property
    def is_stable(self) -> bool:
        return self.successes >= 3

    @property
    def is_dying(self) -> bool:
        return not self.is_dead and not self.is_stable


def roll_death_save(saves: DeathSaves) -> dict:
    """掷一次死亡豁免。

    D&D 5e规则：
    - d20 >= 10 → 成功（自然20=恢复1HP醒来）
    - d20 < 10 → 失败（自然1=计2次失败）
    - 累计3成功=稳定（0HP但不再濒死）
    - 累计3失败=死亡
    """
    roll = roll_d20()
    if roll == 20:
        saves.successes = 0
        saves.failures = 0
        return {"roll": roll, "result": "复活", "hp_restored": 1,
                "successes": saves.successes, "failures": saves.failures}
    if roll == 1:
        saves.failures += 2
        return {"roll": roll, "result": "两次失败",
                "successes": saves.successes, "failures": saves.failures,
                "dead": saves.is_dead}
    if roll >= 10:
        saves.successes += 1
        return {"roll": roll, "result": "成功",
                "successes": saves.successes, "failures": saves.failures,
                "stable": saves.is_stable}
    else:
        saves.failures += 1
        return {"roll": roll, "result": "失败",
                "successes": saves.successes, "failures": saves.failures,
                "dead": saves.is_dead}


# ═══════════════════════════════════════════════════════════════
# 休息机制
# ═══════════════════════════════════════════════════════════════

def short_rest(hp: int, max_hp: int, level: int, con_mod: int,
               hit_dice_remaining: int, hit_dice_type: int = 8,
               dice_to_use: int | None = None, min_per_die: int = 0) -> dict:
    """短休：消耗生命骰恢复HP。

    不指定数量时默认至多 2 个（避免一次短休把骰池抽干）；
    显式指定时按其数量执行，但不会超过剩余生命骰。
    `min_per_die` 为每颗骰子的最低治疗量（特长「强健」= 2×CON 调整值）。
    """
    if dice_to_use is None:
        dice_to_use = min(2, hit_dice_remaining)
    else:
        try:
            dice_to_use = max(0, min(int(dice_to_use), hit_dice_remaining))
        except (TypeError, ValueError):
            dice_to_use = min(2, hit_dice_remaining)
    healed = sum(max(min_per_die, random.randint(1, hit_dice_type) + con_mod)
                 for _ in range(dice_to_use))
    new_hp = min(max_hp, hp + healed)
    return {
        "hp_restored": new_hp - hp,
        "new_hp": new_hp,
        "hit_dice_used": dice_to_use,
        "hit_dice_remaining": hit_dice_remaining - dice_to_use,
    }


def long_rest(hp: int, max_hp: int, hit_dice_total: int) -> dict:
    """长休：恢复全部HP和至多一半生命骰。"""
    return {
        "hp_restored": max_hp - hp,
        "new_hp": max_hp,
        "hit_dice_restored": max(1, hit_dice_total // 2),
    }
