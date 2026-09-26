"""优势/劣势规则的词汇与数据模型：schema、近战/远程词表、推断与 AdvantageDecision。

从 `combat_advantage` 拆出（那边只留裁定逻辑），`combat_advantage` 再导出这些名字，
`tool_defs_combat` / 测试的 import 路径不变。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.engine.rules import AdvantageMode
ATTACK_ADVANTAGE_SCHEMA: dict[str, dict] = {
    "advantage": {
        "type": "string", "enum": ["normal", "advantage", "disadvantage"],
        "description": "可选。后端先按状态、俯卧、束缚、隐形、力竭、长射程与近战远程规则自动判定；只有未被结构化规则覆盖的特殊来源（包抄、高台、特定法术/生物特性）才在这里声明",
    },
    "advantage_reason": {"type": "string", "description": "可选。声明 advantage/disadvantage 的特殊来源，写入结算说明"},
    "attack_kind": {"type": "string", "enum": ["melee", "ranged"], "description": "可选。本次攻击是近战还是远程；留空时后端按动作/武器/特性推断"},
    "long_range": {"type": "boolean", "description": "可选。远程攻击处于长射程；神射手可抵消该劣势"},
    "surprise": {"type": "boolean", "description": "可选。首次交战时声明本次攻击属于突袭：后端把对方标记为突袭轮不能行动/反应（警觉或免疫特性除外），下一轮自动解除"},
}
PLAYER_ATTACK_ADVANTAGE_SCHEMA = {
    **ATTACK_ADVANTAGE_SCHEMA,
    "player_condition": {"type": "string", "description": "可选。玩家当前状态描述，用于后端判定攻击劣势"},
}
ENEMY_ATTACK_ADVANTAGE_SCHEMA = {
    **ATTACK_ADVANTAGE_SCHEMA,
    "attacker_condition": {"type": "string", "description": "可选。敌人当前状态描述，用于后端判定攻击劣势"},
    "player_condition": {"type": "string", "description": "可选。玩家当前状态描述，用于后端判定受击优势/劣势"},
}


_RANGED_WORDS = (
    "弓", "弩", "远程", "射击", "射", "投掷", "飞镖", "枪", "射线",
    "ranged", "bow", "crossbow", "sling", "throw",
)
_MELEE_WORDS = (
    "近战", "挥", "劈", "砍", "刺", "戳", "咬", "爪", "剑", "斧", "锤",
    "杖", "矛", "melee", "bite", "claw", "sword", "axe",
)


def _norm(text: Any) -> str:
    return str(text or "").strip().lower()


def _has(text: str, *words: str) -> bool:
    return any(word and word.lower() in text for word in words)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _norm(value) in ("1", "true", "yes", "y", "是", "真")


def infer_attack_kind(action: str = "", weapon: str = "", traits: str = "",
                      explicit: Any = "") -> str:
    """推断攻击是近战还是远程；显式声明优先。"""
    declared = _norm(explicit)
    if declared in ("ranged", "远程", "远"):
        return "ranged"
    if declared in ("melee", "近战", "近"):
        return "melee"
    text = _norm(" ".join([action, weapon, traits]))
    if _has(text, *_RANGED_WORDS):
        return "ranged"
    if _has(text, *_MELEE_WORDS):
        return "melee"
    return "melee"


def _parse_declared(value: Any) -> AdvantageMode:
    text = _norm(value)
    if text in ("advantage", "adv", "优势", "有利"):
        return AdvantageMode.ADVANTAGE
    if text in ("disadvantage", "disadv", "劣势", "不利"):
        return AdvantageMode.DISADVANTAGE
    return AdvantageMode.NORMAL


@dataclass
class AdvantageDecision:
    mode: AdvantageMode = AdvantageMode.NORMAL
    advantages: list[str] = field(default_factory=list)
    disadvantages: list[str] = field(default_factory=list)
    neutral: list[str] = field(default_factory=list)
    cancelled: bool = False

    def summary(self) -> str:
        """给玩家/主 DM 的短说明；没有可解释来源时返回空串。"""
        if not self.advantages and not self.disadvantages and not self.neutral:
            return ""
        if self.cancelled:
            return "优势/劣势抵消：" + "、".join(self.advantages + self.disadvantages + self.neutral)
        if self.mode == AdvantageMode.ADVANTAGE:
            return "优势：" + "、".join(self.advantages)
        if self.mode == AdvantageMode.DISADVANTAGE:
            return "劣势：" + "、".join(self.disadvantages)
        if self.neutral:
            return "抵消：" + "、".join(self.neutral)
        return ""

    def event_data(self) -> dict:
        data: dict[str, Any] = {"advantage": self.mode.value}
        note = self.summary()
        if note:
            data["advantage_note"] = note
        return data
