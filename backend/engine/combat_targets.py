"""战斗目标解析：NPC 卡 / 生物图鉴卡 → 实际战斗实体与数值。

从 backend.engine.combat 拆出（combat 只留结算流程）；combat 反向再导出，
media_tools 与 dm_agent 的既有 import 不受影响。
"""
from __future__ import annotations

import re
from typing import Any

from backend.engine.session import GameSessionState
from backend.engine.world_state import NpcEntry



def _first_int(text: Any) -> int:
    """从文本中取第一个整数（兼容 '15 (天生护甲)'、'22 (3d8+6)'）。"""
    m = re.search(r"-?\d+", str(text or ""))
    return int(m.group()) if m else 0



def _first_dice(text: Any) -> str:
    """从文本中取第一个伤害骰表达式，如 '2d6+3'。"""
    m = re.search(r"\d+d\d+(?:\+\d+)?", str(text or ""))
    return m.group() if m else ""



def _find_bestiary_card(state: GameSessionState, name: str) -> dict | None:
    card = None
    try:
        from backend.media_manager import list_bestiary
        scenario_id = state.character_info.get("scenario_id", "") or ""
        items = list_bestiary(state.username or "default", scenario_id or None)
        # 先找当前剧本自己的条目，避免同名通用图鉴抢先命中。
        for item in items:
            if str(item.get("scenario_id") or "") != scenario_id:
                continue
            if str(item.get("name", "")) == name or str(item.get("id", "")) == name:
                card = dict(item)
                break
        # 当前剧本没有同名条目时，才回退到通用参考。
        if card is None:
            for item in items:
                if str(item.get("scenario_id") or ""):
                    continue
                if str(item.get("name", "")) == name or str(item.get("id", "")) == name:
                    card = dict(item)
                    break
    except Exception as e:
        from backend.logging_utils import get_logger
        get_logger("dm_agent.bestiary").warning("查找图鉴卡失败: %s", e, exc_info=True)
    # 本局临时覆写：优先合并到图鉴卡；若图鉴无此卡，则用覆写构造临时卡
    override = getattr(state, "bestiary_overrides", {}).get(name)
    if override:
        if card is None:
            card = {"name": name, "stats": {}, "description": "", "tags": [], "image_path": ""}
        stats = dict(card.get("stats") or {})
        stats.update(override.get("stats") or {})
        card["stats"] = stats
        if override.get("description"):
            card["description"] = str(override["description"])
        if override.get("tags"):
            card["tags"] = override.get("tags")
    return card



def _register_combatant_from_card(state: GameSessionState, name: str,
                                  card: dict, fallback: dict) -> Any:
    """把生物图鉴卡注册为世界状态中的实际战斗实体，返回 NpcEntry。"""
    ws = getattr(state, "world_state", None)
    if ws is None:
        return None
    npc = ws.get_npc(name)
    if npc is not None:
        return npc
    stats = card.get("stats") or {}
    attrs = {}
    for key, label in (("力量", "str"), ("敏捷", "dex"), ("体质", "con"),
                       ("智力", "int"), ("感知", "wis"), ("魅力", "cha")):
        score = _first_int(stats.get(key, ""))
        if score:
            attrs[label] = score
    level = _first_int(stats.get("等级", stats.get("挑战等级", stats.get("CR", "")))) or 1
    ac = _first_int(stats.get("AC", stats.get("ac", ""))) or int(fallback.get("e_ac", 10))
    hp = _first_int(stats.get("HP", stats.get("hp", ""))) or int(fallback.get("e_hp", 10))
    traits = []
    for key in ("特性", "动作", "Traits", "Actions"):
        if stats.get(key):
            traits.append(str(stats[key]))
    if stats.get("技能") or stats.get("skills"):
        skills = [str(stats.get("技能") or stats.get("skills"))]
    else:
        skills = []
    entry = NpcEntry(
        name=name,
        role="生物（图鉴）",
        location=ws.scene.current_location or "未知",
        attitude="敌对",
        alive=True,
        level=level,
        ac=ac,
        hp=hp,
        max_hp=hp,
        attributes=attrs,
        skills=skills,
        traits=traits,
        image_path=card.get("image_path", ""),
    )
    ws.add_npc(entry)
    return entry



def _resolve_enemy_from_cards(state: GameSessionState, enemy: str, args: dict) -> dict:
    """从 NPC 卡 / 生物图鉴卡解析敌人战斗数值；无卡时按参数生成临时实体。"""
    fallback = {
        "e_ac": int(args.get("enemy_ac", 13) or 13),
        "e_mod": int(args.get("enemy_attack_modifier", 3) or 3),
        "e_dice": str(args.get("enemy_damage_dice", "1d6") or "1d6"),
        "e_hp": int(args.get("enemy_hp", 20) or 20),
    }
    ws = getattr(state, "world_state", None)
    if ws is not None:
        npc = ws.get_npc(enemy)
        if npc is not None:
            attrs = npc.attributes or {}
            prof = 2 + (max(1, min(20, int(npc.level or 1))) - 1) // 4
            atk_attr = max(((attrs.get(k, 10) or 10) - 10) // 2 for k in ("str", "dex"))
            traits_text = " ".join(npc.traits or [])
            current_hp = _resolve_npc_hp(args.get("enemy_hp"), npc)
            return {
                "npc": npc,
                "e_ac": int(args.get("enemy_ac", 0) or npc.ac or fallback["e_ac"]),
                "e_mod": int(args.get("enemy_attack_modifier", 0) or (atk_attr + prof) or fallback["e_mod"]),
                "e_dice": str(args.get("enemy_damage_dice", "") or _first_dice(traits_text) or fallback["e_dice"]),
                # 注意：已阵亡 NPC 的 hp=0 是有效数值，不能用 or 兜底成默认血量，
                # 否则死掉的敌人会以满血“复活”继续挨打。
                "e_hp": current_hp,
                "e_max_hp": max(current_hp, int(getattr(npc, "max_hp", 0) or 0) or current_hp),
            }
    card = _find_bestiary_card(state, enemy)
    if card:
        npc = _register_combatant_from_card(state, enemy, card, fallback)
        if npc is not None:
            attrs = npc.attributes or {}
            prof = 2 + (max(1, min(20, int(npc.level or 1))) - 1) // 4
            atk_attr = max(((attrs.get(k, 10) or 10) - 10) // 2 for k in ("str", "dex"))
            traits_text = " ".join(npc.traits or [])
            return {
                "npc": npc,
                "e_ac": int(args.get("enemy_ac", 0) or npc.ac),
                "e_mod": int(args.get("enemy_attack_modifier", 0) or (atk_attr + prof)),
                "e_dice": str(args.get("enemy_damage_dice", "") or _first_dice(traits_text) or fallback["e_dice"]),
                "e_hp": int(args.get("enemy_hp", 0) or npc.hp),
                "e_max_hp": int(getattr(npc, "max_hp", 0) or npc.hp or fallback["e_hp"]),
            }
    if ws is not None:
        npc = ws.get_npc(enemy) or NpcEntry(
            name=enemy, role="临时敌人", location=ws.scene.current_location or "未知",
            attitude="敌对", level=1, ac=fallback["e_ac"],
            hp=fallback["e_hp"], max_hp=fallback["e_hp"],
        )
        if ws.get_npc(enemy) is None:
            ws.add_npc(npc)
        fallback["npc"] = npc
    return fallback



def _resolve_npc_hp(arg_hp: Any, npc: NpcEntry) -> int:
    """解析 NPC 当前 HP：显式参数优先，其次用 NPC 自身数值（含 0）。"""
    for candidate in (arg_hp, getattr(npc, "hp", None)):
        if candidate is None:
            continue
        try:
            value = int(candidate)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return max(0, int(getattr(npc, "hp", 0) or 0))
