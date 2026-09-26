"""濒死与死亡流程：倒地、自动死亡豁免与死亡锁定。

从 `backend/engine/character_state.py` 拆出；那边只保留 `_exec_update_state` 主处理器并再导出这些名字。
"""
from __future__ import annotations

from typing import Any

from backend.engine.rules import DeathSaves
from backend.engine.session import GameSessionState, push_event
from backend.engine.tool_shims import _game_system


async def _exec_death_save(args: dict, state: Any) -> str:
    """惰性转发到 dm_agent（与 character_state 原来的 shim 一致，避免循环导入）。"""
    from backend.engine import dm_agent
    return await dm_agent._exec_death_save(args, state)

async def _handle_dying_transition(state: GameSessionState, hp_before: int, hp_after: int) -> None:
    """HP 归零时进入濒死流程。

    濒死规则此前只写在提示词里（F节），DM 忘了调用死亡豁免就没有任何后果；
    这里做代码级兜底：进入濒死、给玩家可见提示、并给下一轮注入强制提示。
    """
    if _game_system(state) not in ("dnd5e", "dnd4e"):
        return

    # 5e 专注：受伤必须掷体质豁免（DC = max(10, 伤害/2)）；昏迷会直接中断专注
    info = state.character_info
    concentration = info.get("concentration")
    if isinstance(concentration, dict) and concentration.get("spell"):
        if hp_after <= 0:
            from backend.engine.concentration import clear_concentration
            await clear_concentration(state, reason="昏迷")
        elif hp_after < hp_before:
            damage = hp_before - hp_after
            # 伤害后的专注豁免由后端掷（此前只发提示，DM 忘掷就永不断专注）
            from backend.engine.concentration import resolve_concentration_save
            outcome = await resolve_concentration_save(state, damage, reason="受到伤害")
            state.pending_system_hints = [
                h for h in state.pending_system_hints if not h.startswith("[系统强制-专注]")
            ]
            if outcome.get("rolled"):
                state.pending_system_hints.append(
                    f"[系统强制-专注] 你正在维持「{outcome['spell']}」，本回合受到 {damage} 点伤害："
                    f"{outcome['note']}。请据此叙述"
                    + ("，并说明法术效果已终止。" if outcome.get("success") is False else "。")
                )
    if hp_after > 0:
        if getattr(state, "dying", False):
            state.dying = False
            state.pending_system_hints = [
                hint for hint in state.pending_system_hints if not hint.startswith("[系统强制-濒死]")
            ]
        # 复活/被救回：解除死亡锁定（Revivify 之类的叙事由 DM 决定）
        state.character_dead = False
        return
    if hp_before <= 0 and getattr(state, "dying", False):
        return  # 已在濒死流程中，不重复触发
    if hp_before > 0:
        state._death_saves = DeathSaves()  # 首次倒地：豁免计数从零开始
    state.dying = True
    state.pending_system_hints = [
        hint for hint in state.pending_system_hints if not hint.startswith("[系统强制-濒死]")
    ]
    state.pending_system_hints.append(
        "[系统强制-濒死] 玩家当前 HP=0，已倒地昏迷：本轮必须调用 death_saving_throw 掷一次死亡豁免；"
        "昏迷期间不能行动、移动、施法或交谈，只能由他人施救或等待豁免结果。"
    )
    await push_event(state, "game_event", {
        "type": "dying",
        "description": "⚰️ 你倒下了——失去意识，无法行动。接下来每回合都要掷死亡豁免。",
    })

async def _maybe_auto_death_save(state: GameSessionState) -> str:
    """安全网：濒死回合若 DM 没掷豁免，回合末自动补掷一次，保证时钟推进。"""
    if not getattr(state, "dying", False):
        return ""
    ws = getattr(state, "world_state", None)
    current_turn = int(getattr(ws, "turn_count", 0) or 0)
    if getattr(state, "_death_save_turn", -1) == current_turn:
        return ""
    return await _exec_death_save({}, state)
