"""持久化世界状态——NPC可见度控制、场景追踪、时间系统。

核心设计：
- 每个NPC有 visibility 字典控制哪些字段对玩家可见
- 场景追踪：当前时间、地点、天气、氛围
- 玩家笔记：仅导出可见信息到前端侧边栏
- AI可通过 reveal_info 工具修改可见度
"""

import copy
import json, os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta


# ═══════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════

@dataclass
class NpcVisibility:
    """控制NPC各字段对玩家的可见度。

    visible: 玩家完全可见
    hidden: 显示为"???"（对玩家隐藏但AI知道）
    partial: 显示部分/模糊信息
    """
    name: str = "visible"           # 名字
    race: str = "visible"           # 种族
    role: str = "visible"           # 身份（如"???商人"则role="partial"但name visible）
    appearance: str = "visible"     # 外貌描述
    personality: str = "hidden"     # 性格——通常隐藏
    motivation: str = "hidden"      # 动机——几乎总是隐藏
    secret: str = "hidden"          # 秘密——总是隐藏
    relation_to_plot: str = "hidden" # 剧情关联——通常隐藏
    alive: str = "visible"          # 是否存活
    notes: str = "hidden"           # 备注

    def to_dict(self) -> dict:
        result = {}
        for k in ["name", "race", "role", "appearance", "personality",
                  "motivation", "secret", "relation_to_plot", "alive", "notes"]:
            result[k] = getattr(self, k, "hidden")
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "NpcVisibility":
        defaults = {
            "name": "visible", "race": "visible", "role": "visible",
            "appearance": "visible", "personality": "hidden",
            "motivation": "hidden", "secret": "hidden",
            "relation_to_plot": "hidden", "alive": "visible", "notes": "hidden",
        }
        for k, v in (data or {}).items():
            if k in defaults:
                defaults[k] = v
        return cls(**defaults)

    @classmethod
    def full_reveal(cls) -> "NpcVisibility":
        """全可见（盟友/公开NPC）。"""
        return cls(
            name="visible", race="visible", role="visible",
            appearance="visible", personality="visible",
            motivation="visible", secret="visible",
            relation_to_plot="visible", alive="visible", notes="visible",
        )

    @classmethod
    def mysterious(cls) -> "NpcVisibility":
        """完全神秘（隐藏反派/陌生人）。"""
        return cls(
            name="visible", race="hidden", role="hidden",
            appearance="visible", personality="hidden",
            motivation="hidden", secret="hidden",
            relation_to_plot="hidden", alive="visible", notes="hidden",
        )


@dataclass
class NpcEntry:
    """关键NPC完整记录——包含可见度控制。"""
    name: str
    race: str = ""
    role: str = ""
    location: str = ""
    attitude: str = "中立"
    alive: bool = True
    appearance: str = ""        # 外貌描述
    personality: str = ""
    motivation: str = ""
    secret: str = ""
    relation_to_plot: str = ""
    notes: str = ""
    level: int = 1
    ac: int = 10
    hp: int = 10
    max_hp: int = 10
    attributes: dict = field(default_factory=dict)   # 六维/COC属性等
    skills: list = field(default_factory=list)       # 技能列表
    traits: list = field(default_factory=list)       # 特性/动作/专长等
    equipment: list = field(default_factory=list)    # 可见装备（武器/护甲/随身物品）
    related_locations: list = field(default_factory=list)  # 关联地点名
    related_npcs: list = field(default_factory=list)       # 关联NPC名
    related_creatures: list = field(default_factory=list)  # 关联生物/怪物名
    image_path: str = ""
    importance: str = "minor"       # major=重要NPC（完整卡） minor=简单NPC（简要卡）
    discovered: bool = True         # 玩家是否已见过/知道该NPC；False 时不出现在玩家笔记
    turn_added: int = 0             # 首次进入世界状态的轮数
    turn_last_seen: int = 0         # 最近一次出场/被提及的轮数
    visibility: NpcVisibility = field(default_factory=NpcVisibility)

    def to_player_view(self) -> dict:
        """生成对玩家可见的信息（根据visibility过滤）。"""
        v = self.visibility
        result = {
            "name": self.name if v.name == "visible" else "???",
            "attitude": self.attitude,
            "alive": self.alive if v.alive == "visible" else None,
        }

        def _show(field_val: str, vis: str, default: str = "???") -> str:
            if vis == "visible": return field_val if field_val else (default or "???")
            if vis == "partial": return f"???{field_val[:3] if field_val else ''}" if field_val else (default or "???")
            return default or "???"

        result["race"] = _show(self.race, v.race)
        result["role"] = _show(self.role, v.role)
        result["appearance"] = _show(self.appearance, v.appearance, "")
        result["personality"] = _show(self.personality, v.personality, "")
        result["motivation"] = _show(self.motivation, v.motivation, "")
        result["secret"] = _show(self.secret, v.secret, "")
        result["relation_to_plot"] = _show(self.relation_to_plot, v.relation_to_plot, "")
        hidden_count = sum(
            1 for f in [v.race, v.role, v.appearance, v.personality,
                        v.motivation, v.secret, v.relation_to_plot]
            if f == "hidden"
        )
        fully_revealed = hidden_count == 0
        result["fully_revealed"] = fully_revealed

        if fully_revealed:
            result.update({
                "level": self.level,
                "ac": self.ac,
                "hp": self.hp,
                "max_hp": self.max_hp,
                "image_path": self.image_path,
                "attributes": self.attributes,
                "skills": self.skills,
                "traits": self.traits,
                "equipment": self.equipment,
                "related_locations": self.related_locations,
                "related_npcs": self.related_npcs,
                "related_creatures": self.related_creatures,
            })
        else:
            result.update({
                "level": None,
                "ac": None,
                "hp": None,
                "max_hp": None,
                "image_path": "",
                "attributes": {},
                "skills": [],
                "traits": [],
                "equipment": [],
                "related_locations": [],
                "related_npcs": [],
                "related_creatures": [],
            })

        return result


@dataclass
class PlotFlag:
    key: str
    status: str = "未触发"
    description: str = ""
    consequence: str = ""
    visible: bool = True  # 对玩家可见？
    turn_added: int = 0       # 首次出现的轮数
    turn_resolved: int = 0    # 进入已完成/已失败等终态的轮数

    def to_player_view(self) -> dict:
        if not self.visible:
            return {"key": "???", "status": "???", "description": ""}
        return {"key": self.key, "status": self.status, "description": self.description}


@dataclass
class LocationEntry:
    name: str
    description: str = ""
    status: str = "可访问"
    type: str = ""
    culture: str = ""
    notable_figures: str = ""
    dangers: str = ""
    secrets: str = ""
    secret_revealed: bool = False
    related_locations: list = field(default_factory=list)
    related_npcs: list = field(default_factory=list)
    related_creatures: list = field(default_factory=list)
    discovered: bool = True  # 玩家是否已发现
    turn_added: int = 0          # 首次进入世界状态的轮数
    turn_last_visited: int = 0   # 最近一次到访/提及的轮数

    def to_player_view(self) -> dict:
        if not self.discovered:
            return {"name": "???", "description": "尚未发现", "status": "未知"}
        result = {
            "name": self.name, "description": self.description, "status": self.status,
            "type": self.type, "culture": self.culture, "notable_figures": self.notable_figures,
            "dangers": self.dangers,
            "related_locations": self.related_locations,
            "related_npcs": self.related_npcs,
            "related_creatures": self.related_creatures,
        }
        if self.secret_revealed and self.secrets:
            result["secret"] = self.secrets
        return result


@dataclass
class CharacterNote:
    """角色视角的笔记——以角色口吻评价NPC/事件/地点。"""
    target: str                  # 目标名称(NPC名/事件/地点)
    target_type: str = "npc"     # npc / event / location / quest
    character_comment: str = ""  # 角色视角的简短评价(1-2句, 第一人称)
    clue: str = ""               # 相关线索或推论
    turn_added: int = 0          # 在第几轮添加的
    visible: bool = True         # 是否在玩家笔记中显示


@dataclass
class NotableEntry:
    """值得注意的场景/物品/线索——冒险笔记“角色和场景”页的数据源。"""
    name: str
    entry_type: str = "scene"      # scene | item | object | clue | other
    description: str = ""
    location: str = ""
    status: str = ""
    importance: str = "minor"      # major | minor
    discovered: bool = True
    tags: list[str] = field(default_factory=list)
    image_path: str = ""
    turn_added: int = 0

    def to_player_view(self) -> dict:
        if not self.discovered:
            return {"name": "???", "entry_type": "???", "description": "尚未发现"}
        return {
            "name": self.name,
            "entry_type": self.entry_type,
            "description": self.description,
            "location": self.location,
            "status": self.status,
            "importance": self.importance,
            "tags": self.tags,
            "image_path": self.image_path,
            "turn_added": self.turn_added,
        }


@dataclass
class SceneInfo:
    """当前场景信息——每回合更新。"""
    current_location: str = "未知"
    current_time: str = ""      # 如 "午夜前两小时"
    day_count: int = 1           # 第几天
    weather: str = ""
    atmosphere: str = ""         # 氛围描述
    visible_npcs_here: list[str] = field(default_factory=list)  # 当前在场的NPC名


@dataclass
class WorldState:
    """完整的持久化世界状态。"""
    session_id: str = ""
    world_title: str = ""
    world_outline: str = ""
    world_rules: str = ""

    npcs: list[NpcEntry] = field(default_factory=list)
    plot_flags: list[PlotFlag] = field(default_factory=list)
    locations: list[LocationEntry] = field(default_factory=list)
    creatures: list = field(default_factory=list)
    spells: list = field(default_factory=list)

    scene: SceneInfo = field(default_factory=SceneInfo)

    # 角色视角笔记
    character_notes: list[CharacterNote] = field(default_factory=list)

    # 值得注意的场景/物品/线索（冒险笔记“角色和场景”页）
    notables: list[NotableEntry] = field(default_factory=list)
    turn_count: int = 0  # 当前轮数

    # 幕后剧情事件：玩家不在场时世界仍在推进
    background_events: list[dict] = field(default_factory=list)

    # 显式关系边（类知识图谱）：source/target/relation/strength/confidence/notes
    relations: list[dict] = field(default_factory=list)

    change_log: list[dict] = field(default_factory=list)
    _storage_dir: str = field(default="world_states", repr=False)

    @classmethod
    def load(cls, session_id: str, storage_dir: str = "world_states") -> "WorldState":
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
                                           "level","ac","hp","max_hp","attributes","skills","traits","equipment","related_locations","related_npcs","related_creatures","image_path","importance","discovered","turn_added","turn_last_seen"]})
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

    def save(self):
        os.makedirs(self._storage_dir, exist_ok=True)
        path = os.path.join(self._storage_dir, f"{self.session_id}.json")
        data = {
            "world_title": self.world_title,
            "world_outline": self.world_outline,
            "world_rules": self.world_rules,
            "npcs": [{**asdict(n), "visibility": n.visibility.to_dict()} for n in self.npcs],
            "plot_flags": [asdict(p) for p in self.plot_flags],
            "locations": [asdict(l) for l in self.locations],
            "creatures": self.creatures,
            "spells": self.spells,
            "scene": asdict(self.scene),
            "character_notes": [asdict(cn) for cn in self.character_notes],
            "notables": [asdict(n) for n in self.notables],
            "turn_count": self.turn_count,
            "background_events": self.background_events,
            "relations": self.relations,
            "change_log": self.change_log,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_npc(self, name: str) -> NpcEntry | None:
        for n in self.npcs:
            if n.name == name:
                return n
        return None

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
            self.save()
            return True
        return False

    def add_npc(self, entry: NpcEntry):
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
        for k, v in kwargs.items():
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
        # 玩家进入某个地点后，该地点应被发现并刷新到访轮数
        loc = self.get_location(self.scene.current_location)
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

    def add_character_note(self, target: str, target_type: str = "npc",
                           comment: str = "", clue: str = ""):
        """添加角色视角笔记——以角色口吻评价。"""
        # 去重：同一目标+同一类型不重复添加
        for n in self.character_notes:
            if n.target == target and n.target_type == target_type:
                if comment: n.character_comment = comment
                if clue: n.clue = clue
                n.turn_added = self.turn_count
                break
        else:
            self.character_notes.append(CharacterNote(
                target=target, target_type=target_type,
                character_comment=comment, clue=clue,
                turn_added=self.turn_count,
            ))
        self.save()

    def add_background_event(self, event: dict):
        """记录一条幕后剧情事件，并自动落盘。"""
        event = dict(event or {})
        event.setdefault("turn", self.turn_count)
        self.background_events.append(event)
        # 只保留最近 100 条，避免存档无限膨胀
        if len(self.background_events) > 100:
            self.background_events = self.background_events[-100:]
        self.save()

    def add_or_update_relation(
        self,
        source: str,
        target: str,
        relation: str = "related",
        strength: float | None = None,
        confidence: float | None = None,
        notes: str = "",
    ) -> dict:
        """新增/更新一条显式关系边（亲密度 0-100，置信度 0-1）。"""
        source = (source or "").strip()
        target = (target or "").strip()
        if not source or not target or source == target:
            return {}
        relation = (relation or "related").strip()
        try:
            strength = None if strength is None else max(0.0, min(100.0, float(strength)))
        except (TypeError, ValueError):
            strength = None
        try:
            confidence = None if confidence is None else max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = None
        for rel in self.relations:
            if rel.get("source") == source and rel.get("target") == target and rel.get("relation") == relation:
                if strength is not None:
                    rel["strength"] = strength
                if confidence is not None:
                    rel["confidence"] = confidence
                if notes:
                    rel["notes"] = notes
                rel["turn_updated"] = self.turn_count
                self.save()
                return rel
        rel = {
            "source": source,
            "target": target,
            "relation": relation,
            "strength": strength if strength is not None else 50.0,
            "confidence": confidence if confidence is not None else 0.5,
            "notes": notes or "",
            "turn_added": self.turn_count,
            "turn_updated": self.turn_count,
        }
        self.relations.append(rel)
        self.save()
        return rel

    def get_relations_for(self, name: str) -> list[dict]:
        """返回与某实体相关的所有显式关系边。"""
        name = (name or "").strip()
        if not name:
            return []
        return [r for r in self.relations
                if r.get("source") == name or r.get("target") == name]

    def advance_turn(self):
        """推进轮数。"""
        self.turn_count += 1
        # 可选：不每次保存，由调用方决定

    def _log_change(self, desc: str):
        self.change_log.append({
            "time": datetime.now().isoformat(),
            "description": desc,
        })

    def _maintenance_impl(
        self,
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
        now = self.turn_count
        cutoff = now - max(1, int(older_than_turns or 20))
        removed = {
            "npcs": 0, "locations": 0, "flags": 0, "notes": 0,
            "notables": 0, "relations": 0, "logs": 0,
            "removed_total": 0,
        }

        current_loc = (self.scene.current_location or "").strip()
        visible_here = {str(x).strip() for x in (self.scene.visible_npcs_here or [])}

        # ── NPC ────────────────────────────────────────────────
        if do_all or scope == "npcs":
            # 与玩家/主线有强关系（高亲密度或高置信度）的 NPC 不自动删除
            protected_names: set[str] = set()
            for rel in self.relations:
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
            for n in self.npcs:
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
                self.npcs = keep_npcs
                # 同步清理指向已移除 NPC 的笔记与关系
                self.character_notes = [
                    cn for cn in self.character_notes
                    if not (cn.target_type == "npc" and cn.target in removed_names)
                ]
                self.relations = [
                    r for r in self.relations
                    if r.get("source") not in removed_names and r.get("target") not in removed_names
                ]

        # ── 地点 ────────────────────────────────────────────────
        if do_all or scope == "locations":
            keep_locations = []
            removed_locs = set()
            blocked_status = {"已摧毁", "不可访问", "已废弃", "封闭", "已关闭"}
            for loc in self.locations:
                name = (loc.name or "").strip()
                if name == current_loc or not loc.discovered:
                    keep_locations.append(loc)
                    continue
                blocked_now = str(loc.status or "") in {"已摧毁", "不可访问", "已废弃", "封闭", "已关闭"}
                last = int(loc.turn_last_visited or loc.turn_added or 0) or (cutoff - 1 if blocked_now else now)
                referenced = (
                    any((n.location or "").strip() == name for n in self.npcs)
                    or any((no.location or "").strip() == name for no in self.notables)
                )
                if (last > 0 and last < cutoff
                        and str(loc.status or "") in blocked_status
                        and not referenced):
                    removed_locs.add(name)
                    removed["locations"] += 1
                    continue
                keep_locations.append(loc)
            if removed_locs:
                self.locations = keep_locations
                self.notables = [no for no in self.notables if (no.location or "").strip() not in removed_locs]
                self.character_notes = [
                    cn for cn in self.character_notes
                    if not (cn.target_type == "location" and cn.target in removed_locs)
                ]
                self.relations = [
                    r for r in self.relations
                    if r.get("source") not in removed_locs and r.get("target") not in removed_locs
                ]

        # ── 剧情旗标 ────────────────────────────────────────────
        if do_all or scope == "flags":
            resolved_status = {"已完成", "已失败", "已关闭", "已废弃"}
            keep_flags = []
            for f in self.plot_flags:
                if str(f.status or "") not in resolved_status:
                    keep_flags.append(f)
                    continue
                resolved_at = int(f.turn_resolved or f.turn_added or 0) or (cutoff - 1)
                if resolved_at < cutoff:
                    removed["flags"] += 1
                    continue
                keep_flags.append(f)
            self.plot_flags = keep_flags

        # ── 值得注意条目 ────────────────────────────────────────
        if do_all or scope == "notables":
            resolved_status = {"已解决", "已拿走", "已取走", "已摧毁", "已关闭", "已离开", "已失效", "已完成"}
            keep_notables = []
            for no in self.notables:
                notable_added = int(no.turn_added or 0) or (cutoff - 1)
                if str(no.status or "") in resolved_status and notable_added < cutoff:
                    removed["notables"] += 1
                    continue
                keep_notables.append(no)
            self.notables = keep_notables

        # ── 角色笔记：删指向已不存在实体的笔记，并按条数截断 ──
        if do_all or scope == "notes":
            npc_names = {(n.name or "").strip() for n in self.npcs}
            loc_names = {(l.name or "").strip() for l in self.locations}
            kept = []
            for cn in self.character_notes:
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
            self.character_notes = kept

        # ── 关系：删除悬空边并按强度/更新时间截断 ──────────────
        if do_all or scope == "relations":
            known = set()
            for n in self.npcs:
                known.add((n.name or "").strip())
            for l in self.locations:
                known.add((l.name or "").strip())
            for f in self.plot_flags:
                known.add((f.key or "").strip())
            for no in self.notables:
                known.add((no.name or "").strip())
            for c in self.creatures:
                if isinstance(c, dict):
                    known.add(str(c.get("name", "")).strip())
            for sp in self.spells:
                if isinstance(sp, dict):
                    known.add(str(sp.get("name", "")).strip())
            kept = []
            for r in self.relations:
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
            self.relations = kept

        # ── 日志/幕后事件：只保留最近 N 条 ─────────────────────
        if do_all or scope == "logs":
            if len(self.change_log) > max_change_log:
                removed["logs"] += len(self.change_log) - max_change_log
                self.change_log = self.change_log[-max_change_log:]
            if len(self.background_events) > max_background:
                removed["logs"] += len(self.background_events) - max_background
                self.background_events = self.background_events[-max_background:]

        removed["removed_total"] = sum(
            removed[k] for k in ("npcs", "locations", "flags", "notes", "notables", "relations", "logs")
        )
        return removed

    def maintenance(
        self,
        scope: str = "all",
        older_than_turns: int = 20,
        max_notes: int = 120,
        max_relations: int = 400,
        max_change_log: int = 300,
        max_background: int = 100,
        dry_run: bool = False,
    ) -> dict:
        """清理过期/低价值世界状态；dry_run=True 时在副本上计算，不修改原状态。"""
        target = copy.deepcopy(self) if dry_run else self
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

    def to_player_journal(self) -> dict:
        """生成玩家笔记——仅包含可见信息。

        这是前端侧边栏的数据源。
        """
        # NPC 按态度分组
        allies = []
        enemies = []
        neutrals = []
        for n in self.npcs:
            if not getattr(n, "discovered", True):
                continue  # 玩家尚未见过的 NPC 不暴露
            view = n.to_player_view()
            view["location"] = n.location  # 位置始终可见
            if n.attitude in ("友善", "忠诚"): allies.append(view)
            elif n.attitude in ("敌对",): enemies.append(view)
            else: neutrals.append(view)

        return {
            "scene": {
                "location": self.scene.current_location,
                "time": self.scene.current_time or f"第{self.scene.day_count}天",
                "weather": self.scene.weather,
                "atmosphere": self.scene.atmosphere,
                "npcs_here": self.scene.visible_npcs_here,
            },
            "npcs": {
                "allies": allies,
                "enemies": enemies,
                "neutrals": neutrals,
                # 只统计对玩家可见/已发现的角色，隐藏角色不计入数量
                "total": len(allies) + len(enemies) + len(neutrals),
            },
            "plot_flags": [p.to_player_view() for p in self.plot_flags if p.visible],
            "locations": [l.to_player_view() for l in self.locations if l.discovered],
            # 角色视角笔记——按类型分组
            "character_notes": {
                "npc_notes": [{"target": n.target, "comment": n.character_comment, "clue": n.clue,
                               "turn": n.turn_added}
                              for n in self.character_notes if n.target_type == "npc" and n.visible],
                "event_notes": [{"target": n.target, "comment": n.character_comment, "clue": n.clue,
                                 "turn": n.turn_added}
                                for n in self.character_notes if n.target_type == "event" and n.visible],
                "quest_clues": [{"target": n.target, "comment": n.character_comment, "clue": n.clue,
                                 "turn": n.turn_added}
                                for n in self.character_notes if n.target_type == "quest" and n.visible],
                "location_notes": [{"target": n.target, "comment": n.character_comment, "clue": n.clue,
                                    "turn": n.turn_added}
                                   for n in self.character_notes if n.target_type == "location" and n.visible],
            },
            "world_events": [
                {"turn": e.get("turn"), "text": e.get("public_hint") or e.get("event")}
                for e in self.background_events[-10:] if e.get("public_hint") or e.get("visible")
            ],
            "notables": [n.to_player_view() for n in self.notables if n.discovered],
            "turn_count": self.turn_count,
        }

    def to_context_string(self) -> str:
        """为AI生成完整的世界状态上下文（含隐藏信息——AI需要知道全部）。"""
        lines = []

        # 场景
        sc = self.scene
        lines.append(f"## 当前场景\n- 地点: {sc.current_location}\n- 时间: {sc.current_time or f'第{sc.day_count}天'}\n- 天气: {sc.weather}\n- 氛围: {sc.atmosphere}")
        if sc.visible_npcs_here:
            lines.append(f"- 在场NPC: {', '.join(sc.visible_npcs_here)}")

        if self.world_title:
            lines.append(f"\n## 冒险\n{self.world_title}")

        if self.npcs:
            lines.append("\n## 全部NPC（含隐藏信息——仅你可见，勿直接透露给玩家）")
            for n in self.npcs:
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

        if self.plot_flags:
            lines.append("\n## 剧情进度（含暗线；暗线对玩家隐藏，但你必须持续推进）")
            for f in self.plot_flags:
                icon = {"未触发":"⚪","进行中":"🔵","已完成":"✅","已失败":"❌"}.get(f.status,"⚪")
                tag = " [暗线]" if not f.visible else ""
                line = f"- {icon} {f.key}: {f.status}{tag}"
                if f.description:
                    line += f" — {f.description}"
                if f.consequence:
                    line += f"（后果：{f.consequence}）"
                lines.append(line)

        if self.background_events:
            lines.append("\n## 幕后事件（玩家不在场时发生的进展）")
            for e in self.background_events[-5:]:
                line = f"- [第{e.get('turn', 0)}轮] {e.get('event', '')}"
                if e.get('impact'):
                    line += f"（影响：{e['impact']}）"
                if e.get('public_hint'):
                    line += f" [可被玩家听闻：{e['public_hint']}]"
                lines.append(line)

        try:
            from backend.engine.knowledge_graph import graph_to_context
            kg = graph_to_context(self)
            if kg:
                lines.append("\n" + kg)
        except Exception as e:
            from backend.logging_utils import get_logger
            get_logger("world_state.graph").warning("graph_to_context 注入失败: %s", e, exc_info=True)

        return "\n".join(lines)

    def to_context_compact(self) -> str:
        """紧凑版——每轮AI调用时注入的简要世界状态。"""
        lines = ["## 当前世界状态（每轮必读）"]

        sc = self.scene
        lines.append(f"📍 {sc.current_location} | 🕐 {sc.current_time or f'第{sc.day_count}天'} | 🌤 {sc.weather}")
        if sc.visible_npcs_here:
            lines.append(f"👥 在场: {', '.join(sc.visible_npcs_here)}")

        if self.npcs:
            lines.append("### NPC状态")
            for n in self.npcs[:8]:  # 最多8个，避免token爆炸
                tag = "☠" if not n.alive else ""
                hidden = sum(1 for f in [n.visibility.personality, n.visibility.motivation,
                                         n.visibility.secret, n.visibility.relation_to_plot]
                            if f == "hidden")
                lines.append(f"- {tag}{n.name}({n.role}) 态度:{n.attitude} 位置:{n.location} 隐藏字段:{hidden}")

        if self.plot_flags:
            active = [f for f in self.plot_flags if f.status in ("进行中", "未触发")]
            if active:
                lines.append("### 关键旗标")
                for f in active[:6]:
                    tag = " [暗线]" if not f.visible else ""
                    lines.append(f"- {f.key}: {f.status}{tag}")

        if self.notables:
            notable = [n for n in self.notables if n.discovered]
            if notable:
                lines.append("### 值得注意的场景/物品")
                for n in notable[:6]:
                    lines.append(f"- {n.name}（{n.entry_type}）{n.description[:50]}")

        if self.background_events:
            latest = self.background_events[-1]
            lines.append(f"### 幕后进展（共{len(self.background_events)}条）")
            lines.append(f"- {latest.get('event', '')[:60]}")

        return "\n".join(lines)


def cleanup_world_states(storage_dir: str = "world_states", active_session_ids: list[str] | None = None,
                         max_age_days: int = 7) -> int:
    """清理不再活跃且超过保留期的 world_state JSON 文件。

    存档本身包含 world_state 快照，因此这里的运行期文件可以安全清理。
    """
    import os
    import time

    if not os.path.isdir(storage_dir):
        return 0
    active = set(active_session_ids or [])
    now = time.time()
    removed = 0
    for fn in os.listdir(storage_dir):
        if not fn.endswith(".json"):
            continue
        sid = fn[:-5]
        if sid in active:
            continue
        path = os.path.join(storage_dir, fn)
        try:
            if now - os.path.getmtime(path) > max_age_days * 86400:
                os.remove(path)
                removed += 1
        except OSError:
            continue
    return removed
