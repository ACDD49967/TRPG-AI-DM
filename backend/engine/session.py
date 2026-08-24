"""游戏会话管理器——管理活跃会话、事件队列和 SSE 推送。

MVP 阶段使用内存存储，后续可迁移至 Redis 以支持多进程部署。
"""

import asyncio
import json
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

from backend.config import settings
from backend.engine.memory import MemorySystem


@dataclass
class GameSessionState:
    """单个活跃游戏会话的运行时状态。"""

    session_id: str
    character_id: str
    character_name: str
    character_info: dict  # 种族、职业、等级、属性等
    username: str = "default"

    # 玩家自定义 LLM 配置（覆盖全局设置）
    api_key: str | None = None
    model_name: str | None = None
    base_url: str | None = None
    thinking_strength: str = "medium"
    resumed: bool = False

    # 事件流 —— 通过 asyncio.Queue 跨协程传递 SSE 事件
    event_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    seq: int = 0  # 事件序号，用于断线重连

    # 分层记忆
    memory: MemorySystem = field(default_factory=MemorySystem)

    # 状态机
    status: str = "active"  # active | paused | ended
    in_combat: bool = False

    # 速率限制
    last_action_time: float = 0.0

    # 中断控制 —— 设置此标志以停止当前 LLM 生成
    _abort_flag: bool = field(default=False, repr=False)

    # 持久化世界状态
    world_state: object | None = field(default=None, repr=False)

    # 简单问答缓存：相同信息类问题直接返回，避免重复消耗 token
    response_cache: dict[str, str] = field(default_factory=dict, repr=False)

    # 游戏内临时覆写（生物/城市），不影响知识库
    bestiary_overrides: dict[str, dict] = field(default_factory=dict, repr=False)
    city_overrides: dict[str, dict] = field(default_factory=dict, repr=False)

    def check_rate_limit(self) -> bool:
        """检查距上次操作是否已超过速率限制。"""
        now = time.time()
        return now - self.last_action_time >= settings.RATE_LIMIT_SECONDS

    def mark_action(self):
        """记录当前时间作为最近一次操作时间。"""
        self.last_action_time = time.time()

    def request_abort(self):
        """请求中断当前生成。"""
        self._abort_flag = True

    def reset_abort(self):
        """清除中断标志，准备新一轮生成。"""
        self._abort_flag = False

    @property
    def aborted(self) -> bool:
        return self._abort_flag


class SessionManager:
    """全局会话管理器。

    管理所有活跃游戏会话的生命周期。
    MVP 阶段使用内存字典存储，生产环境需替换为 Redis 后端。
    """

    def __init__(self):
        self._sessions: dict[str, GameSessionState] = {}

    def create_session(
        self,
        session_id: str,
        character_id: str,
        character_name: str,
        character_info: dict,
        api_key: str | None = None,
        model_name: str | None = None,
        username: str = "default",
    ) -> GameSessionState:
        """创建并注册一个新的游戏会话。"""
        state = GameSessionState(
            session_id=session_id,
            character_id=character_id,
            character_name=character_name,
            character_info=character_info,
            api_key=api_key,
            model_name=model_name,
            username=username,
        )
        self._sessions[session_id] = state
        return state

    def get_session(self, session_id: str) -> GameSessionState | None:
        """根据 ID 查找活跃会话。"""
        return self._sessions.get(session_id)

    def remove_session(self, session_id: str):
        """从内存中移除会话（不影响数据库记录）。"""
        self._sessions.pop(session_id, None)

    def is_active(self, session_id: str) -> bool:
        """检查会话是否在内存中（是否活跃）。"""
        return session_id in self._sessions


# 全局单例
session_manager = SessionManager()


# ── SSE 事件格式化工具 ────────────────────────────────────

def _format_sse(event_type: str, data: dict | None = None, seq: int = 0) -> str:
    """将事件格式化为 SSE (Server-Sent Events) 协议格式。

    格式: event: <type>\ndata: <json>\n\n
    """
    payload = json.dumps(data or {}, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n"


async def sse_event_generator(
    state: GameSessionState,
) -> AsyncGenerator[str, None]:
    """异步生成器——从会话队列中读取事件并生成 SSE 格式字符串。

    连接建立后，先由 AI 生成动态开场白（打字机流式推送），
    然后进入事件队列循环。每30秒发送心跳保活。
    """
    # 第一步：AI 生成动态开场白
    from backend.engine.dm_agent import generate_opening_scene

    if getattr(state, "resumed", False):
        # 读档恢复：直接推送完整对话历史，前端原样渲染，不生成新开场
        turns = [
            {"player_input": t.player_input, "dm_response": t.dm_response}
            for t in state.memory.turns
        ]
        await push_event(state, "history", {"turns": turns})
    else:
        try:
            await asyncio.wait_for(generate_opening_scene(state), timeout=60)
        except Exception:
            await push_narrative_token(state, f"欢迎，{state.character_name}。冒险开始了…")

    # 推送初始角色状态到前端 —— 这样StatusPanel可以正确显示HP/属性/物品
    info = state.character_info
    await push_event(state, "state_update", {
        "hp": info.get("hp", 30),
        "max_hp": info.get("max_hp", 30),
        "mp": info.get("mp", 10),
        "max_mp": info.get("max_mp", 10),
        "xp": info.get("xp", 0),
        "gold": info.get("gold", 10),
        "level": info.get("level", 1),
        "inventory": info.get("inventory", {}).get("items", []) if isinstance(info.get("inventory"), dict) else [],
        "attributes": info.get("attributes", {}),
        "ac": info.get("ac", 12),
        "character_name": state.character_name,
        "race": info.get("race", ""),
        "char_class": info.get("char_class", ""),
        "gender": info.get("gender", ""),
        "game_system": info.get("game_system", "dnd5e"),
        "username": info.get("username", "default"),
        "character_image": info.get("character_image", ""),
        "scenario_id": info.get("scenario_id", ""),
        "backstory": info.get("backstory", ""),
        "skill_proficiencies": info.get("skill_proficiencies", []),
        "skills": info.get("skills", {}),
        "saves": info.get("saves", {}),
        "passive_perception": info.get("passive_perception", 10),
        "feats": info.get("feats", []),
        "custom_classes": info.get("custom_classes", []),
        "custom_skills": info.get("custom_skills", []),
        "extra_attributes": info.get("extra_attributes", {}),
        "race_traits": info.get("race_traits", []),
        "class_proficiencies": info.get("class_proficiencies", []),
        "hit_die": info.get("hit_die", ""),
        "san": info.get("san", info.get("max_san", 0)),
        "maxSan": info.get("max_san", info.get("san", 0)),
        "luck": info.get("luck", 0),
        "healing_surges": info.get("healing_surges", 0),
        "max_healing_surges": info.get("max_healing_surges", 0),
        "surge_value": info.get("surge_value", 0),
        "proficiency_bonus": info.get("proficiency_bonus", 2),
        "spell_slots": info.get("spell_slots", []),
        "class_resources": info.get("class_resources", []),
        "known_spells": info.get("known_spells", []),
        "action_points": info.get("action_points", 1),
        "fortitude": info.get("fortitude", 10),
        "reflex": info.get("reflex", 10),
        "will": info.get("will", 10),
        "damage_bonus": info.get("damage_bonus", "0"),
        "build": info.get("build", 0),
    })

    # 将 end_of_turn 推入队列（排在叙事token之后）
    await push_event(state, "end_of_turn", {})

    while state.status == "active":
        try:
            event_type, data = await asyncio.wait_for(
                state.event_queue.get(), timeout=30.0
            )
        except asyncio.TimeoutError:
            # 心跳保活
            yield ": heartbeat\n\n"
            continue

        if event_type is None:
            # 哨兵值，停止生成器
            break

        state.seq += 1
        data["seq"] = state.seq
        yield _format_sse(event_type, data, state.seq)


async def push_event(
    state: GameSessionState,
    event_type: str,
    data: dict | None = None,
):
    """向会话的 SSE 队列推送一个事件。"""
    await state.event_queue.put((event_type, data or {}))


async def push_narrative_token(state: GameSessionState, token: str):
    """推送单个叙事 token，用于打字机效果。"""
    await push_event(state, "narrative", {"token": token})


async def push_narrative_flush(state: GameSessionState, full_text: str):
    """推送完整叙事文本，跳过打字机直接显示。"""
    await push_event(state, "narrative_flush", {"full_text": full_text})
