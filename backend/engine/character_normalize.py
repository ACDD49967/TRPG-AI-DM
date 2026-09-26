"""角色状态归一化：法术/物品字典、专长效果查询、状态效果的文本与结构归一。

从 `backend/engine/character_state.py` 拆出；那边只保留 `_exec_update_state` 主处理器并再导出这些名字。
"""
from __future__ import annotations

import re
from typing import Any

from backend.engine.session import GameSessionState

def _normalize_spell(item: Any) -> dict:
    """将已习得法术统一为 {name, level, school, description, casting_time, range, components, duration, classes, prepared}。"""

    def _norm_classes(value: Any) -> list:
        if isinstance(value, str):
            return [x.strip() for x in re.split(r"[,，、]", value) if x.strip()]
        if isinstance(value, list):
            return [str(x) for x in value if x]
        return []

    if isinstance(item, dict):
        return {
            "name": str(item.get("name") or "未命名法术"),
            "level": str(item.get("level") or "0"),
            "school": str(item.get("school") or ""),
            "description": str(item.get("description") or ""),
            "casting_time": str(item.get("casting_time") or ""),
            "range": str(item.get("range") or ""),
            "components": str(item.get("components") or ""),
            "duration": str(item.get("duration") or ""),
            "classes": _norm_classes(item.get("classes")),
            "ritual": bool(item.get("ritual", False)),
            "prepared": bool(item.get("prepared", True)),
        }
    return {
        "name": str(item),
        "level": "0", "school": "", "description": "",
        "casting_time": "", "range": "", "components": "", "duration": "",
        "classes": [], "ritual": False, "prepared": True,
    }

def _normalize_item(item: Any) -> dict:
    """将背包条目统一为结构化对象：{name, description, quantity, type, properties}。"""
    if isinstance(item, dict):
        return {
            "name": str(item.get("name") or item.get("item") or "未命名物品"),
            "description": str(item.get("description") or ""),
            "quantity": int(item.get("quantity") or 1),
            "type": str(item.get("type") or "misc"),
            "properties": item.get("properties") or {},
            "equipped": bool(item.get("equipped", False)),
        }
    return {
        "name": str(item),
        "description": "",
        "quantity": 1,
        "type": "misc",
        "properties": {},
        "equipped": False,
    }

def _has_feat_effect(state: GameSessionState, effect_key: str) -> bool:
    """检查角色是否拥有带指定 effect 的特长（如战地施法者的专注豁免优势）。"""
    from backend.engine.feats import FEATS_LIST

    feats = state.character_info.get("feats") or []
    names = set()
    for feat in feats:
        if isinstance(feat, dict):
            names.add(str(feat.get("id") or ""))
            names.add(str(feat.get("name") or ""))
        else:
            names.add(str(feat))
    for catalog_entry in FEATS_LIST:
        entry_names = {str(catalog_entry.get("id") or ""), str(catalog_entry.get("name") or "")}
        if names & entry_names and (catalog_entry.get("effect") or {}).get(effect_key):
            return True
    # 角色卡上直接写了 effect 的情况
    for feat in feats:
        if isinstance(feat, dict) and (feat.get("effect") or {}).get(effect_key):
            return True
    return False

def _format_condition(condition: dict | str) -> str:
    """把状态效果格式化成一行中文描述。"""
    if isinstance(condition, str):
        return condition
    name = str(condition.get("name") or "状态")
    parts = [name]
    if condition.get("description"):
        parts.append(str(condition["description"]))
    rounds = condition.get("remaining_rounds")
    if rounds:
        parts.append(f"剩余{rounds}回合")
    return "（".join([parts[0], "，".join(parts[1:]) + "）"]) if len(parts) > 1 else name

def _normalize_condition(raw: Any) -> dict | None:
    """统一状态效果结构：名称/描述/剩余回合/来源 + 可选每回合伤害与治疗。"""
    if isinstance(raw, str):
        name = raw.strip()
        return {"name": name, "description": "", "remaining_rounds": 0, "source": "",
                "damage_per_turn": "", "damage_type": "", "heal_per_turn": 0,
                "save_dc": 0, "save_ability": "", "grappled_by": ""} if name else None
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or raw.get("condition") or "").strip()
    if not name:
        return None
    try:
        rounds = max(0, int(raw.get("remaining_rounds") or raw.get("rounds") or 0))
    except (TypeError, ValueError):
        rounds = 0
    try:
        heal = max(0, int(raw.get("heal_per_turn") or 0))
    except (TypeError, ValueError):
        heal = 0
    try:
        save_dc = max(0, int(raw.get("save_dc") or 0))
    except (TypeError, ValueError):
        save_dc = 0
    return {
        "name": name,
        "description": str(raw.get("description") or raw.get("effect") or ""),
        "remaining_rounds": rounds,
        "source": str(raw.get("source") or ""),
        "damage_per_turn": raw.get("damage_per_turn") or raw.get("damage") or "",
        "damage_type": str(raw.get("damage_type") or ""),
        "heal_per_turn": heal,
        "save_dc": save_dc,
        "save_ability": str(raw.get("save_ability") or "").lower(),
        # 擒抱专用：谁抓着你——擒抱者倒下时后端据此自动解除（见 contest_rules）
        "grappled_by": str(raw.get("grappled_by") or ""),
    }
