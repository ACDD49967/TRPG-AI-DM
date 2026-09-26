"""回合开始效果：阳光超敏伤害与再生（含酸/火/光耀抑制、0 HP 复活延后结算）。

再生生物被击倒时不立即发经验：先标记 pending；其回合开始若成功再生则
撤销击倒，若被抑制则补发击败经验。
"""
from __future__ import annotations

import re
from typing import Any

from backend.engine.combat_advantage import in_sunlight
from backend.engine.session import GameSessionState, push_event, push_narrative_token

_SUNLIGHT_HYPERSENSITIVITY = re.compile(
    r"sunlight\s+hypersensitivity|阳光超敏|阳光过敏", re.I)
_REGENERATION = re.compile(r"regeneration|再生", re.I)
_REGEN_AMOUNT = re.compile(
    r"regains?\s+(\d+)\s+hit points|恢复\s*(\d+)\s*点", re.I)


def _applied(state: GameSessionState) -> set[str]:
    applied = getattr(state, "turn_start_effects_applied", None)
    if not isinstance(applied, set):
        applied = set()
        try:
            state.turn_start_effects_applied = applied
        except Exception:
            pass
    return applied


def _round_key(state: GameSessionState, actor: str) -> str:
    from backend.engine import initiative
    tracker = initiative.tracker_for(state)
    round_no = int(getattr(tracker, "round", 0) or 0)
    return f"{str(actor or '').strip().lower()}@{round_no}"


def _traits_text(actor: str, npc: Any = None) -> str:
    if npc is not None:
        return " ".join(str(t) for t in (getattr(npc, "traits", []) or []))
    return ""


def has_regeneration(npc: Any) -> bool:
    """NPC 是否带再生特性。"""
    return bool(npc is not None and _REGENERATION.search(_traits_text("", npc)))


def _pending(state: GameSessionState) -> set[str]:
    pending = getattr(state, "pending_regeneration", None)
    if not isinstance(pending, set):
        pending = set()
        try:
            state.pending_regeneration = pending
        except Exception:
            pass
    return pending


def mark_pending_regeneration(state: GameSessionState, actor: str) -> None:
    key = str(actor or "").strip().lower()
    if key:
        _pending(state).add(key)


def is_pending_regeneration(state: GameSessionState, actor: str) -> bool:
    return str(actor or "").strip().lower() in _pending(state)


def _clear_pending(state: GameSessionState, actor: str) -> None:
    _pending(state).discard(str(actor or "").strip().lower())


def record_damage_type(state: GameSessionState, actor: str, damage_type: Any) -> None:
    """记录某单位近期受到的伤害类型，供再生抑制判断。"""
    from backend.engine.damage_rules import canonical_damage_type

    canonical = canonical_damage_type(damage_type) or str(damage_type or "").strip()
    key = str(actor or "").strip().lower()
    if not key or not canonical:
        return
    recent = getattr(state, "recent_damage_types", None)
    if not isinstance(recent, dict):
        recent = {}
        try:
            state.recent_damage_types = recent
        except Exception:
            return
    recent.setdefault(key, set()).add(canonical)


def _take_recent_damage_types(state: GameSessionState, actor: str) -> set[str]:
    recent = getattr(state, "recent_damage_types", None)
    if not isinstance(recent, dict):
        return set()
    return set(recent.pop(str(actor or "").strip().lower(), set()) or set())


def _regen_amount(traits: str) -> int:
    match = _REGEN_AMOUNT.search(traits)
    if not match:
        return 0
    return int(match.group(1) or match.group(2) or 0)


def _regen_block_reason(state: GameSessionState, traits: str,
                        recent_types: set[str]) -> str:
    text = traits.lower()
    recent = " ".join(sorted(recent_types)).lower()
    if ("acid" in text or "强酸" in text) and ("fire" in text or "火焰" in text):
        if "强酸" in recent or "火焰" in recent:
            return "近期受到强酸或火焰伤害"
    if "radiant" in text or "光耀" in text:
        if "光耀" in recent:
            return "近期受到光耀伤害"
    if ("isn't in sunlight" in text or "不在阳光下" in text) and in_sunlight(state):
        return "处于阳光下"
    return ""


async def apply_turn_start_effects(
    state: GameSessionState, actor: str, npc: Any = None,
) -> str:
    """结算某单位本轮的回合开始效果；返回给 DM 的可见说明。"""
    key = _round_key(state, actor)
    applied = _applied(state)
    if key in applied:
        return ""
    applied.add(key)

    traits = _traits_text(actor, npc)
    lines: list[str] = []
    if _SUNLIGHT_HYPERSENSITIVITY.search(traits) and in_sunlight(state):
        damage = 20
        if npc is None:
            from backend.engine import player_damage
            outcome = await player_damage.apply(
                state, damage, damage_type="光耀",
                reason="阳光超敏", source=actor)
            lines.append(
                f"☀️ {actor} 在阳光下承受阳光超敏：受到 {outcome['hp_damage']} 点光耀伤害"
                f"（HP {outcome['hp_before']}→{outcome['hp_after']}）。")
        else:
            current = int(getattr(npc, "hp", 0) or 0)
            new_hp = max(0, current - damage)
            fortitude_note = ""
            if new_hp <= 0:
                from backend.engine.undead_fortitude import resolve_undead_fortitude
                fort = await resolve_undead_fortitude(
                    state, npc, actor, damage=damage, damage_type="光耀")
                fortitude_note = str(fort.get("note") or "")
                if fort.get("applied"):
                    new_hp = int(fort.get("hp") or 1)
            from backend.engine import combat
            await combat._persist_combat_damage(state, npc, new_hp)
            lines.append(
                f"☀️ {actor} 在阳光下承受阳光超敏：受到 {damage} 点光耀伤害"
                f"（HP {current}→{new_hp}）。")
            if fortitude_note:
                lines.append(f"  [{fortitude_note}]")

    recent_types = _take_recent_damage_types(state, actor)
    if npc is not None and has_regeneration(npc):
        amount = _regen_amount(traits)
        current = int(getattr(npc, "hp", 0) or 0)
        max_hp = int(getattr(npc, "max_hp", 0) or 0)
        block = _regen_block_reason(state, traits, recent_types)
        pending = is_pending_regeneration(state, actor)
        if amount > 0 and current <= 0 and pending and not block:
            new_hp = min(max_hp or amount, amount)
            npc.hp = new_hp
            npc.alive = True
            npc.xp_awarded = False
            from backend.engine import initiative
            initiative.revive(state, actor, new_hp, max_hp)
            _clear_pending(state, actor)
            lines.append(f"♻️ {actor} 再生：从 0 HP 恢复到 {new_hp}，重新站起。")
        elif amount > 0 and current <= 0 and pending and block:
            _clear_pending(state, actor)
            from backend.engine.combat_rewards import _award_defeat_xp
            xp = await _award_defeat_xp(state, npc)
            suffix = f"（+{xp} XP）" if xp else ""
            lines.append(f"♻️ {actor} 的再生被抑制（{block}），无法复活{suffix}。")
        elif amount > 0 and current > 0 and not block:
            new_hp = min(max_hp or current + amount, current + amount)
            from backend.engine import combat
            await combat._persist_combat_damage(state, npc, new_hp)
            lines.append(f"♻️ {actor} 再生：恢复 {new_hp - current} 点（HP {current}→{new_hp}）。")
        elif block:
            lines.append(f"♻️ {actor} 的再生被抑制（{block}）。")

    if npc is not None:
        from backend.engine.recharge_rules import roll_recharge
        recharge_text = roll_recharge(state, actor, npc)
        if recharge_text:
            lines.append(recharge_text)
        if getattr(npc, "conditions", None):
            from backend.engine.condition_rules import (
                apply_condition_end_saves, apply_condition_tick_effects,
            )
            tick_lines = await apply_condition_tick_effects(
                state, npc.conditions, actor, is_player=False)
            lines.extend(tick_lines)
            npc.conditions, _save_lines = await apply_condition_end_saves(
                state, npc.conditions, actor, is_player=False)
            expired: list[str] = []
            kept: list[Any] = []
            for condition in npc.conditions:
                if isinstance(condition, dict):
                    rounds = int(condition.get("remaining_rounds") or 0)
                    if rounds > 0:
                        rounds -= 1
                        condition["remaining_rounds"] = rounds
                        if rounds == 0:
                            expired.append(str(condition.get("name") or "状态"))
                            continue
                kept.append(condition)
            npc.conditions = kept
            if expired:
                lines.append(f"⏳ {actor} 的状态结束：" + "、".join(expired))

    if not lines:
        return ""
    text = "\n".join(lines)
    await push_narrative_token(state, f"\n{text}\n")
    await push_event(state, "game_event", {
        "type": "turn_start_effect",
        "description": text,
        "extra": {"actor": actor},
    })
    return text
