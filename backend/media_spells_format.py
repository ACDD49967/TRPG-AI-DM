"""法术条目格式化：5etools 标签清洗与施法时间/距离/成分/持续时间的可读化。

从 backend/media_spells 拆出；这些函数只做纯文本转换，不碰存储。
"""
from __future__ import annotations

import re
from typing import Any

_DND5_ENTRY_RE = re.compile(r"\{@(?:damage|dice|hit|chance)\s+([^}]+)\}")

_DND5_SPELL_RE = re.compile(r"\{@spell\s+([^}]+)\}")



def _entries_to_text(entries: Any) -> str:
    """把 5etools entries 转为纯文本，去掉 @ 标签但保留数值。"""
    if isinstance(entries, str):
        return entries
    parts: list[str] = []

    def walk(node: Any):
        if isinstance(node, str):
            parts.append(node)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            if node.get("type") == "entries":
                walk(node.get("entries"))
            elif node.get("type") == "list":
                for item in node.get("items", []):
                    parts.append("· ")
                    walk(item)
                    parts.append("；")
            elif node.get("type") == "table":
                parts.append("（见表）")
            else:
                for v in node.values():
                    walk(v)

    walk(entries)
    text = " ".join("".join(parts).split())
    text = _DND5_ENTRY_RE.sub(lambda m: m.group(1), text)
    text = _DND5_SPELL_RE.sub(lambda m: m.group(1), text)
    text = re.sub(r"\{@[a-z]+\s+([^}]+)\}", lambda m: m.group(1), text)
    return text[:2000]



def _fmt_time(data: Any) -> str:
    try:
        if isinstance(data, list) and data:
            t = data[0]
            n = t.get("number", 1)
            unit = str(t.get("unit", "action"))
            unit_cn = {"action": "动作", "bonus": "附赠动作", "reaction": "反应",
                       "minute": "分钟", "hour": "小时", "instantaneous": "立即"}.get(unit, unit)
            return f"{n} {unit_cn}"
    except Exception:
        pass
    return "1 动作"



def _fmt_range(data: Any) -> str:
    try:
        if isinstance(data, dict):
            rtype = str(data.get("type", ""))
            if rtype == "self":
                return "自身"
            if rtype == "touch":
                return "触及"
            if rtype == "point":
                dist = data.get("distance", {})
                amount = dist.get("amount", "")
                unit = str(dist.get("type", "feet"))
                return f"{amount} {'尺' if unit == 'feet' else unit}"
    except Exception:
        pass
    return "自身"



def _fmt_components(data: Any) -> str:
    try:
        if not isinstance(data, dict):
            return ""
        parts = []
        if data.get("v"):
            parts.append("V")
        if data.get("s"):
            parts.append("S")
        mat = data.get("m")
        if mat:
            text = _entries_to_text(mat.get("text", "")) if isinstance(mat, dict) else str(mat)
            parts.append(f"M（{text}）")
        return "、".join(parts)
    except Exception:
        return ""



def _fmt_duration(data: Any) -> str:
    try:
        if isinstance(data, list) and data:
            t = data[0]
            conc = "专注，至多 " if t.get("concentration") else ""
            rtype = str(t.get("type", ""))
            if rtype == "instant":
                return "立即"
            dur = t.get("duration", {})
            n = dur.get("amount", "")
            unit = str(dur.get("type", "minute"))
            unit_cn = {"minute": "分钟", "hour": "小时", "round": "轮", "day": "日"}.get(unit, unit)
            return f"{conc}{n} {unit_cn}".strip()
    except Exception:
        pass
    return "立即"
