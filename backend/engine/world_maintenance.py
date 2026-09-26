"""世界状态维护：过期内容清理与生命周期整理（world_state.maintenance 的实现）。"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta
from typing import Any

def maintenance_impl(
    ws,
    scope: str = "all",
    older_than_turns: int = 20,
    max_notes: int = 120,
    max_relations: int = 400,
    max_change_log: int = 300,
    max_background: int = 100,
) -> dict:
    """清理过期/低价值世界状态，返回统计摘要。

    scope: all | npcs | locations | flags | notes | notables | relations | logs
    设计原则：积极清理“确定过期”的临时内容；长期角色/当前地点/未完成主线不删。
    """
    scope = (scope or "all").strip().lower()
    do_all = scope in ("all", "")
    now = ws.turn_count
    cutoff = now - max(1, int(older_than_turns or 20))
    removed = {
        "npcs": 0, "locations": 0, "flags": 0, "notes": 0,
        "notables": 0, "relations": 0, "logs": 0,
        "removed_total": 0,
    }

    current_loc = (ws.scene.current_location or "").strip()
    visible_here = {str(x).strip() for x in (ws.scene.visible_npcs_here or [])}

    # ── NPC ────────────────────────────────────────────────
    if do_all or scope == "npcs":
        # 与玩家/主线有强关系（高亲密度或高置信度）的 NPC 不自动删除
        protected_names: set[str] = set()
        for rel in ws.relations:
            try:
                strong = (float(rel.get("strength") or 0) >= 70
                          or float(rel.get("confidence") or 0) >= 0.8)
            except (TypeError, ValueError):
                strong = False
            if strong:
                protected_names.add(str(rel.get("source", "")).strip())
                protected_names.add(str(rel.get("target", "")).strip())
        keep_npcs = []
        removed_names = set()
        for n in ws.npcs:
            name = (n.name or "").strip()
            last = int(n.turn_last_seen or n.turn_added or 0) or (now if n.alive else cutoff - 1)
            is_major = str(getattr(n, "importance", "minor")) == "major"
            here = name in visible_here or (n.location or "").strip() == current_loc
            if here or (is_major and n.alive):
                keep_npcs.append(n)
                continue
            if is_major and n.alive:
                keep_npcs.append(n)
                continue
            if name in protected_names:
                keep_npcs.append(n)
                continue
            stale = last < cutoff
            if stale and (not n.alive or not is_major):
                removed_names.add(name)
                removed["npcs"] += 1
                continue
            keep_npcs.append(n)
        if removed_names:
            ws.npcs = keep_npcs
            # 同步清理指向已移除 NPC 的笔记与关系
            ws.character_notes = [
                cn for cn in ws.character_notes
                if not (cn.target_type == "npc" and cn.target in removed_names)
            ]
            ws.relations = [
                r for r in ws.relations
                if r.get("source") not in removed_names and r.get("target") not in removed_names
            ]

    # ── 地点 ────────────────────────────────────────────────
    if do_all or scope == "locations":
        keep_locations = []
        removed_locs = set()
        blocked_status = {"已摧毁", "不可访问", "已废弃", "封闭", "已关闭"}
        for loc in ws.locations:
            name = (loc.name or "").strip()
            if name == current_loc or not loc.discovered:
                keep_locations.append(loc)
                continue
            blocked_now = str(loc.status or "") in {"已摧毁", "不可访问", "已废弃", "封闭", "已关闭"}
            last = int(loc.turn_last_visited or loc.turn_added or 0) or (cutoff - 1 if blocked_now else now)
            referenced = (
                any((n.location or "").strip() == name for n in ws.npcs)
                or any((no.location or "").strip() == name for no in ws.notables)
            )
            if (last > 0 and last < cutoff
                    and str(loc.status or "") in blocked_status
                    and not referenced):
                removed_locs.add(name)
                removed["locations"] += 1
                continue
            keep_locations.append(loc)
        if removed_locs:
            ws.locations = keep_locations
            ws.notables = [no for no in ws.notables if (no.location or "").strip() not in removed_locs]
            ws.character_notes = [
                cn for cn in ws.character_notes
                if not (cn.target_type == "location" and cn.target in removed_locs)
            ]
            ws.relations = [
                r for r in ws.relations
                if r.get("source") not in removed_locs and r.get("target") not in removed_locs
            ]

    # ── 剧情旗标 ────────────────────────────────────────────
    if do_all or scope == "flags":
        resolved_status = {"已完成", "已失败", "已关闭", "已废弃"}
        keep_flags = []
        for f in ws.plot_flags:
            if str(f.status or "") not in resolved_status:
                keep_flags.append(f)
                continue
            resolved_at = int(f.turn_resolved or f.turn_added or 0) or (cutoff - 1)
            if resolved_at < cutoff:
                removed["flags"] += 1
                continue
            keep_flags.append(f)
        ws.plot_flags = keep_flags

    # ── 值得注意条目 ────────────────────────────────────────
    if do_all or scope == "notables":
        resolved_status = {"已解决", "已拿走", "已取走", "已摧毁", "已关闭", "已离开", "已失效", "已完成"}
        keep_notables = []
        for no in ws.notables:
            notable_added = int(no.turn_added or 0) or (cutoff - 1)
            if str(no.status or "") in resolved_status and notable_added < cutoff:
                removed["notables"] += 1
                continue
            keep_notables.append(no)
        ws.notables = keep_notables

    # ── 角色笔记：删指向已不存在实体的笔记，并按条数截断 ──
    if do_all or scope == "notes":
        npc_names = {(n.name or "").strip() for n in ws.npcs}
        loc_names = {(l.name or "").strip() for l in ws.locations}
        kept = []
        for cn in ws.character_notes:
            if cn.target_type == "npc" and (cn.target or "").strip() not in npc_names:
                removed["notes"] += 1
                continue
            if cn.target_type == "location" and (cn.target or "").strip() not in loc_names:
                removed["notes"] += 1
                continue
            kept.append(cn)
        if len(kept) > max_notes:
            kept.sort(key=lambda c: int(c.turn_added or 0), reverse=True)
            removed["notes"] += len(kept) - max_notes
            kept = kept[:max_notes]
            kept.sort(key=lambda c: int(c.turn_added or 0))
        ws.character_notes = kept

    # ── 关系：删除悬空边并按强度/更新时间截断 ──────────────
    if do_all or scope == "relations":
        known = set()
        for n in ws.npcs:
            known.add((n.name or "").strip())
        for l in ws.locations:
            known.add((l.name or "").strip())
        for f in ws.plot_flags:
            known.add((f.key or "").strip())
        for no in ws.notables:
            known.add((no.name or "").strip())
        for c in ws.creatures:
            if isinstance(c, dict):
                known.add(str(c.get("name", "")).strip())
        for sp in ws.spells:
            if isinstance(sp, dict):
                known.add(str(sp.get("name", "")).strip())
        kept = []
        for r in ws.relations:
            src = str(r.get("source", "")).strip()
            dst = str(r.get("target", "")).strip()
            if not src or not dst or src not in known or dst not in known:
                removed["relations"] += 1
                continue
            kept.append(r)
        if len(kept) > max_relations:
            kept.sort(
                key=lambda r: (
                    float(r.get("turn_updated") or r.get("turn_added") or 0),
                    float(r.get("strength") or 0),
                ),
                reverse=True,
            )
            removed["relations"] += len(kept) - max_relations
            kept = kept[:max_relations]
        ws.relations = kept

    # ── 日志/幕后事件：只保留最近 N 条 ─────────────────────
    if do_all or scope == "logs":
        if len(ws.change_log) > max_change_log:
            removed["logs"] += len(ws.change_log) - max_change_log
            ws.change_log = ws.change_log[-max_change_log:]
        if len(ws.background_events) > max_background:
            removed["logs"] += len(ws.background_events) - max_background
            ws.background_events = ws.background_events[-max_background:]

    removed["removed_total"] = sum(
        removed[k] for k in ("npcs", "locations", "flags", "notes", "notables", "relations", "logs")
    )
    return removed


def run_maintenance(
    ws,
    scope: str = "all",
    older_than_turns: int = 20,
    max_notes: int = 120,
    max_relations: int = 400,
    max_change_log: int = 300,
    max_background: int = 100,
    dry_run: bool = False,
) -> dict:
    """清理过期/低价值世界状态；dry_run=True 时在副本上计算，不修改原状态。"""
    target = copy.deepcopy(ws) if dry_run else ws
    summary = target._maintenance_impl(
        scope=scope,
        older_than_turns=older_than_turns,
        max_notes=max_notes,
        max_relations=max_relations,
        max_change_log=max_change_log,
        max_background=max_background,
    )
    summary["dry_run"] = bool(dry_run)
    if not dry_run and summary.get("removed_total"):
        target._log_change(
            f"世界状态维护[{scope}]: 清理 {summary['removed_total']} 条过期内容"
        )
        if len(target.change_log) > max_change_log:
            target.change_log = target.change_log[-max_change_log:]
        target.save()
    return summary
