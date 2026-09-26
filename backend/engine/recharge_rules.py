"""生物充能能力：解析 `Recharge 5—6`、检查可用性并在回合开始掷骰充能。"""
from __future__ import annotations

import random
import re
from typing import Any

_RECHARGE = re.compile(
    r"([A-Za-z\u4e00-\u9fff][^；;。.\n]{0,40}?)[（(]\s*(?:recharge|充能)\s*(\d)"
    r"\s*(?:[-—–]\s*(\d))?\s*[)）]",
    re.I,
)

def _traits_text(npc: Any) -> str:
    return " ".join(str(t) for t in (getattr(npc, "traits", []) or []))


def parse_recharge_abilities(npc: Any) -> dict[str, int]:
    """返回 {能力名: 充能最低 d6 值}；没有充能特性返回空字典。"""
    text = _traits_text(npc)
    if not text:
        return {}
    out: dict[str, int] = {}
    for chunk in re.split(r"[；;。.\n]", text):
        match = _RECHARGE.search(chunk)
        if not match:
            continue
        name = re.sub(r"^[\s:：]+", "", match.group(1)).strip()
        if name:
            out[name] = int(match.group(2))
    return out


def _state_key(actor: str, ability: str) -> str:
    return f"{str(actor or '').strip().lower()}|{str(ability or '').strip().lower()}"


def _used(state: Any) -> set[str]:
    used = getattr(state, "recharge_used", None)
    if not isinstance(used, set):
        used = set()
        try:
            state.recharge_used = used
        except Exception:
            pass
    return used


def _match_ability(abilities: dict[str, int], requested: str) -> tuple[str, int] | None:
    key = str(requested or "").strip().lower()
    if not key:
        return None
    for name, minimum in abilities.items():
        low = name.lower()
        if key == low or key in low or low in key:
            return name, minimum
    return None


def match_recharge_ability(npc: Any, requested: str) -> str:
    """从动作名/描述里匹配图鉴中的充能能力名；未命中返回空串。"""
    matched = _match_ability(parse_recharge_abilities(npc), str(requested or ""))
    return matched[0] if matched else ""


def recharge_available(state: Any, actor: str, ability: str, npc: Any) -> tuple[bool, str]:
    """检查能力是否可用；非充能能力直接放行。"""
    matched = _match_ability(parse_recharge_abilities(npc), ability)
    if matched is None:
        return True, ""
    name, minimum = matched
    if _state_key(actor, name) in _used(state):
        return False, f"⚠ {actor} 的「{name}」尚未充能（Recharge {minimum}+），本轮不能使用。"
    return True, ""


def mark_recharge_used(state: Any, actor: str, ability: str, npc: Any) -> None:
    """登记一次能力使用；非充能能力静默忽略。"""
    matched = _match_ability(parse_recharge_abilities(npc), ability)
    if matched is not None:
        _used(state).add(_state_key(actor, matched[0]))


def roll_recharge(state: Any, actor: str, npc: Any, rng: Any = None) -> str:
    """回合开始掷 d6；返回已充能/未充能的可见说明。"""
    abilities = parse_recharge_abilities(npc)
    used = _used(state)
    lines: list[str] = []
    r = rng or random
    for name, minimum in abilities.items():
        key = _state_key(actor, name)
        if key not in used:
            continue
        roll = int(r.randint(1, 6))
        if roll >= minimum:
            used.discard(key)
            lines.append(f"♻️ {actor} 的「{name}」充能成功（d6={roll}）。")
        else:
            lines.append(f"⏳ {actor} 的「{name}」未充能（d6={roll}）。")
    return "\n".join(lines)


RECHARGE_ABILITY_SCHEMA = {
    "recharge_ability": {
        "type": "string",
        "description": "可选。若本次使用的是 Recharge/充能能力（如 Fire Breath），填能力名；后端检查冷却并在回合开始掷充能",
    },
}
SAVE_DAMAGE_RECHARGE_SCHEMA = {
    **RECHARGE_ABILITY_SCHEMA,
    "actor": {"type": "string", "description": "可选。范围能力的使用者（怪物吐息、陷阱等）；仅用于充能追踪"},
}
