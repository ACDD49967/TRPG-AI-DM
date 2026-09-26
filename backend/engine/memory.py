"""分层记忆系统——维持叙事一致性的核心组件。

三层记忆架构：
  第1层 — 活跃上下文：最近N轮完整对话记录
  第2层 — 摘要缓冲区：由旧轮次压缩而成的叙事摘要
  第3层 — 向量长期记忆：关键事实（Phase 3 实现）

本模块只留 DialogueTurn、记忆字段与"轮次写入/压缩"；剧情记忆层（世界事实/大事件/
暗线/人物影响）在 `memory_plot`，上下文渲染在 `memory_context`，由 MemorySystem 组合。
"""

from dataclasses import dataclass, field

from backend.engine.memory_context import MemoryContextMixin
from backend.engine.memory_plot import PlotMemoryMixin


@dataclass
class DialogueTurn:
    """一轮完整的玩家-DM交互记录。"""
    player_input: str        # 玩家输入的行动
    dm_response: str         # DM 的叙事回复
    events: list[str] = field(default_factory=list)  # 本轮的骰子/战斗事件


@dataclass
class MemorySystem(PlotMemoryMixin, MemoryContextMixin):
    """管理单个游戏会话的三层记忆。

    属性:
        turns: 完整对话历史（最新轮次在末尾）
        summary: 旧对话的压缩摘要
        world_facts: 由DM手动或自动记录的重要世界事实
        major_events: 大事件记忆（含影响）
        hidden_threads: 剧情暗线（伏笔/幕后进展）
        character_impacts: 重要人物及其影响
        max_active_turns: 保留多少轮完整对话后才开始压缩
    """

    turns: list[DialogueTurn] = field(default_factory=list)
    summary: str = ""
    world_facts: list[str] = field(default_factory=list)
    major_events: list[dict] = field(default_factory=list)
    hidden_threads: list[dict] = field(default_factory=list)
    character_impacts: list[dict] = field(default_factory=list)
    max_active_turns: int = 10
    summary_trigger: int = 8  # 超过此轮数触发摘要压缩

    def add_turn(
        self,
        player_input: str,
        dm_response: str,
        events: list[str] | None = None,
    ):
        """记录一轮完成的对话。"""
        self.turns.append(DialogueTurn(
            player_input=player_input,
            dm_response=dm_response,
            events=events or [],
        ))
        self._maybe_summarise()

    def _maybe_summarise(self):
        """当对话轮数超过阈值时触发压缩。

        MVP阶段使用简单的截断策略——丢弃最旧轮次并附加一行提示。
        Phase 2+ 将替换为轻量 LLM 调用进行智能摘要。
        """
        if len(self.turns) <= self.summary_trigger:
            return

        overflow = len(self.turns) - self.max_active_turns
        if overflow <= 0:
            return

        # 保留最近的轮次，压缩旧轮次
        old_turns = self.turns[:overflow]
        self.turns = self.turns[overflow:]

        # 提取式摘要（后续阶段升级为 LLM 摘要）
        key_points = []
        for t in old_turns:
            key_points.append(f"- 玩家: {t.player_input[:60]}... → DM叙述了结果")
            for ev in t.events:
                key_points.append(f"  [{ev}]")

        if key_points:
            # 只保留最近5个关键点，避免摘要过长
            new_summary = "先前发生的事:\n" + "\n".join(key_points[-5:])
            if self.summary:
                self.summary = self.summary + "\n" + new_summary
            else:
                self.summary = new_summary
