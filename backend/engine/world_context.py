"""世界状态 → 前端笔记 / DM 上下文文本。"""
from __future__ import annotations

from typing import Any

def to_player_journal(ws) -> dict:
    """生成玩家笔记——仅包含可见信息。

    这是前端侧边栏的数据源。
    """
    # NPC 按态度分组
    allies = []
    enemies = []
    neutrals = []
    for n in ws.npcs:
        if not getattr(n, "discovered", True):
            continue  # 玩家尚未见过的 NPC 不暴露
        view = n.to_player_view()
        view["location"] = n.location  # 位置始终可见
        if n.attitude in ("友善", "忠诚"): allies.append(view)
        elif n.attitude in ("敌对",): enemies.append(view)
        else: neutrals.append(view)

    return {
        "scene": {
            "location": ws.scene.current_location,
            "time": ws.scene.current_time or f"第{ws.scene.day_count}天",
            "weather": ws.scene.weather,
            "atmosphere": ws.scene.atmosphere,
            "npcs_here": ws.scene.visible_npcs_here,
            "light": getattr(ws.scene, "light", ""),
            "light_source": getattr(ws.scene, "light_source", ""),
        },
        "npcs": {
            "allies": allies,
            "enemies": enemies,
            "neutrals": neutrals,
            # 只统计对玩家可见/已发现的角色，隐藏角色不计入数量
            "total": len(allies) + len(enemies) + len(neutrals),
        },
        "plot_flags": [p.to_player_view() for p in ws.plot_flags if p.visible],
        "locations": [l.to_player_view() for l in ws.locations if l.discovered],
        # 角色视角笔记——按类型分组
        "character_notes": {
            "npc_notes": [{"target": n.target, "comment": n.character_comment, "clue": n.clue,
                           "turn": n.turn_added}
                          for n in ws.character_notes if n.target_type == "npc" and n.visible],
            "event_notes": [{"target": n.target, "comment": n.character_comment, "clue": n.clue,
                             "turn": n.turn_added}
                            for n in ws.character_notes if n.target_type == "event" and n.visible],
            "quest_clues": [{"target": n.target, "comment": n.character_comment, "clue": n.clue,
                             "turn": n.turn_added}
                            for n in ws.character_notes if n.target_type == "quest" and n.visible],
            "location_notes": [{"target": n.target, "comment": n.character_comment, "clue": n.clue,
                                "turn": n.turn_added}
                               for n in ws.character_notes if n.target_type == "location" and n.visible],
        },
        "world_events": [
            {"turn": e.get("turn"), "text": e.get("public_hint") or e.get("event")}
            for e in ws.background_events[-10:] if e.get("public_hint") or e.get("visible")
        ],
        "notables": [n.to_player_view() for n in ws.notables if n.discovered],
        "turn_count": ws.turn_count,
    }


def to_context_string(ws) -> str:
    """为AI生成完整的世界状态上下文（含隐藏信息——AI需要知道全部）。"""
    lines = []

    # 场景
    sc = ws.scene
    lines.append(f"## 当前场景\n- 地点: {sc.current_location}\n- 时间: {sc.current_time or f'第{sc.day_count}天'}\n- 天气: {sc.weather}\n- 氛围: {sc.atmosphere}")
    if sc.visible_npcs_here:
        lines.append(f"- 在场NPC: {', '.join(sc.visible_npcs_here)}")

    if ws.world_title:
        lines.append(f"\n## 冒险\n{ws.world_title}")

    if ws.npcs:
        lines.append("\n## 全部NPC（含隐藏信息——仅你可见，勿直接透露给玩家）")
        for n in ws.npcs:
            tag = "☠已故" if not n.alive else "🟢"
            lines.append(f"\n- {tag} **{n.name}** | {n.race} {n.role} | 位置:{n.location} | 态度:{n.attitude}")
            lines.append(f"  [对玩家可见度] 外貌:{n.visibility.appearance} 性格:{n.visibility.personality} 动机:{n.visibility.motivation}")
            if n.appearance and n.visibility.appearance == "visible":
                lines.append(f"  外貌: {n.appearance}")
            if n.personality:
                lines.append(f"  性格: {n.personality}")
            if n.motivation:
                lines.append(f"  动机: {n.motivation}")
            if n.secret:
                lines.append(f"  秘密: {n.secret}" +
                             (" [对玩家隐藏]" if n.visibility.secret == "hidden" else ""))
            if n.relation_to_plot:
                lines.append(f"  剧情关联: {n.relation_to_plot}")

    if ws.plot_flags:
        lines.append("\n## 剧情进度（含暗线；暗线对玩家隐藏，但你必须持续推进）")
        for f in ws.plot_flags:
            icon = {"未触发":"⚪","进行中":"🔵","已完成":"✅","已失败":"❌"}.get(f.status,"⚪")
            tag = " [暗线]" if not f.visible else ""
            line = f"- {icon} {f.key}: {f.status}{tag}"
            if f.description:
                line += f" — {f.description}"
            if f.consequence:
                line += f"（后果：{f.consequence}）"
            lines.append(line)

    if ws.background_events:
        lines.append("\n## 幕后事件（玩家不在场时发生的进展）")
        for e in ws.background_events[-5:]:
            line = f"- [第{e.get('turn', 0)}轮] {e.get('event', '')}"
            if e.get('impact'):
                line += f"（影响：{e['impact']}）"
            if e.get('public_hint'):
                line += f" [可被玩家听闻：{e['public_hint']}]"
            lines.append(line)

    try:
        from backend.engine.knowledge_graph import graph_to_context
        kg = graph_to_context(ws)
        if kg:
            lines.append("\n" + kg)
    except Exception as e:
        from backend.logging_utils import get_logger
        get_logger("world_state.graph").warning("graph_to_context 注入失败: %s", e, exc_info=True)

    return "\n".join(lines)


def to_context_compact(ws) -> str:
    """紧凑版——每轮AI调用时注入的简要世界状态。"""
    lines = ["## 当前世界状态（每轮必读）"]

    sc = ws.scene
    lines.append(f"📍 {sc.current_location} | 🕐 {sc.current_time or f'第{sc.day_count}天'} | 🌤 {sc.weather}")
    if sc.visible_npcs_here:
        lines.append(f"👥 在场: {', '.join(sc.visible_npcs_here)}")

    if ws.npcs:
        lines.append("### NPC状态")
        for n in ws.npcs[:8]:  # 最多8个，避免token爆炸
            tag = "☠" if not n.alive else ""
            hidden = sum(1 for f in [n.visibility.personality, n.visibility.motivation,
                                     n.visibility.secret, n.visibility.relation_to_plot]
                        if f == "hidden")
            lines.append(f"- {tag}{n.name}({n.role}) 态度:{n.attitude} 位置:{n.location} 隐藏字段:{hidden}")

    if ws.plot_flags:
        active = [f for f in ws.plot_flags if f.status in ("进行中", "未触发")]
        if active:
            lines.append("### 关键旗标")
            for f in active[:6]:
                tag = " [暗线]" if not f.visible else ""
                lines.append(f"- {f.key}: {f.status}{tag}")

    if ws.notables:
        notable = [n for n in ws.notables if n.discovered]
        if notable:
            lines.append("### 值得注意的场景/物品")
            for n in notable[:6]:
                lines.append(f"- {n.name}（{n.entry_type}）{n.description[:50]}")

    if ws.background_events:
        latest = ws.background_events[-1]
        lines.append(f"### 幕后进展（共{len(ws.background_events)}条）")
        lines.append(f"- {latest.get('event', '')[:60]}")

    return "\n".join(lines)
