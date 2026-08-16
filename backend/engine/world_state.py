"""持久化世界状态——NPC可见度控制、场景追踪、时间系统。

核心设计：
- 每个NPC有 visibility 字典控制哪些字段对玩家可见
- 场景追踪：当前时间、地点、天气、氛围
- 玩家笔记：仅导出可见信息到前端侧边栏
- AI可通过 reveal_info 工具修改可见度
"""

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
        result["level"] = self.level
        result["ac"] = self.ac
        result["hp"] = self.hp
        result["max_hp"] = self.max_hp
        result["attributes"] = self.attributes
        result["skills"] = self.skills
        result["traits"] = self.traits

        # 统计隐藏字段数
        hidden_count = sum(
            1 for f in [v.race, v.role, v.appearance, v.personality,
                        v.motivation, v.secret, v.relation_to_plot]
            if f == "hidden"
        )
        result["_hidden_fields"] = hidden_count
        result["_fully_revealed"] = hidden_count == 0

        return result


@dataclass
class PlotFlag:
    key: str
    status: str = "未触发"
    description: str = ""
    consequence: str = ""
    visible: bool = True  # 对玩家可见？

    def to_player_view(self) -> dict:
        if not self.visible:
            return {"key": "???", "status": "???", "description": ""}
        return {"key": self.key, "status": self.status, "description": self.description}


@dataclass
class LocationEntry:
    name: str
    description: str = ""
    status: str = "可访问"
    secrets: str = ""
    discovered: bool = True  # 玩家是否已发现

    def to_player_view(self) -> dict:
        if not self.discovered:
            return {"name": "???", "description": "尚未发现", "status": "未知"}
        return {"name": self.name, "description": self.description, "status": self.status}


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

    scene: SceneInfo = field(default_factory=SceneInfo)

    # 角色视角笔记
    character_notes: list[CharacterNote] = field(default_factory=list)
    turn_count: int = 0  # 当前轮数

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
                vis_data = n.pop("visibility", {})
                npc = NpcEntry(**{k: v for k, v in n.items()
                                  if k in ["name","race","role","location","attitude",
                                           "alive","appearance","personality","motivation",
                                           "secret","relation_to_plot","notes",
                                           "level","ac","hp","max_hp","attributes","skills","traits"]})
                npc.visibility = NpcVisibility.from_dict(vis_data)
                ws.npcs.append(npc)

            ws.plot_flags = [PlotFlag(**{k: v for k, v in p.items()
                                         if k in ["key","status","description","consequence","visible"]})
                             for p in data.get("plot_flags", [])]
            ws.locations = [LocationEntry(**{k: v for k, v in l.items()
                                             if k in ["name","description","status","secrets","discovered"]})
                            for l in data.get("locations", [])]

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
            "scene": asdict(self.scene),
            "character_notes": [asdict(cn) for cn in self.character_notes],
            "turn_count": self.turn_count,
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
        self.npcs.append(entry)
        self._log_change(f"新增NPC: {entry.name} ({entry.role})")
        self.save()

    def set_flag(self, key: str, status: str, description: str = "", consequence: str = ""):
        for f in self.plot_flags:
            if f.key == key:
                old = f.status
                f.status = status
                if description: f.description = description
                if consequence: f.consequence = consequence
                self._log_change(f"Flag[{key}]: {old} -> {status}")
                self.save()
                return
        self.plot_flags.append(PlotFlag(key=key, status=status,
                                         description=description, consequence=consequence))
        self._log_change(f"新增Flag: {key} = {status}")
        self.save()

    def update_scene(self, **kwargs):
        """更新当前场景信息。同时自动注册场景中出现的未知NPC。"""
        for k, v in kwargs.items():
            if hasattr(self.scene, k):
                setattr(self.scene, k, v)
        # P0-0修复：场景中出现的NPC名若不存在，自动创建默认NpcEntry
        for npc_name in self.scene.visible_npcs_here:
            if not self.get_npc(npc_name):
                self.add_npc(NpcEntry(name=npc_name, role="未知身份", location=self.scene.current_location, attitude="中立"))
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

    def advance_turn(self):
        """推进轮数。"""
        self.turn_count += 1
        # 可选：不每次保存，由调用方决定

    def _log_change(self, desc: str):
        self.change_log.append({
            "time": datetime.now().isoformat(),
            "description": desc,
        })

    def to_player_journal(self) -> dict:
        """生成玩家笔记——仅包含可见信息。

        这是前端侧边栏的数据源。
        """
        # NPC 按态度分组
        allies = []
        enemies = []
        neutrals = []
        for n in self.npcs:
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
                "total": len(self.npcs),
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
            lines.append("\n## 剧情进度")
            for f in self.plot_flags:
                icon = {"未触发":"⚪","进行中":"🔵","已完成":"✅","已失败":"❌"}.get(f.status,"⚪")
                lines.append(f"- {icon} {f.key}: {f.status}")

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
                for f in active[:5]:
                    lines.append(f"- {f.key}: {f.status}")

        return "\n".join(lines)
