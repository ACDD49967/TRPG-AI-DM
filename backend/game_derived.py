"""开局派生值：按规则系统算 HP/AC/豁免/法术位/职业资源，发初始装备，组装前端状态。

从 `backend/game_setup.py` 拆出（那边只留"建用户 → 建角色 → 建会话 → 落世界状态"的流程）。
这些计算全部是查表 + 赋值，与数据库/HTTP 无关，所以可以独立成模块并单测。
"""
from __future__ import annotations

from typing import Any

# 返回给前端的 status 字段（含 camelCase 映射，见 build_status_payload）
STATUS_KEYS = [
    "hp", "max_hp", "mp", "max_mp", "xp", "gold", "level", "ac", "inventory", "attributes",
    "character_name", "race", "char_class", "gender", "game_system", "username",
    "character_image", "scenario_id", "backstory", "skill_proficiencies", "skills", "saves",
    "passive_perception", "feats", "custom_classes", "custom_skills", "extra_attributes",
    "race_traits", "class_proficiencies", "hit_die", "san", "max_san", "luck",
    "healing_surges", "max_healing_surges", "surge_value", "speed", "proficiency_bonus",
    "spell_slots", "class_resources", "known_spells", "action_points", "fortitude",
    "reflex", "will", "damage_bonus", "build",
]


def apply_system_derived(game_system: str, character_info: dict, luck: int = 50) -> None:
    """按规则系统预填衍生数值（5e / CoC / 4e；自定义系统不强行套用）。"""
    if game_system == "dnd5e":
        from backend.engine.game_systems import (
            get_dnd5_class_resources,
            get_dnd5_derived,
            get_dnd5_proficiency_bonus,
            get_dnd5_saves,
            get_dnd5_spell_slots,
            get_passive_perception,
        )
        d5 = get_dnd5_derived(character_info.get("char_class", "战士"),
                              character_info.get("attributes", {}),
                              character_info.get("level", 1))
        character_info["hp"] = d5["hp"]
        character_info["max_hp"] = d5["max_hp"]
        character_info["hit_die"] = d5["hit_die"]
        character_info["proficiency_bonus"] = get_dnd5_proficiency_bonus(character_info.get("level", 1))
        character_info["spell_slots"] = get_dnd5_spell_slots(
            character_info.get("char_class", ""), character_info.get("level", 1))
        character_info["saves"] = get_dnd5_saves(
            character_info.get("char_class", ""), character_info.get("attributes", {}),
            character_info["proficiency_bonus"],
        )
        character_info["passive_perception"] = get_passive_perception(
            character_info.get("attributes", {}), character_info["proficiency_bonus"],
            character_info.get("skill_proficiencies", []),
        )
        character_info["class_resources"] = get_dnd5_class_resources(
            character_info.get("char_class", ""), character_info.get("attributes", {}),
            character_info.get("level", 1),
        )
    elif game_system == "coc":
        from backend.engine.game_systems import get_coc_derived
        coc = get_coc_derived(character_info.get("attributes", {}), luck or 50)
        character_info["hp"] = coc["hp"]
        character_info["max_hp"] = coc["hp"]
        character_info["mp"] = coc["mp"]
        character_info["max_mp"] = coc["mp"]
        character_info["san"] = coc["san"]
        character_info["max_san"] = coc["san"]
        character_info["luck"] = coc["luck"]
        character_info["damage_bonus"] = coc["damage_bonus"]
        character_info["build"] = coc["build"]
    elif game_system == "dnd4e":
        from backend.engine.game_systems import get_dnd4_defenses, get_dnd4_derived
        d4 = get_dnd4_derived(character_info.get("char_class", "战士"),
                              character_info.get("attributes", {}))
        defenses = get_dnd4_defenses(character_info.get("char_class", "战士"),
                                     character_info.get("attributes", {}),
                                     character_info.get("level", 1))
        character_info["hp"] = d4["hp"]
        character_info["max_hp"] = d4["max_hp"]
        character_info["healing_surges"] = d4["healing_surges"]
        character_info["max_healing_surges"] = d4["max_healing_surges"]
        character_info["surge_value"] = d4["surge_value"]
        character_info["ac"] = defenses["ac"]
        character_info["fortitude"] = defenses["fortitude"]
        character_info["reflex"] = defenses["reflex"]
        character_info["will"] = defenses["will"]
        # 4e 行动点：每次长休重置为 1，里程碑奖励 +1（前端角色卡单独渲染）
        character_info["action_points"] = 1
        character_info["class_resources"] = []
    # 职业资源（dnd4e 已有行动点；coc/自定义无固定职业资源）
    character_info.setdefault("class_resources", [])


def apply_starter_equipment(game_system: str, character: Any, character_info: dict) -> None:
    """初始白板装备：仅当玩家背包为空时按职业发放，不覆盖自定义开局。"""
    if (character.inventory or {}).get("items"):
        return
    from backend.engine.game_systems import get_starter_equipment
    starter_items = get_starter_equipment(game_system, character.char_class)
    character_info["inventory"] = {"items": starter_items}
    character.inventory = character_info["inventory"]


def build_status_payload(character_info: dict, username: str, char_name: str) -> dict:
    """组装前端可直接恢复的 status（含正确 username 与 camelCase 字段）。"""
    status = {k: character_info.get(k) for k in STATUS_KEYS if k in character_info}
    status["username"] = username or "default"
    status["character_name"] = char_name or status.get("character_name", "")
    # 兼容后端历史格式：inventory 可能是 {"items":[...]}，前端需要数组
    if isinstance(status.get("inventory"), dict):
        status["inventory"] = status["inventory"].get("items") or []
    for snake, camel in (("max_hp", "maxHp"), ("max_mp", "maxMp"), ("max_san", "maxSan")):
        if snake in status:
            status[camel] = status.pop(snake)
    return status


__all__ = ["apply_system_derived", "apply_starter_equipment", "build_status_payload", "STATUS_KEYS"]
