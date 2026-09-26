"""5e 力竭表的机械后果：4 级生命上限减半、6 级死亡。

1 级（检定劣势）与 3 级（攻击/豁免劣势）在 `dice_tools` 与 `combat_save_damage`
里已经落地；这里补上剩下两条**改数值**的，让能力表不再是"只写在提示词里"。

2 级（移速减半）与 5 级（移速归零）在本项目里没有数值意义：位置用 battlefield 的
档位（engaged/near/far/out）抽象，不按尺数计算，所以这两级只保留提示文案，
不改任何字段——把原因写在这里，避免以后被当成漏实现。
"""
from __future__ import annotations

from typing import Any

_HINT_PREFIX = "[系统强制-力竭]"
_BASE_MAX_HP_KEY = "_base_max_hp"


def apply_exhaustion_effects(state: Any, info: dict) -> dict:
    """按当前力竭等级调整生命上限与死亡状态；返回要并入 applied 的字段。

    幂等：力竭降回 4 级以下时会恢复原始生命上限，不会连着减半两次。
    """
    level = max(0, min(6, int(info.get("exhaustion", 0) or 0)))
    applied: dict = {}
    base = int(info.get(_BASE_MAX_HP_KEY) or 0)
    current_max = int(info.get("max_hp") or 0)

    if level >= 4:
        if base <= 0:                      # 首次减半：记下原始上限，便于恢复
            base = current_max or 1
            info[_BASE_MAX_HP_KEY] = base
        halved = max(1, base // 2)
        if current_max != halved:
            info["max_hp"] = halved
            applied["max_hp"] = halved
        if int(info.get("hp") or 0) > halved:
            info["hp"] = halved
            applied["hp"] = halved
            applied["hp_capped_by_exhaustion"] = True
    elif base > 0:                          # 力竭降到 4 级以下：恢复原始上限
        if current_max != base:
            info["max_hp"] = base
            applied["max_hp"] = base
        info.pop(_BASE_MAX_HP_KEY, None)

    if level >= 6:
        info["hp"] = 0
        applied.setdefault("hp", 0)
        state.character_dead = True
        state.dying = True
        applied["dead"] = True

    hints = [h for h in (getattr(state, "pending_system_hints", []) or [])
             if not h.startswith(_HINT_PREFIX)]
    if level >= 6:
        hints.append(f"{_HINT_PREFIX} 力竭 6 级：角色死亡。请在叙事中交代结局。")
    elif level >= 4:
        hints.append(f"{_HINT_PREFIX} 力竭 {level} 级：生命上限减半"
                     f"（当前 {info.get('hp')}/{info.get('max_hp')}），长休可减轻力竭。")
    state.pending_system_hints = hints
    return applied
