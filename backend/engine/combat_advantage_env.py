"""优势/劣势的环境来源：群体战术与阳光敏感。

从 `combat_advantage` 拆出（那边只留裁定逻辑并再导出 `in_sunlight`，
`turn_start_effects` 的 import 不变）。依赖 `combat_advantage_base` 的文本工具。
"""
from __future__ import annotations

from typing import Any

from backend.engine.combat_advantage_base import _has, _norm

def _pack_tactics_source(state: Any, enemy: str, traits_text: str) -> str:
    """群体战术：攻击者有此特性，且另一名敌对盟友正与目标缠斗时给优势。"""
    if not _has(_norm(traits_text), "pack tactics", "群体战术", "群战", "包抄"):
        return ""
    from backend.engine import battlefield

    target_band = battlefield.band_of(state, "你")
    if not target_band:
        target_band = battlefield.band_of(state, str(getattr(state, "character_name", "") or ""))
    if target_band != "engaged":
        return ""
    world = getattr(state, "world_state", None)
    for npc in (getattr(world, "npcs", []) or []):
        name = str(getattr(npc, "name", "") or "")
        if not name or name == enemy or not bool(getattr(npc, "alive", True)):
            continue
        if "敌对" not in str(getattr(npc, "attitude", "") or ""):
            continue
        if battlefield.band_of(state, name) == "engaged":
            return f"群体战术（{name}与目标缠斗）"
    return ""


def _in_sunlight(state: Any) -> bool:
    """从场景时间与天气保守推断是否处于阳光环境；没有结构化记录时不猜。"""
    world = getattr(state, "world_state", None)
    scene = getattr(world, "scene", None)
    if scene is None:
        return False
    time_text = _norm(getattr(scene, "current_time", ""))
    weather = _norm(getattr(scene, "weather", ""))
    daylight = _has(time_text, "白天", "上午", "中午", "正午", "下午", "清晨", "黎明",
                    "morning", "noon", "afternoon", "daytime")
    sunny = _has(weather, "晴", "阳光", "烈日", "无云", "日照", "clear", "sunny")
    return daylight and sunny


def in_sunlight(state: Any) -> bool:
    """公开查询：场景时间/天气是否构成阳光环境（不含未记录猜测）。"""
    return _in_sunlight(state)


def _sunlight_disadvantage(state: Any, traits_text: str) -> str:
    """阳光敏感/阳光弱点：特性 + 结构化场景光照都成立才给攻击劣势。"""
    traits = _norm(traits_text)
    if not _has(traits, "sunlight sensitivity", "sunlight weakness", "阳光敏感", "阳光弱点"):
        return ""
    if not _in_sunlight(state):
        return ""
    scene = getattr(getattr(state, "world_state", None), "scene", None)
    weather = str(getattr(scene, "weather", "") or "")
    return f"阳光敏感（{weather}）"
