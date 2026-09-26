"""单个活跃游戏会话的运行时状态（从 session.py 拆出）。

字段涵盖事件流缓冲、分层记忆、遥测、行动经济账本、濒死标记与并发锁；
会话生命周期与 SSE 推送分别在 session_manager / sse_bus，`session.py` 只做再导出。
"""
import asyncio
import time
from collections import deque
from dataclasses import dataclass, field

from backend.config import settings
from backend.engine.memory import MemorySystem
from backend.telemetry import TelemetryCollector


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
    opening_text: str = ""

    # 事件流 —— 广播给每个 SSE 订阅者，并保存环形历史用于断线重放
    subscribers: set[asyncio.Queue] = field(default_factory=set, repr=False)
    event_history: deque = field(default_factory=lambda: deque(maxlen=500), repr=False)
    seq: int = 0  # 事件序号，用于断线重连
    last_active_at: float = field(default_factory=time.time)

    # 分层记忆
    memory: MemorySystem = field(default_factory=MemorySystem)

    # 当前会话的回合耗时、模型调用次数和 token 统计
    telemetry: TelemetryCollector = field(default_factory=TelemetryCollector, repr=False)

    # 状态机
    status: str = "active"  # active | paused | ended
    in_combat: bool = False

    # 速率限制
    last_action_time: float = 0.0

    # 中断控制 —— 设置此标志以停止当前 LLM 生成
    _abort_flag: bool = field(default=False, repr=False)

    # 持久化世界状态
    world_state: object | None = field(default=None, repr=False)

    # 兼容旧会话结构；回合响应不再缓存，避免重复输入跳过结算。
    response_cache: dict[str, str] = field(default_factory=dict, repr=False)

    # 游戏内临时覆写（生物/城市），不影响知识库
    bestiary_overrides: dict[str, dict] = field(default_factory=dict, repr=False)
    city_overrides: dict[str, dict] = field(default_factory=dict, repr=False)

    # 本轮已行动敌人记录：防止同一敌人一个回合被 enemy_attack 重复结算
    enemy_attack_log: dict[str, int] = field(default_factory=dict, repr=False)
    # 追逐中的冲刺计数：{行动者: 已冲刺次数}（5e：超过 3+体质调整值就要掷体质豁免）
    chase_dashes: dict[str, int] = field(default_factory=dict, repr=False)
    # 本回合的行动经济账本：{行动者: {来源: 已用次数}}，来源 "primary" 为主行动
    turn_action_ledger: dict[str, dict[str, int]] = field(default_factory=dict, repr=False)
    # 本轮已执行的结算类工具结果：同回合相同调用直接复用，避免并发子 Agent 重复结算
    turn_tool_results: dict[str, str] = field(default_factory=dict, repr=False)
    # 先攻表（backend.engine.initiative.InitiativeTracker）：战斗中由后端维护顺序与回合余额
    initiative: object | None = field(default=None, repr=False)
    # 战场态势（backend.engine.battlefield.Battlefield）：距离档位与掩体
    battlefield: object | None = field(default=None, repr=False)

    # 濒死状态（D&D 系）：HP 0 倒地昏迷，每回合必须掷死亡豁免
    dying: bool = False
    # 角色已永久死亡（3 次死亡豁免失败）；复活（HP 恢复为正）后清除
    character_dead: bool = False
    # 需要在下一轮注入给主 DM 的系统提示（安全网用，玩家不可见）
    pending_system_hints: list[str] = field(default_factory=list, repr=False)

    # 每会话串行锁：防止同一会话的多个玩家行动并发修改世界状态
    action_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    # 工具执行锁：多个专业子 Agent 并发调用工具时，串行化状态变更
    tool_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    # P1-15: 写入型子 Agent 的整段串行锁（避免读-改-写交错造成丢失更新）
    agent_write_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

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
