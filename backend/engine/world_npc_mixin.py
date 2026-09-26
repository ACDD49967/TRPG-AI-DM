"""WorldState 的 NPC / 地点 / 名人查询与变更（从 world_state 拆出）。

方法只碰 `self.npcs/locations/notables` 与 `self._log_change`，字段仍定义在 WorldState。
"""
from __future__ import annotations

from backend.engine.world_models import (
    LocationEntry, NotableEntry, NpcEntry, NpcVisibility,
)
from backend.engine.world_names import clean_npc_name


class WorldNpcMixin:
    def get_npc(self, name: str) -> NpcEntry | None:
        canonical = self.canonical_npc_name(name)
        for n in self.npcs:
            if n.name == canonical:
                return n
        return None

    def canonical_npc_name(self, name: str) -> str:
        """把模型给的名字归一到已有 NPC：先精确匹配，再无歧义地按包含关系归名。

        「地精斥候（灌木丛后未现身）」「两只地精斥候」都应指向既有的「地精斥候」，
        否则每次场景更新都会凭空多出一个默认属性的幽灵 NPC。
        """
        cleaned = clean_npc_name(name)
        if not cleaned:
            return cleaned
        lowered = cleaned.lower()
        for npc in self.npcs:
            if npc.name and npc.name.strip().lower() == lowered:
                return npc.name
        contained = [npc.name for npc in self.npcs if npc.name and npc.name.lower() in lowered]
        if len(contained) == 1:
            return contained[0]
        return cleaned

    def update_npc(self, name: str, **changes) -> bool:
        npc = self.get_npc(name)
        if npc:
            for k, v in changes.items():
                if k == "visibility" and isinstance(v, dict):
                    npc.visibility = NpcVisibility.from_dict(v)
                    self._log_change(f"NPC[{name}] visibility updated")
                elif hasattr(npc, k):
                    old = getattr(npc, k)
                    setattr(npc, k, v)
                    self._log_change(f"NPC[{name}] {k}: {old} -> {v}")
            # HP 归零必须同步 alive=False：否则会出现"HP=0 但 alive=True"，
            # 击败经验与阵亡拦截都判断不到（`adjust_npc` 与这里两条路径都要守）。
            try:
                if int(getattr(npc, "hp", 0) or 0) <= 0:
                    npc.alive = False
            except (TypeError, ValueError):
                pass
            self.save()
            return True
        return False

    def add_npc(self, entry: NpcEntry):
        entry.name = self.canonical_npc_name(entry.name)
        existing = self.get_npc(entry.name)
        if existing is not None:
            # 同名再次登记时补齐空缺字段，不追加重复条目
            for field_name in ("role", "location", "attitude", "appearance", "personality",
                               "motivation", "secret", "relation_to_plot", "notes"):
                if not getattr(existing, field_name, "") and getattr(entry, field_name, ""):
                    setattr(existing, field_name, getattr(entry, field_name))
            existing.turn_last_seen = self.turn_count
            existing.discovered = existing.discovered or entry.discovered
            self._log_change(f"NPC已存在，补充信息: {entry.name}")
            self.save()
            return
        entry.turn_added = entry.turn_added or self.turn_count
        entry.turn_last_seen = self.turn_count
        self.npcs.append(entry)
        self._log_change(f"新增NPC: {entry.name} ({entry.role})")
        self.save()


    def get_location(self, name: str) -> "LocationEntry | None":
        for l in self.locations:
            if l.name == name:
                return l
        return None

    def add_location(self, entry: "LocationEntry"):
        """新增/更新地点实体（同名更新描述，不重复追加）。"""
        for i, loc in enumerate(self.locations):
            if loc.name == entry.name:
                entry.turn_added = entry.turn_added or loc.turn_added or self.turn_count
                entry.turn_last_visited = self.turn_count
                self.locations[i] = entry
                self._log_change(f"地点更新: {entry.name}")
                self.save()
                return
        entry.turn_added = entry.turn_added or self.turn_count
        entry.turn_last_visited = self.turn_count
        self.locations.append(entry)
        self._log_change(f"新增地点: {entry.name}")
        self.save()

    def get_notable(self, name: str) -> NotableEntry | None:
        for n in self.notables:
            if n.name == name:
                return n
        return None

    def add_notable(self, entry: NotableEntry):
        """新增/更新值得注意的场景或物品（同名更新，不重复追加）。"""
        for i, n in enumerate(self.notables):
            if n.name == entry.name:
                self.notables[i] = entry
                self._log_change(f"值得注意条目更新: {entry.name}")
                self.save()
                return
        self.notables.append(entry)
        self._log_change(f"新增值得注意条目: {entry.name} ({entry.entry_type})")
        self.save()

    def update_notable(self, name: str, **changes) -> bool:
        n = self.get_notable(name)
        if n is None:
            return False
        for k, v in changes.items():
            if hasattr(n, k):
                setattr(n, k, v)
        self._log_change(f"值得注意条目[{name}] 已更新")
        self.save()
        return True

    def remove_notable(self, name: str) -> bool:
        before = len(self.notables)
        self.notables = [n for n in self.notables if n.name != name]
        if len(self.notables) == before:
            return False
        self._log_change(f"值得注意条目已移除: {name}")
        self.save()
        return True
