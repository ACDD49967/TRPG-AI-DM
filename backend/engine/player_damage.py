"""玩家侧伤害管线：抗性/免疫/易伤 + 临时生命值 + 死亡豁免的统一入口。

后端化目标：敌人攻击、范围伤害（吐息/火球/陷阱）、持续伤害都走同一条管线，
不让 LLM 每次即兴判断"你穿的是抗火斗篷所以减半"。规则计算在
`backend.engine.damage_rules`，本模块只负责"取哪些来源 + 落到状态上"。

来源只收"当前真的生效"的东西：结构化字段（damage_resistances 等）、种族特性、
专长、职业特性描述、状态效果、**正在专注的法术**、已装备物品描述。
已学会但未施放的法术不算（否则"知道防护能量"就等于永久抗性）。
"""
from __future__ import annotations

import re
from typing import Any

from backend.engine.damage_rules import (
    ability_modifier, canonical_damage_type, damage_multiplier,
)
from backend.engine.session import GameSessionState, push_event

# 玩家在工具参数里的常见称呼
_PLAYER_ALIASES = {"你", "玩家", "pc", "player", "主角", "自己", "我方玩家"}


def is_player_name(state: Any, name: Any) -> bool:
    """判断目标名是不是玩家（支持"你/玩家/PC"以及角色名）。"""
    key = re.sub(r"\s+", "", str(name or "")).lower()
    if not key:
        return False
    if key in _PLAYER_ALIASES:
        return True
    char = re.sub(r"\s+", "", str(getattr(state, "character_name", "") or "")).lower()
    return bool(char) and key == char


def _add_source(parts: list[str], value: Any) -> None:
    if isinstance(value, str):
        if value.strip():
            parts.append(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (str, int, float)):
                parts.append(f"{key} {item}")
            else:
                _add_source(parts, item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _add_source(parts, item)


def resistance_sources(state: Any) -> str:
    """把当前生效的抗性来源拼成可被 damage_rules 解析的文本。"""
    info = getattr(state, "character_info", {}) or {}
    parts: list[str] = []

    # 1) 结构化字段：DM / 前端 / 法术效果都可以直接写
    for key, template in (("damage_resistances", "{v}抗性"),
                          ("damage_immunities", "免疫{v}"),
                          ("damage_vulnerabilities", "{v}易伤"),
                          ("damage_traits", "{v}")):
        values = info.get(key) or []
        if isinstance(values, str):
            values = [values]
        for value in values:
            if str(value or "").strip():
                parts.append(template.format(v=value))

    # 2) 角色卡上的常驻特性
    _add_source(parts, info.get("race_traits"))
    _add_source(parts, info.get("class_proficiencies"))
    _add_source(parts, info.get("damage_traits_notes"))

    # 3) 专长（只有带抗性描述的才生效，直接交给文本解析判断）
    for feat in (info.get("feats") or []):
        if isinstance(feat, dict):
            _add_source(parts, feat.get("name"))
            _add_source(parts, feat.get("desc") or feat.get("description"))
        else:
            _add_source(parts, feat)

    # 4) 职业资源 / 形态特性（狂暴、野性形态等描述里常写抗性）
    for res in (info.get("class_resources") or []):
        if isinstance(res, dict):
            _add_source(parts, res.get("name"))
            _add_source(parts, res.get("desc"))
    _add_source(parts, info.get("wild_shape"))
    _add_source(parts, info.get("active_effects"))

    # 5) 状态效果（可能带"抗性"字样，例如"防护能量"提供的状态）
    _add_source(parts, info.get("conditions"))

    # 6) 正在专注的法术（防护能量/火焰护盾等）——只算正在生效的那一个
    concentration = info.get("concentration")
    if isinstance(concentration, dict):
        _add_source(parts, concentration.get("spell"))
        _add_source(parts, concentration.get("note"))
        # 专注法术写明的抗性类型（如防护能量选择火焰）需要补成"火焰抗性"才可被解析
        values = concentration.get("damage_resistances") or []
        if isinstance(values, str):
            values = [values]
        for value in values:
            if str(value or "").strip():
                parts.append(f"{value}抗性")

    # 7) 已装备物品描述（抗火戒指/龙鳞甲…）
    inventory = info.get("inventory")
    items = inventory.get("items") if isinstance(inventory, dict) else inventory
    for item in (items or []):
        if isinstance(item, dict) and item.get("equipped"):
            _add_source(parts, item.get("name"))
            _add_source(parts, item.get("description") or item.get("desc"))
        elif isinstance(item, str):
            continue  # 纯字符串物品没有装备标记，不作为抗性来源
    return " \n ".join(parts)


def multiplier_for(state: Any, damage_type: Any) -> tuple[float, str]:
    """玩家侧伤害倍率（免疫 0 / 抗性 0.5 / 易伤 2）。"""
    canonical = canonical_damage_type(damage_type)
    if not canonical:
        return 1.0, ""
    return damage_multiplier(resistance_sources(state), canonical)


def save_modifier(state: Any, ability: str) -> tuple[int, str]:
    """玩家豁免加值：优先角色卡里算好的 saves，其次属性 + 熟练。"""
    info = getattr(state, "character_info", {}) or {}
    ability = str(ability or "dex").lower()
    saves = info.get("saves")
    if isinstance(saves, dict):
        entry = saves.get(ability)
        if isinstance(entry, dict) and entry.get("value") is not None:
            return int(entry["value"]), "角色卡豁免"
        if isinstance(entry, (int, float)):
            return int(entry), "角色卡豁免"
    attrs = info.get("attributes") or {}
    mod = ability_modifier(attrs.get(ability, 10))
    proficient = ability in (info.get("save_proficiencies") or [])
    prof = int(info.get("proficiency_bonus", 2) or 2)
    return (mod + prof if proficient else mod), ("属性+熟练" if proficient else "属性推导")


async def apply(state: GameSessionState, amount: Any, damage_type: Any = "",
                reason: str = "", source: str = "") -> dict:
    """把一次伤害落到玩家身上：先扣临时生命值，再扣 HP，并推送可见事件。

    返回 {raw, applied, temp_absorbed, hp_damage, multiplier, note, hp_before, hp_after}。
    """
    from backend.engine.character_state import _exec_update_state

    info = state.character_info
    raw = max(0, int(amount or 0))
    canonical = canonical_damage_type(damage_type)
    multiplier, note = multiplier_for(state, canonical)
    applied = raw // 2 if multiplier == 0.5 else int(raw * multiplier)
    applied = max(0, int(applied))
    # 固定减伤（如「重甲大师」穿重甲时钝击/穿刺/挥砍 -3）：在抗性之后、临时生命值之前结算
    from backend.engine.feat_effects import damage_reduction

    dr = damage_reduction(state, canonical)
    if dr:
        applied = max(0, applied - dr)
        note = f"{note}；减免 {dr}".strip("；")

    temp_before = int(info.get("temporary_hp", 0) or 0)
    absorbed = min(temp_before, applied)
    hp_damage = applied - absorbed
    hp_before = int(info.get("hp", 0) or 0)
    if absorbed:
        await _exec_update_state({"changes": {"temporary_hp": -absorbed},
                                  "reason": f"临时生命值吸收 {absorbed}"}, state)
    if hp_damage:
        await _exec_update_state(
            {"changes": {"hp": -hp_damage}, "reason": reason or f"受到 {hp_damage} 点伤害"}, state)
    hp_after = int(info.get("hp", 0) or 0)
    # CoC 7e 重伤/致死按"单次伤害"判定——只有这条管线知道单次数值（update_state 只看到增量）
    from backend.engine.bloodied import handle_hp_threshold

    await handle_hp_threshold(state, hp_before, hp_after, damage=hp_damage)

    label = f"{canonical}伤害" if canonical else "伤害"
    desc = f"🩸 {source or '伤害'}：{label} {raw} 点"
    if note:
        desc += f"（{note}）"
    if absorbed:
        desc += f"，临时生命值吸收 {absorbed}"
    desc += f" → 实际扣血 {hp_damage}（HP {hp_before}→{hp_after}）"
    await push_event(state, "game_event", {
        "type": "damage",
        "description": desc,
        "extra": {
            "source": source, "damage_type": canonical, "raw": raw, "applied": applied,
            "temp_absorbed": absorbed, "hp_damage": hp_damage, "multiplier": multiplier,
            "note": note, "hp_before": hp_before, "hp_after": hp_after,
        },
    })
    if hp_after <= 0:
        # 玩家倒下（失能）→ 他抓着的目标立即挣脱（5e：擒抱者无法行动时擒抱结束）
        from backend.engine.contest_rules import release_grapples_by

        await release_grapples_by(state, str(getattr(state, "character_name", "") or ""))
    return {
        "raw": raw, "applied": applied, "temp_absorbed": absorbed, "hp_damage": hp_damage,
        "multiplier": multiplier, "note": note, "hp_before": hp_before, "hp_after": hp_after,
        "description": desc,
    }
