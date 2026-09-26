"""生命阈值规则：4e 的「血竭（Bloodied）」与 CoC 7e 的「重伤（Major Wound）」。

两条都是**后端应该记账、但此前只写在规则文本里**的东西：

- `rules_4e` 写着"HP 降到一半以下进入血竭"，代码里没有任何地方标记或提示；
- CoC 段写着"归 0 时重伤昏迷"，而 7e 的判定条件是**单次伤害 ≥ 一半最大 HP**，
  DM 只能凭记忆判断，玩家也看不到为什么突然被打晕。

做法与理智/幸运一致：改状态 → 推玩家可见事件 → 给主 DM 一条强制提示（真正掷骰/判定仍由 DM 做）。
"""
from __future__ import annotations

from backend.engine.session import GameSessionState, push_event
from backend.engine.tool_shims import _game_system

BLOODIED_FLAG = "bloodied"
_BLOODIED_HINT = "[系统强制-血竭]"
_WOUND_HINT = "[系统强制-重伤]"


def _replace_hint(state: GameSessionState, prefix: str, text: str) -> None:
    existing = [h for h in (state.pending_system_hints or []) if not h.startswith(prefix)]
    state.pending_system_hints = existing + [text]


async def handle_hp_threshold(
    state: GameSessionState, hp_before: int, hp_after: int, damage: int = 0,
) -> None:
    """HP 变化后的阈值兜底：4e 血竭标记；CoC 单次重伤/致死提示。"""
    info = state.character_info
    system = _game_system(state)
    try:
        max_hp = int(info.get("max_hp", 0) or 0)
    except (TypeError, ValueError):
        max_hp = 0

    if system == "dnd4e" and max_hp > 0:
        half = max_hp // 2
        was = bool(info.get(BLOODIED_FLAG)) or (0 < int(hp_before) <= half)
        now = 0 < int(hp_after) <= half
        if now and not was:
            info[BLOODIED_FLAG] = True
            _replace_hint(
                state,
                _BLOODIED_HINT,
                f"{_BLOODIED_HINT} 生命值 {hp_after}/{max_hp}，已进入**血竭**状态："
                "按 4e 规则描写明显的踉跄/挂彩，并注意血竭相关的威能与效果（部分能力对血竭目标额外生效）。",
            )
            await push_event(state, "game_event", {
                "type": "bloodied",
                "description": f"🩸 {state.character_name}进入血竭（{hp_after}/{max_hp}）。",
                "extra": {"hp": int(hp_after), "max_hp": max_hp, "bloodied": True},
            })
            # 前端状态也要知道：4e 角色卡会显示「血竭」标记
            await push_event(state, "state_update", {BLOODIED_FLAG: True})
        elif was and not now and int(hp_after) > half:
            info[BLOODIED_FLAG] = False
            await push_event(state, "game_event", {
                "type": "bloodied_cleared",
                "description": f"💚 {state.character_name}脱离血竭（{hp_after}/{max_hp}）。",
                "extra": {"hp": int(hp_after), "max_hp": max_hp, "bloodied": False},
            })
            await push_event(state, "state_update", {BLOODIED_FLAG: False})
        return

    if system == "coc" and max_hp > 0 and damage > 0:
        half = max(1, (max_hp + 1) // 2)
        if damage >= max_hp:
            _replace_hint(
                state,
                _WOUND_HINT,
                f"{_WOUND_HINT} 单次受到 {damage} 点伤害（≥ 最大生命 {max_hp}）："
                "按 COC 7e 这是致命伤——调查员当场死亡或濒死，请立刻结算死亡/最后的挣扎，"
                "不要描写成普通昏迷后继续行动。",
            )
            await push_event(state, "game_event", {
                "type": "major_wound",
                "description": f"💀 {state.character_name}遭受致命伤（{damage} ≥ {max_hp}）。",
                "extra": {"damage": damage, "max_hp": max_hp, "fatal": True},
            })
        elif damage >= half:
            _replace_hint(
                state,
                _WOUND_HINT,
                f"{_WOUND_HINT} 单次受到 {damage} 点伤害（≥ 最大生命的一半 {half}）："
                "按 COC 7e 属于**重伤**——立刻倒地、掉落手中物品，并掷体质(CON)检定；"
                "失败则昏迷（用 update_state 记录 conditions_add）。",
            )
            await push_event(state, "game_event", {
                "type": "major_wound",
                "description": f"🩸 {state.character_name}受到重伤（{damage} 点，最大生命 {max_hp}）。",
                "extra": {"damage": damage, "max_hp": max_hp, "fatal": False},
            })


__all__ = ["handle_hp_threshold", "BLOODIED_FLAG"]
