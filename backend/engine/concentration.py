"""5e 专注豁免：受伤时由后端掷体质豁免（DC = max(10, 伤害 // 2)）。

此前只想 DM 注入"[系统强制-专注]"提示，DM 忘了掷就永远不会断专注，
法术效果会一直挂着。这里改成后端直接结算：掷骰、写日志、失败即清除专注，
并把结果作为提示留给 DM 叙述。
"""
from __future__ import annotations

import random
from typing import Any

from backend.engine.session import push_event

_HINT_PREFIX = "[系统强制-专注]"


def concentration_dc(damage: Any) -> int:
    """专注豁免 DC：至少 10，伤害每 2 点 +1。"""
    return max(10, int(damage or 0) // 2)


def active_concentration(state: Any) -> dict | None:
    """当前正在专注的法术（没有则返回 None）。"""
    info = getattr(state, "character_info", {}) or {}
    conc = info.get("concentration")
    return conc if isinstance(conc, dict) and conc.get("spell") else None


def _drop_hint(state: Any) -> None:
    state.pending_system_hints = [
        h for h in state.pending_system_hints if not h.startswith(_HINT_PREFIX)
    ]


async def clear_concentration(state: Any, *, reason: str = "") -> str:
    """清除专注并推送状态更新；返回被中断的法术名。"""
    info = state.character_info
    conc = info.pop("concentration", None)
    spell = str((conc or {}).get("spell") or "专注法术")
    _drop_hint(state)
    await push_event(state, "state_update", {"concentration": None})
    await push_event(state, "game_event", {
        "type": "concentration_broken",
        "description": f"💥 专注被打断：「{spell}」的效果终止。",
        "extra": {"spell": spell, "reason": reason},
    })
    return spell


async def resolve_concentration_save(state: Any, damage: Any, *, reason: str = "") -> dict:
    """受伤后的专注豁免，返回结算明细。

    ``{"rolled": False}`` 表示当时没有在专注（或伤害为 0），不掷骰。
    """
    empty = {"rolled": False, "success": True, "dc": 0, "roll": 0, "modifier": 0,
             "spell": "", "note": ""}
    conc = active_concentration(state)
    if conc is None or int(damage or 0) <= 0:
        return empty

    from backend.engine.character_normalize import _has_feat_effect
    from backend.engine.player_damage import save_modifier

    spell = str(conc["spell"])
    dc = concentration_dc(damage)
    mod, source = save_modifier(state, "con")
    advantage = _has_feat_effect(state, "concentration_advantage")
    rolls = [random.randint(1, 20)]
    if advantage:
        rolls.append(random.randint(1, 20))
    roll = max(rolls)
    total = roll + mod
    success = roll == 20 or (roll != 1 and total >= dc)

    event = {"skill": f"{spell} 专注·体质豁免", "dc": dc,
             "roll": roll, "modifier": mod, "source": source,
             "result": "成功" if success else "失败"}
    if advantage:
        event.update({"advantage": "advantage", "advantage_note": "战地施法者"})
    await push_event(state, "dice_roll", event)

    note = (f"专注豁免 DC {dc}：d20={roll}{'+' if mod >= 0 else ''}{mod}={total}"
            f"{'（优势）' if advantage else ''} → {'维持专注' if success else '专注被打断'}")
    if not success:
        await clear_concentration(state, reason=reason or "受到伤害")
    return {"rolled": True, "success": success, "dc": dc, "roll": roll,
            "modifier": mod, "spell": spell, "note": note}


# ── NPC 侧（怪物施法者）────────────────────────────────────────
# 玩家侧的专注存在 character_info["concentration"]；NPC 侧存在 NpcEntry.concentration。

def npc_concentration(npc: Any) -> str:
    return str(getattr(npc, "concentration", "") or "")


async def apply_npc_concentration_change(state: Any, npc: Any, field: str, value: Any) -> str:
    """adjust_npc 的 concentration / concentration_clear 分支。"""
    name = str(getattr(npc, "name", "") or "NPC")
    previous = npc_concentration(npc)
    if field == "concentration_clear":
        npc.concentration = ""
        return f"✅ {name} 专注已清除" + (f"（原：{previous}）" if previous else "")
    spell = str(value or "").strip()
    if not spell:
        return "⚠ concentration 需要 value（法术名）"
    npc.concentration = spell
    return f"{name} 正在专注：{spell}"


async def handle_npc_damage(state: Any, npc: Any, damage: Any) -> dict:
    """NPC 受伤后的专注结算：倒地直接中断，否则掷体质豁免。"""
    spell = npc_concentration(npc)
    empty = {"rolled": False, "success": True, "dc": 0, "spell": spell, "note": ""}
    if not spell or int(damage or 0) <= 0:
        return empty

    name = str(getattr(npc, "name", "") or "NPC")
    if int(getattr(npc, "hp", 0) or 0) <= 0:
        npc.concentration = ""
        await push_event(state, "game_event", {
            "type": "concentration_broken",
            "description": f"💥 {name} 倒下，「{spell}」的专注随之终止。",
            "extra": {"spell": spell, "reason": "倒地"},
        })
        return {"rolled": False, "success": False, "dc": 0, "spell": spell,
                "note": f"{name} 倒地，专注中断"}

    from backend.engine.damage_rules import creature_save_modifier

    dc = concentration_dc(damage)
    mod, source = creature_save_modifier(npc, {}, "con")
    roll = random.randint(1, 20)
    total = roll + mod
    success = roll == 20 or (roll != 1 and total >= dc)
    await push_event(state, "dice_roll", {
        "skill": f"{name} {spell}专注·体质豁免", "dc": dc,
        "roll": roll, "modifier": mod, "source": source,
        "result": "成功" if success else "失败",
    })
    note = (f"{name} 专注豁免 DC {dc}：d20={roll}{'+' if mod >= 0 else ''}{mod}={total}"
            f" → {'维持专注' if success else '专注被打断'}")
    if not success:
        npc.concentration = ""
        await push_event(state, "game_event", {
            "type": "concentration_broken",
            "description": f"💥 {name} 的专注被打断：「{spell}」的效果终止。",
            "extra": {"spell": spell, "reason": "受到伤害"},
        })
    return {"rolled": True, "success": success, "dc": dc, "spell": spell, "note": note}
