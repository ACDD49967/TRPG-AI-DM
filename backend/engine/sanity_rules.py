"""COC 7e 理智：单次损失 ≥5 的临时疯狂风险、SAN 归 0 的永久疯狂。

理智规则此前只写在提示词里（`rules_system` 的 COC 段），后端对 SAN 变化不做任何反应：
DM 忘了掷智力检定、玩家 SAN 掉到 0 也没人管。这里做成代码级兜底——
与濒死流程（`character_dying._handle_dying_transition`）同一套做法：
推一条玩家可见事件 + 给主 DM 注入强制提示。
"""
from __future__ import annotations

from typing import Any

from backend.engine.session import GameSessionState, push_event
from backend.engine.tool_shims import _game_system

# CoC 7e：单次损失 ≥5 点理智 → 智力检定，失败进入临时疯狂
TEMP_INSANITY_THRESHOLD = 5
PERMANENT_FLAG = "permanent_insanity"
_HINT_PREFIX = "[系统强制-理智]"


def _replace_hint(state: GameSessionState, text: str) -> None:
    """同一类提示只保留最新一条，避免多轮累积。"""
    existing = [h for h in (state.pending_system_hints or []) if not h.startswith(_HINT_PREFIX)]
    state.pending_system_hints = existing + [text]


async def handle_sanity_change(
    state: GameSessionState, san_before: int, san_after: int,
) -> None:
    """SAN 变化的规则兜底；非 COC 局直接返回。"""
    if _game_system(state) != "coc":
        return
    info = state.character_info
    lost = max(0, int(san_before) - int(san_after))

    if int(san_after) <= 0:
        if info.get(PERMANENT_FLAG):
            return  # 已经疯了，不重复播报
        info[PERMANENT_FLAG] = True
        _replace_hint(
            state,
            f"{_HINT_PREFIX} 调查员的理智归零：按 COC 7e 进入永久疯狂。"
            "请描写不可逆的精神崩溃（执念或崩溃症状），并让角色退出调查。",
        )
        await push_event(state, "game_event", {
            "type": "insanity",
            "description": f"🧠 {state.character_name}的理智归零——永久疯狂。",
            "extra": {"permanent": True, "san_lost": lost, "san": 0},
        })
        return

    if lost >= TEMP_INSANITY_THRESHOLD:
        _replace_hint(
            state,
            f"{_HINT_PREFIX} 本次损失 {lost} 点理智（≥5）：按 COC 7e 必须掷一次智力(INT)检定；"
            "成功表示把这段记忆压抑下去，失败则进入临时疯狂"
            "（用 update_state 记录 conditions_add 与剩余回合，并在叙事里表现出来）。",
        )
        await push_event(state, "game_event", {
            "type": "sanity",
            "description": f"🧠 {state.character_name}受到 {lost} 点理智冲击。",
            "extra": {"san_lost": lost, "san": int(san_after), "temporary_risk": True},
        })


__all__ = ["handle_sanity_change", "TEMP_INSANITY_THRESHOLD", "PERMANENT_FLAG"]
