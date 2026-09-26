"""光照等级与视觉：明亮 / 微光 / 黑暗，以及黑暗视觉、微光视觉。

此前只有"从时间和天气猜是不是阳光"（`combat_advantage_env.in_sunlight`），没有任何
结构化的光照字段，于是"洞里黑不黑""火把照到哪"全靠 DM 口头描述——可它直接决定
攻击优势与潜行能不能藏。这里把光照做成场景的一等字段，并按 5e 给它后果：

- **黑暗**：没有黑暗视觉的生物等于看不见 → 它攻击有劣势，别人打它有优势；
  别人也看不见它，所以它可以直接藏起来（不必再掷隐匿）。
- **微光**：依赖视觉的察觉检定有劣势；被动察觉按 -5 记（5e 的优劣势±5）。
- **黑暗视觉**：把黑暗当微光看；**微光视觉**（4e）把微光当明亮看。

场景没写光照时不猜（返回空串）——宁可退回旧行为，也不要凭空给玩家加减值。
"""
from __future__ import annotations

from typing import Any

BRIGHT = "bright"
DIM = "dim"
DARK = "dark"

_SYNONYMS = {
    BRIGHT: ("bright", "明亮", "日光", "白天", "白昼", "阳光", "火把", "篝火", "灯下", "光明"),
    DIM: ("dim", "微光", "昏暗", "黄昏", "黎明", "拂晓", "暮色", "月光", "晨光", "阴天"),
    DARK: ("dark", "darkness", "黑暗", "漆黑", "无光", "深夜", "午夜", "夜里", "入夜", "夜晚"),
}
_DARKVISION = ("darkvision", "黑暗视觉", "黑暗视界", "幽暗视觉")
_LOW_LIGHT = ("low-light vision", "low light vision", "微光视觉", "昏暗视觉")


def _flatten(value: Any, parts: list[str]) -> None:
    if isinstance(value, str):
        if value.strip():
            parts.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            _flatten(item, parts)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _flatten(item, parts)


def normalize_light(value: Any) -> str:
    """把 DM 的自由写法归一成 bright/dim/dark；认不出来就返回空串（不猜）。"""
    text = str(value or "").strip().lower()
    if not text:
        return ""
    for level, words in _SYNONYMS.items():
        if any(word in text for word in words):
            return level
    return ""


def _time_light(state: Any) -> str:
    """没有显式光照时的保守推断：只认明确的时间写法。"""
    world = getattr(state, "world_state", None)
    scene = getattr(world, "scene", None)
    time_text = str(getattr(scene, "current_time", "") or "").strip().lower()
    return normalize_light(time_text)


def scene_light(state: Any) -> str:
    """场景光照：显式字段优先，其次按时间保守推断；都没有则空串。"""
    world = getattr(state, "world_state", None)
    scene = getattr(world, "scene", None)
    explicit = normalize_light(getattr(scene, "light", "") if scene is not None else "")
    return explicit or _time_light(state)


def _traits_text(state: Any, name: str) -> str:
    """把目标卡上可能有视觉特性的文本拼起来（玩家看角色卡，NPC 看简易卡）。"""
    from backend.engine.player_damage import is_player_name

    if name is not None and not isinstance(name, str):
        # 直接传了 NPC 对象时也认（调用方图省事）
        npc_name = str(getattr(name, "name", "") or "")
        name = npc_name
    target = str(name or "").strip()
    if target and is_player_name(state, target):
        info = getattr(state, "character_info", {}) or {}
        parts: list[str] = []
        for key in ("race_traits", "species_traits", "class_proficiencies", "feats",
                    "damage_traits_notes", "senses"):
            _flatten(info.get(key), parts)
        return " ".join(parts).lower()
    world = getattr(state, "world_state", None)
    npc = world.get_npc(target) if world is not None else None
    if npc is None:
        return ""
    parts = []
    for value in (getattr(npc, "traits", None) or [], getattr(npc, "notes", "") or "",
                  getattr(npc, "appearance", "") or ""):
        _flatten(value, parts)
    return " ".join(parts).lower()


def vision_kind(state: Any, name: str) -> str:
    """目标的视觉：darkvision / low_light / 空串（普通视觉）。"""
    text = _traits_text(state, name)
    if not text:
        return ""
    if any(word in text for word in _DARKVISION):
        return "darkvision"
    if any(word in text for word in _LOW_LIGHT):
        return "low_light"
    return ""


def effective_light(state: Any, name: str) -> str:
    """目标感知到的光照（把黑暗视觉/微光视觉算进去）。"""
    light = scene_light(state)
    if not light:
        return ""
    kind = vision_kind(state, name)
    if kind == "darkvision":
        return DIM if light == DARK else BRIGHT
    if kind == "low_light" and light == DIM:
        return BRIGHT
    return light


def can_see(state: Any, name: str) -> bool:
    """目标在当前光照下是否还能看见（黑暗且无黑暗视觉 → 看不见）。"""
    return effective_light(state, name) != DARK


def perception_disadvantage(state: Any, name: str) -> str:
    """依赖视觉的察觉检定劣势来源（微光/黑暗）；没有则空串。"""
    light = effective_light(state, name)
    if light == DARK:
        return "黑暗（看不见）"
    if light == DIM:
        return "微光（依赖视觉）"
    return ""


def passive_perception_penalty(state: Any, name: str) -> int:
    """被动察觉的惩罚：依赖视觉的察觉在微光下有劣势 → 按 5e 记 -5。"""
    return -5 if effective_light(state, name) in (DIM, DARK) else 0


def visibility_reasons(state: Any, attacker: str, target: str) -> tuple[list[str], list[str]]:
    """按光照给出攻击的优势/劣势来源（(优势, 劣势) 两个列表）。

    - 攻击者看不见（黑暗且无黑暗视觉）→ 劣势；
    - 目标看不见攻击者 → 优势（相当于"未被看见的攻击者"）。
    """
    advantages: list[str] = []
    disadvantages: list[str] = []
    if not scene_light(state):
        return advantages, disadvantages
    if not can_see(state, attacker):
        disadvantages.append("黑暗中看不见目标")
    if not can_see(state, target):
        advantages.append("目标身处黑暗")
    return advantages, disadvantages
