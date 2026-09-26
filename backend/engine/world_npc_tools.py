"""角色与 NPC 查询/调整工具：状态摘要、资源增减、NPC 检索/调整/晋升、角色笔记。

从 `backend/engine/world_tools.py` 拆出。
"""
from __future__ import annotations

from backend.engine.character_state import _exec_update_state
from backend.engine.character_normalize import _normalize_condition
from backend.engine.condition_rules import condition_block_reason, creature_condition_immunities
from backend.engine.session import GameSessionState, push_event


async def _exec_get_character_state(args: dict, state: GameSessionState) -> str:
    """低 token 角色状态摘要：核心数值/职业资源/法术位/已习得法术。"""
    info = state.character_info
    fields = set(args.get("fields") or ["core", "resources", "spell_slots", "known_spells"])
    lines = []
    if not fields or "core" in fields:
        lines.append(
            f"HP {info.get('hp', 0)}/{info.get('max_hp', 0)} | AC {info.get('ac', 10)} | "
            f"Lv{info.get('level', 1)} | 金币 {info.get('gold', 0)}"
        )
        if info.get("game_system") == "coc":
            lines.append(f"MP {info.get('mp', 0)}/{info.get('max_mp', 0)} | SAN {info.get('san', 0)} | 幸运 {info.get('luck', 0)}")
    if "resources" in fields:
        res = info.get("class_resources", [])
        if res:
            lines.append("资源: " + " ".join(f"{r.get('name')}{r.get('current', 0)}/{r.get('max', 0)}" for r in res))
        if info.get("action_points") is not None:
            lines.append(f"行动点 {info['action_points']}/3")
    if "spell_slots" in fields:
        ss = info.get("spell_slots")
        if isinstance(ss, dict):
            arr = ss.get("spell_slots") or []
            if arr:
                lines.append("法术位: " + "/".join(str(x) for x in arr))
            if ss.get("pact_slots"):
                lines.append(f"契约法术位: {ss['pact_slots']}（{ss.get('pact_slot_level', 1)}环）")
    if "known_spells" in fields:
        spells = info.get("known_spells", [])
        if spells:
            lines.append("已习得: " + "、".join(
                f"{s.get('name')}({s.get('level', '?')}环{s.get('school', '')})" for s in spells
            ))
    if "inventory" in fields:
        items = (info.get("inventory") or {}).get("items", []) if isinstance(info.get("inventory"), dict) else []
        if items:
            lines.append("背包: " + "、".join(
                (i.get("name") if isinstance(i, dict) else str(i)) for i in items[:8]
            ))
    return "\n".join(lines) or "角色状态为空"


async def _exec_adjust_resource(args: dict, state: GameSessionState) -> str:
    key = str(args.get("resource", "")).strip()
    delta = int(args.get("delta", 0) or 0)
    reason = str(args.get("reason", "") or "资源调整")
    result = await _exec_update_state(
        {"changes": {f"class_resource:{key}": delta}, "reason": reason}, state)
    return result


async def _exec_search_npcs(args: dict, state: GameSessionState) -> str:
    ws = getattr(state, "world_state", None)
    if ws is None:
        return "无世界状态"
    query = str(args.get("query", "")).strip().lower()
    top_k = max(1, min(5, int(args.get("top_k", 3) or 3)))
    npcs = list(ws.npcs)
    if query:
        scored = []
        for n in npcs:
            hay = " ".join([n.name, n.role, n.location, n.attitude]).lower()
            scored.append((hay.count(query), n))
        scored.sort(key=lambda x: x[0], reverse=True)
        npcs = [n for c, n in scored if c > 0][:top_k]
    else:
        npcs = npcs[:top_k]
    if not npcs:
        return "世界状态中没有匹配的 NPC"
    return "\n".join(
        f"- {n.name} [{n.role or '未知'}] HP{n.hp}/{n.max_hp} AC{n.ac} Lv{n.level} "
        f"{n.attitude} @{n.location or '未知'}" + (" ☠" if not n.alive else "")
        + (f" [专注:{n.concentration}]" if getattr(n, "concentration", "") else "")
        for n in npcs
    )


async def _exec_adjust_npc(args: dict, state: GameSessionState) -> str:
    ws = getattr(state, "world_state", None)
    if ws is None:
        return "无世界状态"
    name = str(args.get("name", "")).strip()
    field = str(args.get("field", "")).strip()
    delta = int(args.get("delta", 0) or 0)
    npc = ws.get_npc(name)
    if npc is None:
        return f"⚠ NPC 不存在: {name}"
    if field == "alive":
        npc.alive = bool(args.get("value", True))
        ws.save()
    elif field in ("hp", "max_hp", "ac", "level"):
        current = getattr(npc, field, 0)
        setattr(npc, field, max(0, int(current) + delta))
        if field == "hp" and npc.hp > npc.max_hp:
            npc.hp = npc.max_hp
        if field == "hp" and npc.hp <= 0:
            # 与 _persist_combat_damage 同一约定：HP 归零必须同步 alive=False。
            # 以前只改 hp，会出现"HP=0 但 alive=True"的不一致状态。
            npc.alive = False
        ws.save()
    elif field == "condition_add":
        condition = _normalize_condition({
            "name": args.get("value") or args.get("condition") or "",
            "description": args.get("description") or "",
            "remaining_rounds": args.get("remaining_rounds") or 0,
            "source": args.get("reason") or "",
            "damage_per_turn": args.get("damage_per_turn") or "",
            "damage_type": args.get("damage_type") or "",
            "heal_per_turn": args.get("heal_per_turn") or 0,
            "save_dc": args.get("save_dc") or 0,
            "save_ability": args.get("save_ability") or "",
            "grappled_by": args.get("grappled_by") or "",
        })
        if condition is None:
            return "⚠ condition_add 需要 value（条件名）"
        blocked = condition_block_reason(condition["name"], creature_condition_immunities(npc))
        if blocked:
            return f"⚠ {npc.name} {blocked}，状态未添加"
        existing = next(
            (c for c in npc.conditions
             if str(c.get("name") if isinstance(c, dict) else c) == condition["name"]),
            None,
        )
        if existing is None:
            npc.conditions.append(condition)
        elif isinstance(existing, dict):
            existing.update({k: v for k, v in condition.items() if v})
        ws.save()
    elif field == "condition_remove":
        name = str(args.get("value") or args.get("condition") or "").strip()
        before = len(npc.conditions)
        npc.conditions = [
            c for c in npc.conditions
            if str(c.get("name") if isinstance(c, dict) else c) != name
        ]
        ws.save()
        if len(npc.conditions) == before:
            return f"⚠ {name} 不在 {npc.name} 的状态列表中"
    elif field in ("concentration", "concentration_clear"):
        from backend.engine.concentration import apply_npc_concentration_change
        note = await apply_npc_concentration_change(state, npc, field, args.get("value"))
        ws.save()
        await push_event(state, "journal_update", ws.to_player_journal())
        return note if note.startswith("⚠") else f"✅ {note}"
    else:
        return f"⚠ 不支持的字段: {field}"
    await push_event(state, "journal_update", ws.to_player_journal())
    if field in ("condition_add", "condition_remove"):
        names = [
            str(c.get("name") if isinstance(c, dict) else c)
            for c in npc.conditions
        ]
        return f"✅ {name} 状态: {'、'.join(names) if names else '无'}"
    return (f"✅ {name} {field}: {getattr(npc, field)} "
            f"(HP {npc.hp}/{npc.max_hp} AC {npc.ac} Lv {npc.level})")


async def _exec_promote_npc(args: dict, state: GameSessionState) -> str:
    ws = getattr(state, "world_state", None)
    if ws is None:
        return "无世界状态"
    name = str(args.get("name", "")).strip()
    npc = ws.get_npc(name)
    if npc is None:
        return f"⚠ NPC 不存在: {name}"
    npc.importance = "major"
    for field in ("personality", "motivation", "secret", "relation_to_plot", "appearance"):
        if args.get(field):
            setattr(npc, field, str(args[field]))
    if args.get("traits"):
        npc.traits = [str(t) for t in args["traits"]]
    if args.get("attributes"):
        npc.attributes = dict(args["attributes"])
    if args.get("skills"):
        npc.skills = [str(s) for s in args["skills"]]
    if args.get("equipment"):
        npc.equipment = [str(e) for e in args["equipment"]]
    for f in ("related_locations", "related_npcs", "related_creatures"):
        if args.get(f):
            setattr(npc, f, [str(x) for x in args[f]])
    ws.save()
    await push_event(state, "journal_update", ws.to_player_journal())
    return f"✅ {name} 已提升为重要NPC，角色卡已补全"


async def _exec_character_note(args: dict, state: GameSessionState) -> str:
    ws = getattr(state, 'world_state', None)
    if ws is None: return "无世界状态"
    target = str(args.get("target", "") or "").strip()
    comment = str(args.get("comment", "") or "").strip()
    ws.add_character_note(target=args.get("target",""), target_type=args.get("target_type","npc"),
                          comment=comment, clue=args.get("clue",""))

    # 同步更新关系图谱：目标 ↔ 相关NPC
    related = [str(x).strip() for x in (args.get("related_npcs") or []) if str(x).strip()]
    if ws is not None and related:
        strength = args.get("strength")
        confidence = args.get("confidence")
        relation = "note_link" if args.get("target_type", "npc") == "npc" else "note_context"
        for other in related:
            ws.add_or_update_relation(target, other, relation=relation,
                                      strength=strength, confidence=confidence,
                                      notes=comment)

    return f"角色笔记: {target}"
