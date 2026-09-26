"""传奇抗性：解析每日次数并把一次失败豁免改为成功。"""
from __future__ import annotations

import re
from typing import Any

_PATTERN = re.compile(
    r"legendary\s+resistance(?:\s*\((\d+)\s*/\s*day\))?|传奇抗性(?:[（(](\d+)\s*次)?",
    re.I,
)


def _traits_text(npc: Any) -> str:
    return " ".join(str(t) for t in (getattr(npc, "traits", []) or []))


def parse_legendary_resistance(npc: Any) -> int:
    """返回每日上限；无传奇抗性返回 0，未写次数时按 3 次。"""
    match = _PATTERN.search(_traits_text(npc))
    if not match:
        return 0
    return int(match.group(1) or match.group(2) or 3)


def legendary_resistance_remaining(npc: Any) -> int:
    """返回剩余次数；首次查询时从特性初始化。"""
    maximum = int(getattr(npc, "legendary_resistance_max", 0) or 0)
    remaining = int(getattr(npc, "legendary_resistance", 0) or 0)
    if maximum <= 0:
        maximum = parse_legendary_resistance(npc)
        if maximum > 0:
            try:
                npc.legendary_resistance_max = maximum
                npc.legendary_resistance = maximum
            except Exception:
                pass
            remaining = maximum
    return max(0, remaining)


def spend_legendary_resistance(npc: Any) -> bool:
    """消耗一次传奇抗性；没有剩余返回 False。"""
    remaining = legendary_resistance_remaining(npc)
    if remaining <= 0:
        return False
    try:
        npc.legendary_resistance = remaining - 1
    except Exception:
        return False
    return True
