"""法术类工具：检索/学习/遗忘/施法结算，以及时间停止的额外回合提示。

从 `backend/engine/media_tools.py` 拆出——那边现在只剩图鉴/地图/地点的检索与登记。
`media_tools` 反向再导出这些名字，`dm_agent`/`tool_executor` 的既有引用不变。
"""
from __future__ import annotations

import random
import re

from backend.engine.character_state import _exec_update_state, _normalize_spell
from backend.engine.session import (
    GameSessionState, push_event,
)
from backend.engine.tool_shims import _game_system


async def _apply_time_stop(state: GameSessionState, spell_name: str) -> str:
    """时间暂停：额外回合数由**后端**决定（1d4+1），并记进先攻表。

    呼应用户要求：多动不能靠固定流程判定，而是"谁有资格多动"由规则数据决定，
    这里只在法术确实是时间暂停时授予，且落在后端账本上（DM 无法凭空多打一次）。
    """
    if not re.search(r"时间暂停|time\s*stop", spell_name, re.I):
        return ""
    from backend.engine import initiative
    extra = random.randint(1, 4) + 1
    player = str(getattr(state, "character_name", "") or "玩家")
    total = initiative.grant_turns(state, player, extra, note="时间暂停")
    if not total:
        return ""
    await push_event(state, "game_event", {
        "type": "time_stop",
        "description": f"⏳ 时间暂停：你获得 {extra} 个额外回合（本轮共 {total} 个）。",
        "extra": {"turns": extra, "turns_per_round": total},
    })
    return f"（时间暂停：额外 {extra} 个回合，本轮共 {total} 个）"


async def _exec_add_scenario_spell(args: dict, state: GameSessionState) -> str:
    from backend.media_manager import add_spell, find_global_spell, find_spell_exact, update_spell
    username = state.username or "default"
    scenario_id = state.character_info.get("scenario_id", "") or ""
    name = str(args.get("name", "未命名法术"))
    # 只查找同作用域条目；同名通用法术不会被本工具改写。
    existing = find_spell_exact(username, scenario_id or None, name)
    if existing:
        item = update_spell(username, existing["id"], {
            "description": args.get("description", "") or "",
            "level": str(args.get("level", "0")),
            "school": args.get("school", "") or "",
            "ritual": bool(args.get("ritual", False)),
            "casting_time": args.get("casting_time", "") or "",
            "range": args.get("range", "") or "",
            "components": args.get("components", "") or "",
            "duration": args.get("duration", "") or "",
            "classes": args.get("classes") or [],
            "scenario_id": scenario_id,
        })
        action = "更新"
    else:
        ref = find_global_spell(username, name) or {}
        item = add_spell(
            username=username,
            name=name,
            system=_game_system(state),
            description=args.get("description", "") or str(ref.get("description", "") or ""),
            level=str(args.get("level", ref.get("level", "0")) or "0"),
            school=args.get("school", "") or str(ref.get("school", "") or ""),
            ritual=bool(args.get("ritual", ref.get("ritual", False))),
            casting_time=args.get("casting_time", "") or str(ref.get("casting_time", "") or ""),
            range_=args.get("range", "") or str(ref.get("range", "") or ""),
            components=args.get("components", "") or str(ref.get("components", "") or ""),
            duration=args.get("duration", "") or str(ref.get("duration", "") or ""),
            classes=args.get("classes") or list(ref.get("classes", []) or []),
            scenario_id=scenario_id,
        )
        action = "新增"
    await push_event(state, "spells_updated", {})
    return f"✅ 已{action}当前剧本法术/仪式: {item['name']}"


async def _exec_search_spells(args: dict, state: GameSessionState) -> str:
    from backend.media_manager import list_spells
    query = str(args.get("query", "")).strip().lower()
    top_k = max(1, min(5, int(args.get("top_k", 3) or 3)))
    scenario_id = state.character_info.get("scenario_id", "")
    items = list_spells(state.username or "default", scenario_id or None)
    if not query:
        picked = items[:top_k]
    else:
        scored = []
        for it in items:
            hay = " ".join([
                it.get("name", ""), it.get("description", ""),
                it.get("school", ""), " ".join(it.get("classes", [])),
            ]).lower()
            scored.append((hay.count(query), it))
        scored.sort(key=lambda x: x[0], reverse=True)
        picked = [it for _, it in scored if _ > 0][:top_k]
    if not picked:
        return "法术图鉴中没有匹配的法术/仪式"
    return "\n".join(
        f"- {it.get('name','')}（{it.get('level','?')}环 {it.get('school','')}{' 仪式' if it.get('ritual') else ''}）: {str(it.get('description',''))[:80]}"
        for it in picked
    )


async def _exec_cast_spell(args: dict, state: GameSessionState) -> str:
    name = str(args.get("name", "") or "法术")
    level = int(args.get("level", 0) or 0)
    info = state.character_info
    # 施法前先检索法术图鉴确认等级/信息，避免凭空使用错误环位
    ref = _search_spell_for_entity(state, name)
    if ref and not args.get("level"):
        try:
            level = int(ref.get("level", level) or level)
        except Exception:
            level = 0
    # 5e 仪式施法：不消耗法术位，但要 +10 分钟且法术必须有仪式版本
    if bool(args.get("ritual")):
        return await _cast_as_ritual(state, name, level, ref)
    # 邪术师未显式指定时默认消耗契约法术位
    pact = bool(args.get("pact", info.get("char_class") == "邪术师"))
    if level <= 0:
        if bool(args.get("concentration")):
            info["concentration"] = {"spell": name, "level": 0}
            await push_event(state, "state_update", {"concentration": info["concentration"]})
        return f"🎲 {name}（戏法）不消耗法术位"
    current = info.get("spell_slots")
    if not isinstance(current, dict):
        current = {"spell_slots": [], "pact_slots": 0}
    if pact:
        if int(current.get("pact_slots", 0) or 0) <= 0:
            return f"⚠ 契约法术位不足，无法施放 {name}"
        current["pact_slots"] = int(current["pact_slots"]) - 1
        remain = f"契约 {current['pact_slots']}（{current.get('pact_slot_level', '?')}环）"
    else:
        arr = list(current.get("spell_slots") or [])
        if level > len(arr) or int(arr[level - 1] or 0) <= 0:
            # 邪术师常规环位不足时自动回落到契约法术位
            if info.get("char_class") == "邪术师" and int(current.get("pact_slots", 0) or 0) > 0:
                current["pact_slots"] = int(current["pact_slots"]) - 1
                info["spell_slots"] = current
                await push_event(state, "state_update", {"spell_slots": current})
                return (f"🎲 {name}：已消耗契约法术位 → 契约 {current['pact_slots']}"
                        f"（{current.get('pact_slot_level', '?')}环）" + await _apply_time_stop(state, name))
            return f"⚠ 第{level}环法术位不足，无法施放 {name}"
        arr[level - 1] = int(arr[level - 1]) - 1
        current["spell_slots"] = arr
        remain = f"{level}环剩余 {arr[level - 1]}"
    info["spell_slots"] = current
    await push_event(state, "state_update", {"spell_slots": current})
    # 5e 专注：同时只能维持一个专注法术，施放新的会中断旧的
    note = ""
    if bool(args.get("concentration")):
        previous = info.get("concentration")
        if isinstance(previous, dict) and previous.get("spell"):
            note = f"（专注中断：{previous['spell']}）"
        info["concentration"] = {"spell": name, "level": level}
        await push_event(state, "state_update", {"concentration": info["concentration"]})
    return f"🎲 {name}：已消耗法术位 → {remain}{note}" + await _apply_time_stop(state, name)


RITUAL_CLASSES = ("法师", "牧师", "德鲁伊", "吟游诗人")


async def _cast_as_ritual(
    state: GameSessionState, name: str, level: int, ref: dict | None,
) -> str:
    """仪式施法：需要仪式施法能力（职业自带或「仪式施法者」专长）且法术有仪式版本。

    规则要点（5e）：仪式版比正常施法多花 10 分钟，**不消耗法术位**。
    此前 `cast_spell` 没有这条路径——法术数据与专长里都写着"仪式"，代码却只会扣位。
    """
    from backend.engine.character_normalize import _has_feat_effect

    char_class = str(state.character_info.get("char_class") or "")
    has_ability = char_class in RITUAL_CLASSES or _has_feat_effect(state, "ritual_spell_access")
    if not has_ability:
        return ("⚠ 没有仪式施法能力：需要职业自带的仪式施法（法师/牧师/德鲁伊/吟游诗人）"
                "或「仪式施法者」专长。请按普通施法结算。")
    if ref is None or not ref.get("ritual"):
        return (f"⚠ {name} 没有仪式版本，不能以仪式方式施展。"
                "如果只是普通施法，请省略 ritual 参数。")

    from backend.engine import time_rules

    level_text = f"{level} 环" if level > 0 else "戏法"
    rested = await time_rules.advance(state, 10, "仪式施法")
    summary = ""
    if isinstance(rested, dict) and rested.get("summary"):
        summary = f"\n{rested['summary']}"
    return (f"📜 {name}（{level_text}）以仪式方式施展：不消耗法术位，额外耗时 10 分钟。"
            f"请把这段时间写进叙事（同伴可以同时做别的事）。{summary}")


def _search_spell_for_entity(state: GameSessionState, name: str) -> dict | None:
    """玩家/生物获得魔法能力时，先检索法术图鉴确认；找不到则返回 None。"""
    try:
        from backend.media_manager import list_spells
        sid = (state.character_info or {}).get("scenario_id", "") or ""
        for spells in (list_spells(state.username, sid), list_spells(state.username, None)):
            for s in spells or []:
                if str(s.get("name", "")).strip() == name.strip():
                    return s
    except Exception as e:
        from backend.logging_utils import get_logger
        get_logger("dm_agent.spell").warning("检索法术图鉴失败: %s", e, exc_info=True)
    return None


async def _exec_learn_spell(args: dict, state: GameSessionState) -> str:
    name = str(args.get("name", "") or "").strip()
    if not name:
        return "⚠ 缺少法术名"
    ref = _search_spell_for_entity(state, name)
    if ref:
        spell = {
            "name": str(ref.get("name", name)),
            "level": str(ref.get("level", "0") or "0"),
            "school": str(ref.get("school", "") or ""),
            "description": str(ref.get("description", "") or ""),
            "casting_time": str(ref.get("casting_time", "") or ""),
            "range": str(ref.get("range", "") or ""),
            "components": str(ref.get("components", "") or ""),
            "duration": str(ref.get("duration", "") or ""),
            "classes": list(ref.get("classes", []) or []),
            "scenario_id": (state.character_info or {}).get("scenario_id", ""),
        }
    else:
        # 不存在时生成一个合理法术，并写入当前剧本法术图鉴
        spell = _normalize_spell(args)
        spell.setdefault("level", "1")
        spell.setdefault("school", "变化")
        spell.setdefault("description", "")
        spell.setdefault("casting_time", "1动作")
        spell.setdefault("range", "30尺")
        spell.setdefault("components", "V、S")
        spell.setdefault("duration", "瞬间")
        try:
            from backend.media_manager import add_spell
            add_spell(
                username=state.username,
                name=spell["name"],
                system=_game_system(state),
                description=spell.get("description", ""),
                level=str(spell.get("level", "1") or "1"),
                school=str(spell.get("school", "") or ""),
                ritual=bool(spell.get("ritual", False)),
                casting_time=str(spell.get("casting_time", "") or ""),
                range_=str(spell.get("range", "") or ""),
                components=str(spell.get("components", "") or ""),
                duration=str(spell.get("duration", "") or ""),
                classes=list(spell.get("classes", []) or []),
                scenario_id=(state.character_info or {}).get("scenario_id", ""),
                tags=["剧本生成"],
            )
        except Exception:
            pass
    await _exec_update_state({"changes": {"spells_known_add": spell},
                              "reason": f"习得 {spell['name']}"}, state)
    return f"✅ 已习得: {spell['name']}（{spell['level']}环 {spell['school']}）"


async def _exec_forget_spell(args: dict, state: GameSessionState) -> str:
    name = str(args.get("name", ""))
    if not name:
        return "⚠ 缺少法术名"
    await _exec_update_state({"changes": {"spells_known_remove": name},
                              "reason": f"遗忘 {name}"}, state)
    return f"✅ 已遗忘: {name}"
