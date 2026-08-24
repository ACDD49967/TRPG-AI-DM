"""API 请求与响应的 Pydantic 模型定义。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── 请求模型 ──────────────────────────────────────────────

class NewGameRequest(BaseModel):
    """创建新游戏的请求体。"""
    username: str = Field(default="冒险者", min_length=1, max_length=32)
    character_name: str = Field(default="", min_length=0, max_length=32)  # 空→自动生成
    gender: str = Field(default="未指定", max_length=16)  # 男/女/未指定
    race: str = Field(default="人类", max_length=32)
    char_class: str = Field(default="战士", max_length=32)
    attributes: dict[str, int] | None = None  # {str, dex, con, int, wis, cha}
    race_traits: list[str] | None = None       # 种族特性
    class_proficiencies: list[str] | None = None  # 职业熟练项
    api_key: str | None = None                 # 玩家自备的API Key（覆盖环境变量）
    model_name: str | None = None              # 玩家指定的模型（覆盖默认值）
    base_url: str | None = None                # API 地址（默认 OpenAI 兼容）
    thinking_strength: str = Field(default="medium", pattern="^(low|medium|high)$")
    backstory: str | None = None               # AI 生成的背景故事
    world_context: str | None = None           # 玩家提供的剧本/世界设定
    world_outline: str | None = None           # AI生成的完整世界大纲
    world_state_json: str | None = None        # 结构化世界状态JSON（从世界生成接口获得）
    reference_script: str | None = None        # 玩家提供的参考剧本
    scenario_url: str | None = None
    scenario_id: str | None = None
    skill_proficiencies: list[str] | None = None
    skills: dict[str, int] | None = None          # COC/自定义技能具体数值
    feats: list[dict] | None = None
    new_world: bool = True                     # True=全新世界, False=老剧本开新局
    play_mode: str = Field(default="deep", pattern="^(lite|deep)$")  # lite=精简模式, deep=深度模式
    game_system: str = Field(default="dnd5e", pattern="^(dnd5e|dnd4e|coc|custom)$")
    custom_rules: str | None = None            # 自定义规则文本（game_system=custom 时使用）
    luck: int | None = Field(default=None, ge=1, le=99)  # COC 幸运值（可选）
    extension_ids: list[str] = Field(default_factory=list)  # 启用的扩展包 ID 列表
    character_image: str | None = None                     # 角色图片路径（可选）
    custom_classes: list[str] = Field(default_factory=list)  # 剧本专属职业/身份
    custom_skills: list[str] = Field(default_factory=list)   # 剧本专属技能
    extra_attributes: dict[str, str] = Field(default_factory=dict)  # 额外属性


class GenerateBackstoryRequest(BaseModel):
    """根据已有属性请求AI生成背景故事。"""
    character_name: str = Field(min_length=1, max_length=32)
    gender: str = Field(default="未指定", max_length=16)
    race: str = Field(default="人类", max_length=32)
    char_class: str = Field(default="战士", max_length=32)
    attributes: dict[str, int] | None = None  # 已分配的六维属性
    api_key: str | None = None
    model_name: str | None = None
    base_url: str | None = None


class GenerateAttributesRequest(BaseModel):
    """AI根据背景故事生成属性的请求。"""
    character_name: str = Field(min_length=1, max_length=32)
    gender: str = Field(default="未指定", max_length=16)
    race: str = Field(default="人类", max_length=32)
    char_class: str = Field(default="战士", max_length=32)
    backstory: str = Field(default="", max_length=2000)
    attributes: dict[str, int] | None = None  # 可选：已有属性时仅生成背景
    game_system: str = Field(default="dnd5e", pattern="^(dnd5e|dnd4e|coc|custom)$")
    scenario_summary: str | None = None        # 预生成剧本总结，用于沉浸式背景生成
    custom_rules: str | None = None            # 自定义规则文本
    api_key: str | None = None
    model_name: str | None = None
    base_url: str | None = None
    thinking_strength: str = Field(default="medium", pattern="^(low|medium|high)$")


class ActionRequest(BaseModel):
    """玩家提交行动的请求体。"""
    player_input: str = Field(min_length=1, max_length=2000)


class WorldGenRequest(BaseModel):
    """世界大纲生成请求。"""
    description: str = Field(min_length=1, max_length=3000)  # 玩家对世界的描述
    username: str = Field(default="default", min_length=1, max_length=32)
    character_name: str = Field(default="冒险者", max_length=32)
    race: str = Field(default="人类", max_length=32)
    char_class: str = Field(default="战士", max_length=32)
    character_level: int = Field(default=1, ge=1, le=20)
    tone: str = Field(default="史诗奇幻", max_length=64)  # 基调
    game_system: str = Field(default="dnd5e", pattern="^(dnd5e|dnd4e|coc|custom)$")
    custom_rules: str | None = None            # 自定义规则文本（game_system=custom 时使用）
    custom_classes: list[str] = Field(default_factory=list)  # 剧本专属职业/身份
    custom_skills: list[str] = Field(default_factory=list)   # 剧本专属技能
    extra_attributes: dict[str, str] = Field(default_factory=dict)  # 额外属性
    api_key: str | None = None
    model_name: str | None = None
    base_url: str | None = None
    thinking_strength: str = Field(default="medium", pattern="^(low|medium|high)$")


# ── 响应模型 ──────────────────────────────────────────────

class NewGameResponse(BaseModel):
    session_id: str
    character_id: str
    sse_url: str


class ActionAcceptedResponse(BaseModel):
    accepted: bool = True


# ── SSE 事件数据模型 ──────────────────────────────────────

class IntroEvent(BaseModel):
    """开场事件数据。"""
    scene: str
    mood: str = "neutral"


class NarrativeToken(BaseModel):
    """打字机效果——单个叙事 token。"""
    token: str
    seq: int


class NarrativeFlush(BaseModel):
    """跳过打字机效果——完整段落直接显示。"""
    full_text: str


class DiceRollEvent(BaseModel):
    """骰子检定结果。"""
    skill: str
    dc: int
    roll: int
    modifier: int = 0
    result: str  # "成功" | "失败" | "大成功" | "大失败"


class StateUpdateEvent(BaseModel):
    """角色状态变更（仅包含变化的字段）。"""
    hp: int | None = None
    max_hp: int | None = None
    mp: int | None = None
    max_mp: int | None = None
    xp: int | None = None
    gold: int | None = None
    inventory: dict[str, Any] | None = None
    level: int | None = None


class ChoicesEvent(BaseModel):
    """DM 给出的建议选项。"""
    options: list[str]


class GameEventData(BaseModel):
    """游戏事件数据（战斗开始/结束、遭遇等）。"""
    type: str  # combat_start | combat_end | encounter | quest_update
    description: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class ErrorEvent(BaseModel):
    """错误事件。"""
    code: str
    msg: str


class EndOfTurnEvent(BaseModel):
    """本轮处理完毕——前端解锁输入框。"""
    pass
