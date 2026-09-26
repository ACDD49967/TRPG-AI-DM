"""幸运兜底：COC 7e 的幸运消耗约束 + 5e「幸运」专长的长休重置。

与理智（`sanity_rules`）是同一类问题：幸运只写在提示词里——`rules_system` 的 COC 段
只说"可用于重掷或改变处境，由守密人酌情消耗"，代码路径对 `luck` 的变化不做任何校验：

1. 数值没有上限兜底。COC 7e 的幸运是 0-99 的百分制（初始 3d6×5），
   越界后 d100 比对会失真，超出的部分还会一直留在角色卡上；
2. 消耗没有语义约束。幸运只能 1:1 扣检定结果，且**不能**用于幸运检定本身与理智检定，
   DM 很容易把它当成"万能重掷"，甚至一次扣掉几十点；
3. 幸运归 0 之后没有任何提示，下一轮可能继续扣；
4. 5e「幸运」专长的 3 点幸运"每次长休重置"，此前从未被写回
   （`feats` 图鉴里的 `effect.luck_points` 是一条死数据）。

做法与濒死/理智一致：写回前收敛数值，变更后推一条玩家可见事件 + 一条给主 DM 的强制提示。
"""
from __future__ import annotations

from backend.engine.session import GameSessionState, push_event
from backend.engine.tool_shims import _game_system

LUCK_MIN = 0
LUCK_MAX_COC = 99
LUCKY_FEAT_POINTS = 3
_HINT_PREFIX = "[系统强制-幸运]"


def clamp_luck(state: GameSessionState, value: int) -> int:
    """按规则系统收敛幸运：COC 7e 是 0-99 的百分制，其他系统只保证非负。"""
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = LUCK_MIN
    if _game_system(state) == "coc":
        return max(LUCK_MIN, min(LUCK_MAX_COC, value))
    return max(LUCK_MIN, value)


def lucky_feat_points(state: GameSessionState) -> int:
    """5e「幸运」专长每次长休重置的点数；没有该专长返回 0。"""
    if _game_system(state) != "dnd5e":
        return 0
    from backend.engine.character_normalize import _has_feat_effect
    from backend.engine.feats import FEATS_LIST

    if not _has_feat_effect(state, "luck_points"):
        return 0
    for entry in FEATS_LIST:
        points = (entry.get("effect") or {}).get("luck_points")
        if points:
            return int(points)
    return LUCKY_FEAT_POINTS


def _replace_hint(state: GameSessionState, text: str) -> None:
    """同类提示只保留最新一条。"""
    existing = [h for h in (state.pending_system_hints or []) if not h.startswith(_HINT_PREFIX)]
    state.pending_system_hints = existing + [text]


async def handle_luck_change(
    state: GameSessionState, luck_before: int, luck_after: int,
) -> None:
    """幸运变化的规则兜底；非 COC 局直接返回（5e 的幸运点由长休重置，不在这里提示）。"""
    if _game_system(state) != "coc":
        return
    spent = max(0, int(luck_before) - int(luck_after))
    if spent <= 0:
        return
    remaining = max(0, int(luck_after))
    if remaining <= 0:
        _replace_hint(
            state,
            f"{_HINT_PREFIX} 本次消耗 {spent} 点幸运后已归零：本局不能再消耗幸运修正检定"
            "（COC 7e 的幸运只能靠成长结算或守密人奖励恢复）。",
        )
    else:
        _replace_hint(
            state,
            f"{_HINT_PREFIX} 消耗了 {spent} 点幸运（剩余 {remaining}）：COC 7e 的幸运"
            "按 1:1 从检定结果里扣，通常只能在掷骰后使用；不能用于幸运检定本身与理智检定。",
        )
    await push_event(state, "game_event", {
        "type": "luck_spent",
        "description": f"🍀 {state.character_name}消耗 {spent} 点幸运（剩余 {remaining}）。",
        "extra": {"luck_spent": spent, "luck": remaining},
    })


__all__ = [
    "clamp_luck", "lucky_feat_points", "handle_luck_change",
    "LUCK_MAX_COC", "LUCKY_FEAT_POINTS",
]
