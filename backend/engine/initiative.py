"""先攻表门面：建立/同步/推进战斗轮，并把"谁还没动"变成给 DM 的系统提示。

规则模型（Combatant / InitiativeTracker / 加值计算）在 `initiative_model`；
这里只做会话状态编排，并再导出模型名，`from backend.engine.initiative import ...` 全部照旧。
"""
from __future__ import annotations

from typing import Any, Iterable

from backend.engine.initiative_model import (  # noqa: F401
    HINT_PREFIX, Combatant, InitiativeTracker, _RNG, _MULTI_TURN_PATTERN, _sort_key,
    dex_modifier, normalize_key, roll_initiative, turns_per_round_from_traits,
)


def tracker_for(state: Any) -> InitiativeTracker | None:
    tracker = getattr(state, "initiative", None)
    return tracker if isinstance(tracker, InitiativeTracker) else None


def set_tracker(state: Any, tracker: InitiativeTracker | None) -> None:
    try:
        state.initiative = tracker
    except Exception:
        pass


def clear(state: Any) -> None:
    """战斗结束/角色死亡时清空，下一次交战重新掷先攻。"""
    set_tracker(state, None)


def build_roster(state: Any, extra_names: Iterable[str] = ()) -> list[Combatant]:
    """从会话与当前场景收集参战单位（玩家 + 场上存活敌对 NPC + 显式点名的敌人）。"""
    info = getattr(state, "character_info", {}) or {}
    player_name = str(getattr(state, "character_name", "") or "玩家")
    player_hp = int(info.get("hp", 0) or 0)
    player_max = int(info.get("max_hp", player_hp) or player_hp)
    from backend.engine.feat_effects import initiative_bonus as feat_initiative_bonus

    roster = [Combatant(
        name=player_name, side="player", dex_mod=dex_modifier(info.get("attributes")),
        hp=player_hp, max_hp=player_max, alive=not getattr(state, "character_dead", False),
        initiative_bonus=feat_initiative_bonus(state),
        surprise_immune=_player_surprise_immune(state),
    )]

    ws = getattr(state, "world_state", None)
    scene = getattr(ws, "scene", None) if ws is not None else None
    here = str(getattr(scene, "current_location", "") or "")
    visible = {normalize_key(n) for n in (getattr(scene, "visible_npcs_here", []) or [])}
    wanted = {normalize_key(n) for n in extra_names if n}

    for npc in (getattr(ws, "npcs", []) or []):
        name = str(getattr(npc, "name", "") or "")
        if not name or str(getattr(npc, "attitude", "")) != "敌对":
            continue
        key = normalize_key(name)
        location = str(getattr(npc, "location", "") or "")
        on_scene = key in visible or key in wanted or (here and here != "未知" and location == here)
        if not on_scene:
            continue
        traits = list(getattr(npc, "traits", []) or [])
        roster.append(Combatant(
            name=name, side="enemy", dex_mod=dex_modifier(getattr(npc, "attributes", {})),
            hp=int(getattr(npc, "hp", 0) or 0),
            max_hp=int(getattr(npc, "max_hp", 0) or 0),
            alive=bool(getattr(npc, "alive", True)) and int(getattr(npc, "hp", 0) or 0) > 0,
            turns_per_round=turns_per_round_from_traits(traits),
            note="多重回合" if turns_per_round_from_traits(traits) > 1 else "",
            surprise_immune=_traits_surprise_immune(traits),
        ))
    return roster


def _player_surprise_immune(state: Any) -> bool:
    """「警觉」等特性让玩家不会被突袭。"""
    try:
        from backend.engine.character_state import _has_feat_effect
        return bool(_has_feat_effect(state, "cannot_be_surprised"))
    except Exception:
        return False


def _traits_surprise_immune(traits: Iterable[Any]) -> bool:
    text = " ".join(str(t) for t in (traits or [])).lower()
    return any(word in text for word in ("cannot be surprised", "cannot_be_surprised",
                                         "无法被突袭", "不会被突袭", "警觉"))


def start(state: Any, roster: list[Combatant] | None = None, rng: Any = None) -> InitiativeTracker:
    """建立先攻表：给名单里每个单位掷先攻并排序。"""
    combatants = roster if roster is not None else build_roster(state)
    for c in combatants:
        if not c.initiative:
            c.initiative = roll_initiative(c.dex_mod + int(c.initiative_bonus or 0), rng)
    tracker = InitiativeTracker(round=1, order=combatants)
    tracker.order.sort(key=_sort_key)
    set_tracker(state, tracker)
    return tracker


def ensure(state: Any, extra_names: Iterable[str] = (), rng: Any = None,
           surprise_side: str = "") -> InitiativeTracker | None:
    """战斗中确保先攻表存在：已有则同步名单，没有则新建。非战斗（无敌人）返回 None。"""
    tracker = tracker_for(state)
    roster = build_roster(state, extra_names)
    has_enemy = any(c.side == "enemy" for c in roster)
    if not has_enemy:
        return None
    if tracker is None:
        tracker = start(state, roster, rng)
    else:
        tracker.sync(roster)
    if surprise_side:
        tracker.mark_surprised(surprise_side)
    return tracker


def begin_player_turn(state: Any) -> str:
    """玩家提交新行动 = 进入新的战斗轮；返回注入给 DM 的提示（非战斗返回空串）。"""
    tracker = tracker_for(state)
    if tracker is None:
        return ""
    tracker.begin_round()
    return tracker.summary()


def hint(state: Any) -> str:
    tracker = tracker_for(state)
    return tracker.summary() if tracker is not None else ""


def payload(state: Any) -> dict | None:
    tracker = tracker_for(state)
    return tracker.payload() if tracker is not None else None


def consume(state: Any, actor: str, source: str = "", requested: int = 0):
    """先攻表视角的回合消耗；无表/未知单位时放行（由行动经济账本决定）。"""
    tracker = tracker_for(state)
    if tracker is None:
        return True, "", False
    return tracker.consume(actor, source, requested)


def sync_defeat(state: Any, name: str) -> None:
    tracker = tracker_for(state)
    if tracker is not None:
        tracker.mark_defeated(name)


def sync_hp(state: Any, name: str, hp: int, max_hp: int = 0) -> None:
    tracker = tracker_for(state)
    if tracker is not None:
        tracker.update_hp(name, hp, max_hp)


def revive(state: Any, name: str, hp: int, max_hp: int = 0) -> None:
    """再生复活：HP 为正时恢复 alive，并把它当作本轮可行动单位。"""
    tracker = tracker_for(state)
    if tracker is None:
        return
    c = tracker.find(name)
    if c is None:
        return
    c.hp = max(1, int(hp))
    c.max_hp = max(int(max_hp or 0), c.max_hp)
    c.alive = True
    c.turns_used = 0
    c.surprised = False


def grant_turns(state: Any, name: str, turns: int, note: str = "") -> int:
    tracker = tracker_for(state)
    return tracker.grant_turns(name, turns, note) if tracker is not None else 0


def replace_hint(state: Any, text: str) -> None:
    """把先攻提示写进待注入队列（替换同前缀旧提示，避免堆积）。"""
    if not text:
        return
    hints = getattr(state, "pending_system_hints", None)
    if hints is None:
        return
    kept = [h for h in hints if not str(h).startswith(HINT_PREFIX)]
    kept.append(text)
    state.pending_system_hints = kept
