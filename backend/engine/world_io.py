"""世界状态存档读写（JSON 落盘 + 兼容旧版本字段）。"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from backend.engine.world_models import (
    CharacterNote, LocationEntry, NotableEntry, NpcEntry, NpcVisibility,
    PlotFlag, SceneInfo,
)

if TYPE_CHECKING:      # 仅类型标注用，运行时避免与 world_state 形成循环
    from backend.engine.world_state import WorldState

def load_world(cls, session_id: str, storage_dir: str = "world_states") -> "WorldState":
    path = os.path.join(storage_dir, f"{session_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ws = cls(session_id=session_id, _storage_dir=storage_dir)
        ws.world_title = data.get("world_title", "")
        ws.world_outline = data.get("world_outline", "")
        ws.world_rules = data.get("world_rules", "")

        ws.npcs = []
        for n in data.get("npcs", []):
            vis_data = n.get("visibility") or {}
            npc = NpcEntry(**{k: v for k, v in n.items()
                              if k in ["name","race","role","location","attitude",
                                       "alive","appearance","personality","motivation",
                                       "secret","relation_to_plot","notes",
                                       "level","ac","hp","max_hp","attributes","skills","traits","conditions","equipment","related_locations","related_npcs","related_creatures","image_path","importance","discovered","turn_added","turn_last_seen","legendary_resistance","legendary_resistance_max","concentration"]})
            npc.visibility = NpcVisibility.from_dict(vis_data)
            ws.npcs.append(npc)

        ws.plot_flags = [PlotFlag(**{k: v for k, v in p.items()
                                     if k in ["key","status","description","consequence","visible","turn_added","turn_resolved"]})
                         for p in data.get("plot_flags", [])]
        ws.locations = [LocationEntry(**{k: v for k, v in l.items()
                                         if k in ["name","description","status","type","culture","notable_figures","dangers","secrets","secret_revealed","related_locations","related_npcs","related_creatures","discovered","turn_added","turn_last_visited"]})
                        for l in data.get("locations", [])]
        ws.creatures = data.get("creatures", [])
        ws.spells = data.get("spells", [])

        sc = data.get("scene", {})
        ws.scene = SceneInfo(
            current_location=sc.get("current_location", "未知"),
            current_time=sc.get("current_time", ""),
            day_count=sc.get("day_count", 1),
            weather=sc.get("weather", ""),
            atmosphere=sc.get("atmosphere", ""),
            visible_npcs_here=sc.get("visible_npcs_here", []),
            light=sc.get("light", ""),
            light_source=sc.get("light_source", ""),
        )
        ws.change_log = data.get("change_log", [])
        ws.character_notes = [
            CharacterNote(**{k: v for k, v in cn.items()
                             if k in ["target","target_type","character_comment",
                                      "clue","turn_added","visible"]})
            for cn in data.get("character_notes", [])
        ]
        ws.turn_count = data.get("turn_count", 0)
        ws.background_events = data.get("background_events", [])
        ws.relations = data.get("relations", [])
        ws.notables = [
            NotableEntry(**{k: v for k, v in n.items()
                            if k in ["name","entry_type","description","location",
                                     "status","importance","discovered","tags",
                                     "image_path","turn_added"]})
            for n in data.get("notables", [])
        ]

        # 旧存档缺少生命周期时间戳：补为当前轮，给它们一个完整的清理宽限期，
        # 避免升级后的第一次维护一次性清空整个世界。
        default_turn = int(ws.turn_count or 0)
        resolved_status = {"已完成", "已失败", "已关闭", "已废弃"}
        blocked_status = {"已摧毁", "不可访问", "已废弃", "封闭", "已关闭"}
        resolved_notable = {"已解决", "已拿走", "已取走", "已摧毁", "已关闭", "已离开", "已失效", "已完成"}
        for n in ws.npcs:
            n.turn_added = int(n.turn_added or default_turn)
            # 已死亡 NPC 旧数据直接视为过期；存活 NPC 给完整宽限期
            n.turn_last_seen = int(n.turn_last_seen or (default_turn if n.alive else 0))
        for l in ws.locations:
            l.turn_added = int(l.turn_added or default_turn)
            blocked = str(l.status or "") in blocked_status
            l.turn_last_visited = int(l.turn_last_visited or (0 if blocked else default_turn))
        for f in ws.plot_flags:
            f.turn_added = int(f.turn_added or default_turn)
            if str(f.status or "") in resolved_status:
                f.turn_resolved = int(f.turn_resolved or 0)
        for no in ws.notables:
            resolved = str(no.status or "") in resolved_notable
            no.turn_added = int(no.turn_added or (0 if resolved else default_turn))
        for r in ws.relations:
            r["turn_added"] = int(r.get("turn_added") or default_turn)
            r["turn_updated"] = int(r.get("turn_updated") or default_turn)

        return ws
    return cls(session_id=session_id, _storage_dir=storage_dir)


def world_to_dict(ws) -> dict:
    """世界状态的可序列化快照（存档与落盘共用同一份构造）。

    以前 `save_serialize` 是"先落盘再读回硬编码的 world_states/<sid>.json"，
    一旦会话的 `_storage_dir` 不是默认目录（脚本/测试/自定义目录），
    存档里的 world_state 就会静默变成空——这里统一成内存构造，彻底去掉路径耦合。
    """
    return {
        "world_title": ws.world_title,
        "world_outline": ws.world_outline,
        "world_rules": ws.world_rules,
        "npcs": [{**asdict(n), "visibility": n.visibility.to_dict()} for n in ws.npcs],
        "plot_flags": [asdict(p) for p in ws.plot_flags],
        "locations": [asdict(l) for l in ws.locations],
        "creatures": ws.creatures,
        "spells": ws.spells,
        "scene": asdict(ws.scene),
        "character_notes": [asdict(cn) for cn in ws.character_notes],
        "notables": [asdict(n) for n in ws.notables],
        "turn_count": ws.turn_count,
        "background_events": ws.background_events,
        "relations": ws.relations,
        "change_log": ws.change_log,
    }


def save_world(ws):
    os.makedirs(ws._storage_dir, exist_ok=True)
    path = os.path.join(ws._storage_dir, f"{ws.session_id}.json")
    data = world_to_dict(ws)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def log_change(ws, desc: str):
    ws.change_log.append({
        "time": datetime.now().isoformat(),
        "description": desc,
    })
