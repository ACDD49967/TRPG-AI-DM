"""状态效果的增减与回合末递减（含 [系统强制-专注] 之类的提示）。

从 `backend/engine/character_state.py` 拆出；那边只保留 `_exec_update_state` 主处理器并再导出这些名字。
"""
from __future__ import annotations

from typing import Any

from backend.engine.character_normalize import _normalize_condition
from backend.engine.session import GameSessionState, push_event

def _update_conditions(state: GameSessionState, add: Any, remove: Any) -> dict:
    """增删状态效果；返回本次变更（供 applied 与 state_update 使用）。"""
    info = state.character_info
    conditions = [c for c in (info.get("conditions") or []) if isinstance(c, (dict, str))]
    removed: list[str] = []
    remove_names = remove if isinstance(remove, list) else ([remove] if remove else [])
    for raw in remove_names:
        target = str(raw.get("name") if isinstance(raw, dict) else raw).strip()
        if not target:
            continue
        before = len(conditions)
        conditions = [c for c in conditions if str(c.get("name") if isinstance(c, dict) else c) != target]
        if len(conditions) < before:
            removed.append(target)
    added: list[str] = []
    blocked: list[str] = []
    from backend.engine.condition_rules import condition_block_reason, player_condition_immunities
    immunities = player_condition_immunities(state)
    add_items = add if isinstance(add, list) else ([add] if add else [])
    for raw in add_items:
        condition = _normalize_condition(raw)
        if condition is None:
            continue
        reason = condition_block_reason(condition["name"], immunities)
        if reason:
            blocked.append(f"{condition['name']}（{reason}）")
            continue
        existing = next(
            (c for c in conditions if str(c.get("name") if isinstance(c, dict) else c) == condition["name"]),
            None,
        )
        if existing is None:
            conditions.append(condition)
            added.append(condition["name"])
        elif isinstance(existing, dict):
            # 同名状态再次施加：以新描述/回合数覆盖（例如中毒叠加持续时间）
            existing.update({k: v for k, v in condition.items() if v})
    info["conditions"] = conditions
    return {"added": added, "removed": removed, "blocked": blocked, "conditions": conditions}

async def tick_conditions(state: GameSessionState) -> None:
    """回合末递减有限时长的状态效果，并推送变更。"""
    info = state.character_info
    conditions = [c for c in (info.get("conditions") or []) if isinstance(c, dict)]
    if not conditions:
        return
    from backend.engine.condition_rules import apply_condition_tick_effects
    await apply_condition_tick_effects(
        state, conditions, str(getattr(state, "character_name", "") or "玩家"),
        is_player=True,
    )
    from backend.engine.condition_rules import apply_condition_end_saves
    conditions, _save_lines = await apply_condition_end_saves(
        state, conditions, str(getattr(state, "character_name", "") or "玩家"),
        is_player=True,
    )
    expired: list[str] = []
    kept: list[dict] = []
    for condition in conditions:
        rounds = int(condition.get("remaining_rounds") or 0)
        if rounds > 0:
            rounds -= 1
            condition["remaining_rounds"] = rounds
            if rounds == 0:
                # 限时状态到期：显式移除（0 表示"无持续回合/永久"，不能靠 0 判断）
                expired.append(str(condition.get("name") or "状态"))
                continue
        kept.append(condition)
    info["conditions"] = kept
    if expired:
        await push_event(state, "state_update", {"conditions": kept})
        await push_event(state, "game_event", {
            "type": "condition_expired",
            "description": "⏳ 状态结束：" + "、".join(expired),
        })
    else:
        await push_event(state, "state_update", {"conditions": kept})
