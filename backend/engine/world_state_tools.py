"""世界状态写入工具：update_world_state（NPC/地点/名人/旗标/笔记/关系）与 prune。

从 `backend/engine/world_tools.py` 拆出；那边只做再导出，工具注册表与调用方不用改。
"""
from __future__ import annotations

from backend.engine.session import GameSessionState, push_event
from backend.engine.world_builder import _derive_npc_stats
from backend.engine.world_scene_tools import _exec_update_scene
from backend.engine.world_state import LocationEntry, NotableEntry, NpcEntry


async def _exec_prune_world_state(args: dict, state: GameSessionState) -> str:
    """主动清理世界状态中的过期内容，避免冒险笔记只增不减。"""
    ws = getattr(state, "world_state", None)
    if ws is None:
        return "⚠ 无世界状态"
    scope = str(args.get("scope", "all") or "all")
    older = int(args.get("older_than_turns", 20) or 20)
    dry = bool(args.get("dry_run", False))
    summary = ws.maintenance(scope=scope, older_than_turns=older, dry_run=dry)
    if not dry and summary.get("removed_total"):
        await push_event(state, "journal_update", ws.to_player_journal())
    detail = (f"NPC {summary.get('npcs', 0)}、地点 {summary.get('locations', 0)}、"
              f"旗标 {summary.get('flags', 0)}、笔记 {summary.get('notes', 0)}、"
              f"场景物品 {summary.get('notables', 0)}、关系 {summary.get('relations', 0)}、"
              f"日志 {summary.get('logs', 0)}")
    suffix = "（dry_run，未实际删除）" if dry else ""
    return f"🧹 世界状态维护[{scope}]：共清理 {summary.get('removed_total', 0)} 条（{detail}）{suffix}"


async def _exec_update_world_state(args: dict, state: GameSessionState) -> str:
    ws = getattr(state, 'world_state', None)
    if ws is None: return "无世界状态"
    action = args.get("action", ""); target = args.get("target", ""); changes = args.get("changes", {}); reason = args.get("reason", "")
    if action in ("update_scene", "scene"):
        # 场景更新走同一个处理器：以前这里会返回"未知操作"，DM 与接口都得另找工具
        merged = dict(changes or {})
        if reason:
            merged.setdefault("reason", reason)
        return await _exec_update_scene(merged, state)
    if action in ("update_npc", "add_npc"):
        existing = ws.get_npc(target)
        if action == "update_npc" and existing is not None:
            # 只更新调用方显式提供的字段，避免把未填字段重置成默认值
            update_data = {}
            for k in ("race", "role", "location", "attitude", "personality", "motivation",
                      "secret", "relation_to_plot", "alive", "level", "hp", "max_hp", "ac",
                      "attributes", "skills", "traits", "equipment", "related_locations",
                      "related_npcs", "related_creatures", "image_path", "importance"):
                if k in changes:
                    update_data[k] = changes[k]
            if update_data:
                ws.update_npc(target, **update_data)
            existing.turn_last_seen = ws.turn_count
            ws.save()
            await push_event(state, "journal_update", ws.to_player_journal())
            return f"✅ 已更新NPC: {target} ({reason})"

        # 新增或未命中同名实体时，使用合理默认值/派生数值建卡
        level, ac, hp, max_hp = _derive_npc_stats({
            "importance": changes.get("importance", "minor"),
            "role": changes.get("role", ""),
            "name": target,
            "level": changes.get("level", 0) or 0,
            "ac": changes.get("ac", 0) or 0,
            "hp": changes.get("hp", 0) or 0,
            "max_hp": changes.get("max_hp", 0) or 0,
        })
        npc_data = {
            "name": target,
            "race": changes.get("race", ""),
            "role": changes.get("role", ""),
            "location": changes.get("location", ""),
            "attitude": changes.get("attitude", "中立"),
            "personality": changes.get("personality", ""),
            "motivation": changes.get("motivation", ""),
            "secret": changes.get("secret", ""),
            "relation_to_plot": changes.get("relation_to_plot", ""),
            "alive": changes.get("alive", True),
            "level": level,
            "hp": hp,
            "max_hp": max_hp,
            "ac": ac,
            "attributes": changes.get("attributes", {}),
            "skills": changes.get("skills", []),
            "traits": changes.get("traits", []),
            "equipment": changes.get("equipment", []),
            "related_locations": changes.get("related_locations", []),
            "related_npcs": changes.get("related_npcs", []),
            "related_creatures": changes.get("related_creatures", []),
            "image_path": changes.get("image_path", ""),
            "importance": changes.get("importance", "minor"),
        }
        if existing is not None:
            # add_npc 语义但已有同名：保留原实体，仅覆写显式字段同样避免清空
            update_data = {}
            for k in ("race", "role", "location", "attitude", "personality", "motivation",
                      "secret", "relation_to_plot", "alive", "level", "hp", "max_hp", "ac",
                      "attributes", "skills", "traits", "equipment", "related_locations",
                      "related_npcs", "related_creatures", "image_path", "importance"):
                if k in changes:
                    update_data[k] = changes[k]
            if update_data:
                ws.update_npc(target, **update_data)
        else:
            ws.add_npc(NpcEntry(**npc_data))
        ws.save()
        await push_event(state, "journal_update", ws.to_player_journal())
        return f"✅ NPC: {target} ({reason})"
    elif action == "set_flag":
        old_flag = next((f for f in ws.plot_flags if f.key == target), None)
        status = changes.get("status") or (old_flag.status if old_flag else "进行中")
        ws.set_flag(key=target, status=status, description=changes.get("description",""), consequence=changes.get("consequence",""))
        await push_event(state, "journal_update", ws.to_player_journal())
        return f"✅ 旗标: {target} ({reason})"
    elif action == "set_world_rule":
        ws.world_rules = target or str(changes.get("rule", "") or changes.get("description", "") or "")
        ws.save()
        await push_event(state, "journal_update", ws.to_player_journal())
        return f"✅ 世界规则: {ws.world_rules[:80]} ({reason})"
    elif action in ("add_location", "update_location"):
        existing_location = ws.get_location(target)
        if existing_location is not None:
            # 已有地点：只更新显式传入的字段，避免清除未提供的内容
            for k in ("description", "status", "type", "culture", "notable_figures",
                      "dangers", "secrets", "secret_revealed", "related_locations",
                      "related_npcs", "related_creatures", "discovered"):
                if k in changes:
                    setattr(existing_location, k, changes[k])
            existing_location.turn_last_visited = ws.turn_count
            ws.save()
            await push_event(state, "journal_update", ws.to_player_journal())
            return f"✅ 地点已更新: {target} ({reason})"
        ws.add_location(LocationEntry(
            name=target,
            description=changes.get("description", ""),
            status=changes.get("status", "可访问"),
            type=changes.get("type", ""),
            culture=changes.get("culture", ""),
            notable_figures=changes.get("notable_figures", ""),
            dangers=changes.get("dangers", ""),
            secrets=changes.get("secrets", ""),
            secret_revealed=changes.get("secret_revealed", False),
            related_locations=changes.get("related_locations", []),
            related_npcs=changes.get("related_npcs", []),
            related_creatures=changes.get("related_creatures", []),
            discovered=changes.get("discovered", True),
        ))
        await push_event(state, "journal_update", ws.to_player_journal())
        return f"✅ 新增地点: {target} ({reason})"
    elif action in ("add_notable", "update_notable"):
        existing_notable = ws.get_notable(target)
        if existing_notable is not None:
            for k in ("entry_type", "description", "location", "status", "importance",
                      "discovered", "tags", "image_path"):
                if k in changes:
                    setattr(existing_notable, k, changes[k])
            ws.save()
            await push_event(state, "journal_update", ws.to_player_journal())
            return f"✅ 值得注意条目已更新: {target} ({reason})"
        ws.add_notable(NotableEntry(
            name=target,
            entry_type=changes.get("entry_type", "scene"),
            description=changes.get("description", ""),
            location=changes.get("location", ""),
            status=changes.get("status", ""),
            importance=changes.get("importance", "minor"),
            discovered=changes.get("discovered", True),
            tags=changes.get("tags", []),
            image_path=changes.get("image_path", ""),
            turn_added=ws.turn_count,
        ))
        await push_event(state, "journal_update", ws.to_player_journal())
        return f"✅ 新增值得注意条目: {target} ({reason})"
    elif action == "remove_notable":
        if not ws.remove_notable(target):
            return f"⚠ 值得注意条目 {target} 不存在"
        await push_event(state, "journal_update", ws.to_player_journal())
        return f"🗑️ 已移除值得注意条目: {target} ({reason})"
    elif action == "remove_npc":
        before = len(ws.npcs)
        ws.npcs = [n for n in ws.npcs if n.name != target]
        if len(ws.npcs) == before:
            return f"⚠ NPC {target} 不存在"
        # 同步清理现场、角色笔记与关系，避免冒险笔记残留已废弃角色
        ws.scene.visible_npcs_here = [n for n in ws.scene.visible_npcs_here if n != target]
        ws.character_notes = [c for c in ws.character_notes if not (c.target_type == "npc" and c.target == target)]
        ws.relations = [r for r in ws.relations if r.get("source") != target and r.get("target") != target]
        ws.save()
        await push_event(state, "journal_update", ws.to_player_journal())
        return f"🗑️ 已移除NPC: {target} ({reason})"
    elif action == "remove_location":
        before = len(ws.locations)
        ws.locations = [l for l in ws.locations if l.name != target]
        if len(ws.locations) == before:
            return f"⚠ 地点 {target} 不存在"
        if ws.scene.current_location == target:
            ws.scene.current_location = "未知"
        ws.notables = [n for n in ws.notables if n.location != target]
        ws.character_notes = [c for c in ws.character_notes if not (c.target_type == "location" and c.target == target)]
        ws.relations = [r for r in ws.relations if r.get("source") != target and r.get("target") != target]
        ws.save()
        await push_event(state, "journal_update", ws.to_player_journal())
        return f"🗑️ 已移除地点: {target} ({reason})"
    elif action == "remove_flag":
        before = len(ws.plot_flags)
        ws.plot_flags = [f for f in ws.plot_flags if f.key != target]
        if len(ws.plot_flags) == before:
            return f"⚠ 旗标 {target} 不存在"
        ws.save()
        await push_event(state, "journal_update", ws.to_player_journal())
        return f"🗑️ 已移除旗标: {target} ({reason})"
    elif action in ("add_note", "update_note"):
        # 角色视角笔记的增/改：目标+类型相同即视为同一条（与 DM 的 add_character_note 同语义）。
        # 玩家/前端此前只能看不能改，这条把"改"补上；删由 remove_character_note 负责。
        note_target = str(target or changes.get("target") or "").strip()
        note_type = str(changes.get("target_type") or "npc").strip() or "npc"
        if not note_target:
            return "❌ 角色笔记需要 target（针对谁/哪件事）"
        ws.add_character_note(
            target=note_target, target_type=note_type,
            comment=str(changes.get("comment") or ""), clue=str(changes.get("clue") or ""),
        )
        for note in ws.character_notes:
            if note.target == note_target and note.target_type == note_type:
                # add_character_note 只在非空时覆盖，这里让显式传入的字段（含清空/隐藏）真正生效
                if "comment" in changes:
                    note.character_comment = str(changes.get("comment") or "")
                if "clue" in changes:
                    note.clue = str(changes.get("clue") or "")
                if "visible" in changes:
                    note.visible = bool(changes.get("visible"))
                break
        ws.save()
        await push_event(state, "journal_update", ws.to_player_journal())
        return f"✅ 角色笔记: {note_target} ({note_type})"
    elif action == "remove_character_note":
        target_type = str((changes or {}).get("target_type") or "")
        before = len(ws.character_notes)
        ws.character_notes = [
            c for c in ws.character_notes
            if not ((not target_type or c.target_type == target_type) and c.target == target)
        ]
        if len(ws.character_notes) == before:
            return f"⚠ 角色笔记 {target} 不存在"
        ws.save()
        await push_event(state, "journal_update", ws.to_player_journal())
        return f"🗑️ 已移除角色笔记: {target} ({reason})"
    elif action == "remove_relation":
        src = str((changes or {}).get("source") or target or "").strip()
        dst = str((changes or {}).get("target") or "").strip()
        rel = str((changes or {}).get("relation") or "").strip()

        def _match(r: dict) -> bool:
            a = str(r.get("source", "")).strip()
            b = str(r.get("target", "")).strip()
            rr = str(r.get("relation", "")).strip()
            if src and a != src and b != src:
                return False
            if dst and a != dst and b != dst:
                return False
            if rel and rr != rel:
                return False
            return True

        before = len(ws.relations)
        ws.relations = [r for r in ws.relations if not _match(r)]
        if len(ws.relations) == before:
            return f"⚠ 关系不存在: {target}"
        ws.save()
        await push_event(state, "journal_update", ws.to_player_journal())
        return f"🗑️ 已移除关系: {target} ({reason})"
    return f"未知操作: {action}"
