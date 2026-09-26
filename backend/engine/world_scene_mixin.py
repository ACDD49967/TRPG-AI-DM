"""WorldState 的场景/时间/可见度变更（从 world_state 拆出）。

包含 set_flag、update_scene、advance_time、reveal_npc_field 与可见 NPC 清洗。
"""
from __future__ import annotations

import re
from typing import Any

from backend.engine.world_models import LocationEntry, NpcEntry, PlotFlag
from backend.engine.world_names import (
    _EMPTY_NPC_TOKENS, _SCENE_MAX_VISIBLE_NPCS, _SCENE_TEXT_LIMITS,
    _cut_annotation, clean_location_name, clean_scene_text,
)


class WorldSceneMixin:
    def set_flag(self, key: str, status: str, description: str = "", consequence: str = "", visible: bool | None = None):
        resolved = {"已完成", "已失败", "已关闭", "已废弃"}
        for f in self.plot_flags:
            if f.key == key:
                old = f.status
                f.status = status
                if description: f.description = description
                if consequence: f.consequence = consequence
                if visible is not None: f.visible = visible
                if status in resolved:
                    f.turn_resolved = f.turn_resolved or self.turn_count
                else:
                    f.turn_resolved = 0
                self._log_change(f"Flag[{key}]: {old} -> {status}")
                self.save()
                return
        self.plot_flags.append(PlotFlag(key=key, status=status,
                                         description=description, consequence=consequence,
                                         visible=visible if visible is not None else True,
                                         turn_added=self.turn_count,
                                         turn_resolved=self.turn_count if status in resolved else 0))
        self._log_change(f"新增Flag: {key} = {status}")
        self.save()


    def update_scene(self, **kwargs):
        """更新当前场景信息。同时自动注册场景中出现的未知NPC。"""
        prepared = dict(kwargs)
        for field_name, limit in _SCENE_TEXT_LIMITS.items():
            if field_name in prepared and isinstance(prepared[field_name], str):
                prepared[field_name] = clean_scene_text(prepared[field_name], limit)
        if isinstance(prepared.get("current_location"), str):
            prepared["current_location"] = clean_location_name(prepared["current_location"])
        for field_name in ("current_time", "weather"):
            if isinstance(prepared.get(field_name), str):
                prepared[field_name] = _cut_annotation(prepared[field_name])
        if "visible_npcs_here" in prepared:
            prepared["visible_npcs_here"] = self._normalize_visible_npcs(prepared["visible_npcs_here"])
        for k, v in prepared.items():
            if hasattr(self.scene, k):
                setattr(self.scene, k, v)
        # P0-0修复：场景中出现的NPC名若不存在，自动创建默认NpcEntry；已存在则标记为已发现
        for npc_name in self.scene.visible_npcs_here:
            npc = self.get_npc(npc_name)
            if npc is None:
                self.add_npc(NpcEntry(name=npc_name, role="未知身份", location=self.scene.current_location, attitude="中立", discovered=True))
                npc = self.get_npc(npc_name)
            if npc is not None:
                npc.turn_last_seen = self.turn_count
                if not npc.discovered:
                    npc.discovered = True
                    self._log_change(f"NPC[{npc_name}] 已发现")
        # 玩家进入某个地点：不存在则建档（用清洗后的名字），随后标记发现并刷新到访轮数
        loc_name = str(self.scene.current_location or "").strip()
        loc = self.get_location(loc_name)
        if loc is None and loc_name and loc_name != "未知":
            self.add_location(LocationEntry(
                name=loc_name,
                description=self.scene.atmosphere or "当前场景",
                status="当前场景",
                discovered=True,
            ))
            loc = self.get_location(loc_name)
        if loc is not None:
            loc.turn_last_visited = self.turn_count
            if not loc.discovered:
                loc.discovered = True
                self._log_change(f"地点[{loc.name}] 已发现")
        self.save()
        # P0-1修复：日志输出，方便追踪Journal数据流
        print(f"[WorldState] 场景更新: location={self.scene.current_location}, "
              f"time={self.scene.current_time or f'第{self.scene.day_count}天'}, "
              f"weather={self.scene.weather}, npcs_here={self.scene.visible_npcs_here}, "
              f"total_npcs={len(self.npcs)}, turn={self.turn_count}")

    def _normalize_visible_npcs(self, values: Any) -> list[str]:
        """清洗在场 NPC 列表：去注解、去空值、按已有 NPC 归名、去重并限长。"""
        if isinstance(values, str):
            values = re.split(r"[、,，;；]", values)
        if not isinstance(values, (list, tuple, set)):
            return list(self.scene.visible_npcs_here)
        cleaned: list[str] = []
        for raw in values:
            name = self.canonical_npc_name(raw)
            if not name or name.lower() in _EMPTY_NPC_TOKENS:
                continue
            if name not in cleaned:
                cleaned.append(name)
        if not cleaned:
            return []
        return cleaned[:_SCENE_MAX_VISIBLE_NPCS]

    def advance_time(self, minutes: int):
        """推进游戏内时间。"""
        # 简易时间推进——AI可以调用此方法
        self._log_change(f"时间推进 {minutes} 分钟")

    def reveal_npc_field(self, name: str, field: str, level: str = "visible"):
        """揭示NPC的某个隐藏字段。"""
        npc = self.get_npc(name)
        if npc:
            if hasattr(npc.visibility, field):
                setattr(npc.visibility, field, level)
                self._log_change(f"NPC[{name}] 揭示 {field}={level}")
                self.save()
                return True
        return False
