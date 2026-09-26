"""战斗状态快照：由世界状态刷新战斗标志与给前端的战斗面板数据。

从 `backend/engine/combat.py` 拆出；那边保留四个规则处理器并再导出这些名字。
"""
from __future__ import annotations

from backend.engine.combat_targets import _resolve_enemy_from_cards
from backend.engine.session import GameSessionState


from typing import Any

def _refresh_combat_state(state: GameSessionState) -> bool:
    """按世界状态刷新"是否处于战斗中"（**当前场景**仍有存活且敌对的单位）。

    `in_combat` 此前只被读取、从未设置，导致战斗中能休息、背景剧情会在打斗中推进。
    只统计当前场景，避免远处洞穴里的敌人让玩家在村里永远无法休息。
    """
    ws = getattr(state, "world_state", None)
    if ws is None:
        state.in_combat = False
        return False
    scene = getattr(ws, "scene", None)
    here = str(getattr(scene, "current_location", "") or "")
    visible = {str(n) for n in (getattr(scene, "visible_npcs_here", []) or [])}
    pending = getattr(state, "pending_regeneration", None)
    pending = {str(n).strip().lower() for n in pending} if isinstance(pending, (set, list, tuple)) else set()
    alive_hostiles = []
    for npc in (getattr(ws, "npcs", []) or []):
        if str(getattr(npc, "attitude", "")) != "敌对":
            continue
        name = str(getattr(npc, "name", "") or "")
        is_pending = name.strip().lower() in pending
        if not getattr(npc, "alive", True) and not is_pending:
            continue
        location = str(getattr(npc, "location", "") or "")
        if name in visible or (here and here != "未知" and location == here):
            alive_hostiles.append(npc)
    state.in_combat = bool(alive_hostiles)
    if state.in_combat:
        return True
    # 战斗结束：先攻表里也没有存活敌人时清空，下一次交战重新掷先攻
    from backend.engine import initiative
    tracker = initiative.tracker_for(state)
    if tracker is None or not any(c.side == "enemy" and c.alive for c in tracker.order):
        initiative.clear(state)
        # 战斗结束：战场态势（档位/掩体）随之失效，下一次交战重新登记
        from backend.engine import battlefield
        battlefield.clear(state)
    return state.in_combat

def _build_combat_snapshot(state: GameSessionState, names: list[str], target: str, target_hp: int) -> list[dict]:
    """为前端收集当前战斗中敌人的 HP 快照；未显式给出名单时收集当前场景所有存活敌对 NPC。"""
    pending = getattr(state, "pending_regeneration", None)
    pending = {str(n).strip().lower() for n in pending} if isinstance(pending, (set, list, tuple)) else set()
    if not names:
        names = []
        ws = getattr(state, "world_state", None)
        if ws is not None and getattr(ws, "scene", None):
            cur = ws.scene.current_location
            names = [
                n.name for n in ws.npcs
                if (getattr(n, "alive", True) or str(n.name).strip().lower() in pending)
                and n.attitude == "敌对"
                and (not cur or n.location == cur)
                and getattr(n, "discovered", True)
            ]
        if target and target not in names:
            names.append(target)
    out: list[dict] = []
    for nm in names:
        if not nm:
            continue
        stats = _resolve_enemy_from_cards(state, nm, {})
        hp = int(stats.get("e_hp", 0) or 0)
        if nm == target:
            hp = max(0, int(target_hp or 0))
        out.append({"name": nm, "hp": hp,
                    "pending_regen": str(nm).strip().lower() in pending})
    return out
