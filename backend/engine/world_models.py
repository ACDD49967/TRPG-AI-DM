"""世界状态数据模型（NPC/地点/旗标/场景/笔记），从 world_state 拆出。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
    conditions: list = field(default_factory=list)   # 当前状态：俯卧/束缚/中毒等
    equipment: list = field(default_factory=list)    # 可见装备（武器/护甲/随身物品）
    related_locations: list = field(default_factory=list)  # 关联地点名
    related_npcs: list = field(default_factory=list)       # 关联NPC名
    related_creatures: list = field(default_factory=list)  # 关联生物/怪物名
    image_path: str = ""
    importance: str = "minor"       # major=重要NPC（完整卡） minor=简单NPC（简要卡）
    discovered: bool = True         # 玩家是否已见过/知道该NPC；False 时不出现在玩家笔记
    turn_added: int = 0             # 首次进入世界状态的轮数
    turn_last_seen: int = 0         # 最近一次出场/被提及的轮数
    xp_awarded: bool = False        # 击败经验是否已结算（防止重复发奖）
    legendary_resistance: int = 0   # 剩余传奇抗性次数
    legendary_resistance_max: int = 0
    concentration: str = ""         # 正在专注的法术名（怪物施法者）
    visibility: NpcVisibility = field(default_factory=NpcVisibility)

    def to_player_view(self) -> dict:
        """生成对玩家可见的信息（根据visibility过滤）。"""
        v = self.visibility
        result = {
            "name": self.name if v.name == "visible" else "???",
            "attitude": self.attitude,
            "alive": self.alive if v.alive == "visible" else None,
            "conditions": self.conditions,
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
                "legendary_resistance": self.legendary_resistance,
                "legendary_resistance_max": self.legendary_resistance_max,
                "concentration": self.concentration,
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
                "legendary_resistance": 0,
                "legendary_resistance_max": 0,
                "concentration": "",
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
    light: str = ""              # 光照：明亮/微光/黑暗（见 light_rules，未写时不猜）
    light_source: str = ""       # 光源描述，如"火把""月光"
