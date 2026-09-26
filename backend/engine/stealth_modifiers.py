"""潜行的数值与观察者挑选：隐匿加值、护甲劣势、被动察觉比对。

从 `stealth_rules` 拆出（那边只留判定流程），`stealth_rules` 再导出这些名字，
外部与测试的 import 面不变。
"""
from __future__ import annotations

from typing import Any

from backend.engine.combat_advantage_base import _has, _norm
from backend.engine.perception_rules import creature_passive_perception, proficiency_bonus

# 5e 中会使隐匿检定劣势的护甲（链甲衫等不在此列，故排除"衫/shirt"）
_ARMOR_WORDS = ("板甲", "半身板甲", "锁子甲", "链甲", "环甲", "鳞甲", "板条甲", "重甲",
                "plate", "chain mail", "ring mail", "scale mail", "splint")
_ARMOR_EXCEPTIONS = ("衫", "shirt")


def stealth_modifier(state: Any) -> int:
    """玩家隐匿加值：敏捷调整值 + 隐匿/潜行熟练。"""
    from backend.engine.damage_rules import ability_modifier

    info = getattr(state, "character_info", {}) or {}
    mod = ability_modifier((info.get("attributes") or {}).get("dex", 10))
    for skill in (info.get("skill_proficiencies") or []):
        if _has(_norm(skill), "隐匿", "潜行", "stealth"):
            return mod + proficiency_bonus(state)
    return mod


def creature_stealth_modifier(npc: Any) -> int:
    """NPC 隐匿加值：用简易卡的敏捷与技能近似（生物卡没有单独的隐匿加值时）。"""
    from backend.engine.damage_rules import ability_modifier
    from backend.engine.rules_5e import get_dnd5_proficiency_bonus

    if npc is None:
        return 0
    attributes = getattr(npc, "attributes", None) or {}
    mod = ability_modifier(attributes.get("dex", 10))
    for skill in (getattr(npc, "skills", None) or []):
        if _has(_norm(skill), "隐匿", "潜行", "stealth"):
            try:
                level = int(getattr(npc, "level", 1) or 1)
            except (TypeError, ValueError):
                level = 1
            return mod + get_dnd5_proficiency_bonus(level)
    return mod


def armor_disadvantage(state: Any) -> str:
    """身着会给隐匿劣势的护甲时返回说明（如「身着链甲」），否则空串。"""
    info = getattr(state, "character_info", {}) or {}
    inventory = info.get("inventory")
    items = (inventory or {}).get("items", []) if isinstance(inventory, dict) else []
    for item in items:
        if not isinstance(item, dict) or not item.get("equipped"):
            continue
        name = _norm(item.get("name"))
        if _has(name, *_ARMOR_EXCEPTIONS):
            continue
        if _has(name, *_ARMOR_WORDS):
            return f"身着{item.get('name')}"
    return ""


def observer_passive_perception(npc: Any) -> int:
    """NPC 被动察觉：感知调整 + 察觉熟练（生物卡缺属性时退回 10）。"""
    return creature_passive_perception(npc)


def _observer_npcs(state: Any, names: list[str] | None = None) -> list[Any]:
    """挑观察者：显式名单 > 当前在场名单 > 同地点 > 所有活着且在场的 NPC。"""
    world = getattr(state, "world_state", None)
    if world is None:
        return []
    alive = [n for n in (getattr(world, "npcs", None) or []) if bool(getattr(n, "alive", True))]
    wanted = {_norm(n) for n in (names or []) if str(n or "").strip()}
    if wanted:
        return [n for n in alive if _norm(getattr(n, "name", "")) in wanted]
    scene = getattr(world, "scene", None)
    if scene is None:
        return alive
    here = [str(x) for x in (getattr(scene, "visible_npcs_here", None) or [])]
    if here:
        picked = [n for n in alive if str(getattr(n, "name", "")) in here]
        if picked:
            return picked
    location = str(getattr(scene, "current_location", "") or "").strip()
    if location:
        local = [n for n in alive if str(getattr(n, "location", "") or "").strip() == location]
        if local:
            return local
    return alive


def observers(state: Any, names: list[str] | None = None, *,
              target: str = "") -> list[tuple[str, int]]:
    """观察者清单 (名字, 被动察觉)。

    NPC 观察者按 `_observer_npcs` 挑；藏的是 NPC 时把玩家也算进去
    （否则"敌人偷偷藏起来"永远不会被玩家发现）。
    被动察觉会按光照修正：微光/黑暗下依赖视觉的察觉劣势 → 5e 记 -5（见 light_rules）。
    """
    from backend.engine.perception_rules import passive_perception
    from backend.engine.player_damage import is_player_name
    from backend.engine import light_rules

    found: list[tuple[str, int]] = []
    for npc in _observer_npcs(state, names):
        npc_name = str(getattr(npc, "name", "") or "")
        found.append((npc_name, observer_passive_perception(npc)
                      + light_rules.passive_perception_penalty(state, npc_name)))
    if is_player_name(state, target or getattr(state, "character_name", "")):
        return found
    pc_name = str(getattr(state, "character_name", "") or "玩家")
    pc_value = passive_perception(state) + light_rules.passive_perception_penalty(state, pc_name)
    if names:
        if any(is_player_name(state, n) for n in names if str(n or "").strip()):
            found.append((pc_name, pc_value))
    else:
        found.append((pc_name, pc_value))
    return found


def best_observer(state: Any, names: list[str] | None = None,
                  *, target: str = "") -> tuple[str, int]:
    """返回被动察觉最高的观察者 (名字, 数值)；没有人时是 ("", 0)。"""
    best_name, best_value = "", 0
    for name, value in observers(state, names, target=target):
        if value > best_value:
            best_name, best_value = name, value
    return best_name, best_value
