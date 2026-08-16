"""分层记忆系统——维持叙事一致性的核心组件。

三层记忆架构：
  第1层 — 活跃上下文：最近N轮完整对话记录
  第2层 — 摘要缓冲区：由旧轮次压缩而成的叙事摘要
  第3层 — 向量长期记忆：关键事实（Phase 3 实现）

记忆系统将三层信息拼接为一个上下文块，注入每次 LLM 调用的 System Prompt。
"""

from dataclasses import dataclass, field


@dataclass
class DialogueTurn:
    """一轮完整的玩家-DM交互记录。"""
    player_input: str        # 玩家输入的行动
    dm_response: str         # DM 的叙事回复
    events: list[str] = field(default_factory=list)  # 本轮的骰子/战斗事件


@dataclass
class MemorySystem:
    """管理单个游戏会话的三层记忆。

    属性:
        turns: 完整对话历史（最新轮次在末尾）
        summary: 旧对话的压缩摘要
        world_facts: 由DM手动或自动记录的重要世界事实
        max_active_turns: 保留多少轮完整对话后才开始压缩
    """

    turns: list[DialogueTurn] = field(default_factory=list)
    summary: str = ""
    world_facts: list[str] = field(default_factory=list)
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

    def add_world_fact(self, fact: str):
        """记录一条重要的世界事实（去重）。"""
        if fact not in self.world_facts:
            self.world_facts.append(fact)

    def build_context(self) -> str:
        """拼接完整的记忆上下文，用于注入 System Prompt。"""
        parts: list[str] = []

        # 摘要缓冲区
        if self.summary:
            parts.append(f"## 之前的故事摘要\n{self.summary}")

        # 世界事实
        if self.world_facts:
            parts.append("## 重要世界事实\n" + "\n".join(f"- {f}" for f in self.world_facts))

        # 活跃对话
        if self.turns:
            parts.append("## 最近发生的事")
            for i, turn in enumerate(self.turns[-self.max_active_turns:], 1):
                parts.append(f"第{i}轮:")
                parts.append(f"  玩家: {turn.player_input}")
                # 截断过长的 DM 回复，避免上下文溢出
                parts.append(f"  DM: {turn.dm_response[:200]}...")
                if turn.events:
                    parts.append(f"  事件: {', '.join(turn.events)}")
                parts.append("")

        return "\n".join(parts)
