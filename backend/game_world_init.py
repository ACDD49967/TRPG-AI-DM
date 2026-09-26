"""开局的持久化世界状态：从请求里的 world_state_json 还原，或建一个空的并预设初始场景。

从 `backend/game_setup.py` 拆出。旧存档/剧本可能只带部分字段，所以按白名单挑字段构造实体，
避免 NpcEntry/LocationEntry 收到未知键而报错；解析失败时回退成空世界，保证开局不中断。
"""
from __future__ import annotations

import json
import re

from backend.engine.world_state import WorldState

_NPC_FIELDS = [
    "name", "race", "role", "location", "attitude", "alive", "personality", "motivation",
    "secret", "relation_to_plot", "notes", "level", "ac", "hp", "max_hp", "attributes",
    "skills", "traits", "equipment", "related_locations", "related_npcs", "related_creatures",
    "image_path", "importance", "discovered", "visibility",
]
_FLAG_FIELDS = ["key", "status", "description", "consequence", "visible"]
_LOCATION_FIELDS = [
    "name", "description", "status", "type", "culture", "notable_figures", "dangers",
    "secrets", "secret_revealed", "related_locations", "related_npcs", "related_creatures",
    "discovered",
]


def init_world_state(session_id: str, world_state_json: str | None,
                     character_info: dict) -> WorldState:
    """返回可用的 WorldState（失败时退化为空世界 + 预设初始场景）。"""
    if world_state_json:
        try:
            ws_data = json.loads(world_state_json)
            ws = WorldState(session_id=session_id,
                            world_outline=ws_data.get("world_outline", ""),
                            world_rules=ws_data.get("world_rules", ""))
            from backend.engine.world_state import (
                LocationEntry, NpcEntry, NpcVisibility, PlotFlag,
            )
            for n in ws_data.get("npcs", []):
                entry = NpcEntry(**{k: v for k, v in n.items() if k in _NPC_FIELDS})
                if isinstance(entry.visibility, dict):
                    entry.visibility = NpcVisibility.from_dict(entry.visibility)
                ws.npcs.append(entry)
            for p in ws_data.get("plot_flags", []):
                ws.plot_flags.append(PlotFlag(**{k: v for k, v in p.items() if k in _FLAG_FIELDS}))
            for l in ws_data.get("locations", []):
                ws.locations.append(
                    LocationEntry(**{k: v for k, v in l.items() if k in _LOCATION_FIELDS}))
            ws.save()
            return ws
        except Exception:
            return _fresh_world(session_id, character_info)
    return _fresh_world(session_id, character_info)


def _fresh_world(session_id: str, character_info: dict) -> WorldState:
    """没有预生成剧本时也要有 WorldState，否则 update_scene 没法工作。"""
    ws = WorldState(session_id=session_id)
    init_loc = "冒险的起点"
    if character_info.get("world_outline"):
        outline = character_info["world_outline"]
        m = re.search(r'(?:地点|场景|位置|起始)[：:]\s*(.+?)(?:\n|$)', outline)
        init_loc = m.group(1)[:30] if m else "世界的入口"
    ws.update_scene(current_location=init_loc, current_time="第1天 · 冒险开始", weather="")
    ws.save()
    return ws


__all__ = ["init_world_state"]
