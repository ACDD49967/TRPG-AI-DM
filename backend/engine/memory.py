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

    def add_world_fact(self, fact: str):
        """记录一条重要的世界事实（去重）。"""
        if fact not in self.world_facts:
            self.world_facts.append(fact)

    def add_major_event(
        self,
        title: str,
        description: str = "",
        impact: str = "",
        turn: int = 0,
        npcs: list | None = None,
        locations: list | None = None,
    ):
        """记录大事件：标题、简述、对世界/人物的影响。按标题去重。"""
        title = (title or "").strip()
        if not title:
            return
        entry = {
            "turn": int(turn or 0),
            "title": title,
            "description": (description or "").strip(),
            "impact": (impact or "").strip(),
            "npcs": list(npcs or []),
            "locations": list(locations or []),
        }
        for ev in self.major_events:
            if ev.get("title") == title:
                ev.update(entry)
                return
        self.major_events.append(entry)
        # 防止无限增长：只保留最近 60 条
        if len(self.major_events) > 60:
            self.major_events = self.major_events[-60:]

    def add_hidden_thread(
        self,
        key: str,
        description: str = "",
        status: str = "未触发",
        related_npcs: list | None = None,
        related_locations: list | None = None,
        progress: str = "",
        turn: int = 0,
    ):
        """记录/更新一条剧情暗线。key 相同视为同一条暗线。"""
        key = (key or "").strip()
        if not key:
            return
        entry = {
            "key": key,
            "description": (description or "").strip(),
            "status": status if status in ("未触发", "进行中", "已完成", "已失败") else "未触发",
            "progress": (progress or "").strip(),
            "related_npcs": list(related_npcs or []),
            "related_locations": list(related_locations or []),
            "turn": int(turn or 0),
        }
        for ht in self.hidden_threads:
            if ht.get("key") == key:
                ht.update({k: v for k, v in entry.items() if v or k in ("status",)})
                return
        self.hidden_threads.append(entry)
        if len(self.hidden_threads) > 40:
            self.hidden_threads = self.hidden_threads[-40:]

    def update_hidden_thread(
        self,
        key: str,
        status: str | None = None,
        progress: str = "",
        turn: int = 0,
    ):
        """推进已有暗线；不存在时以最小信息创建一条。"""
        key = (key or "").strip()
        if not key:
            return
        for ht in self.hidden_threads:
            if ht.get("key") == key:
                if status and status in ("未触发", "进行中", "已完成", "已失败"):
                    ht["status"] = status
                if progress:
                    ht["progress"] = progress
                if turn:
                    ht["turn"] = int(turn)
                return
        self.add_hidden_thread(key=key, status=status or "未触发", progress=progress, turn=turn)

    def add_character_impact(
        self,
        name: str,
        impact: str,
        event: str = "",
        turn: int = 0,
    ):
        """记录重要人物受到的/造成的影响。"""
        name = (name or "").strip()
        impact = (impact or "").strip()
        if not name or not impact:
            return
        entry = {
            "name": name,
            "impact": impact,
            "event": (event or "").strip(),
            "turn": int(turn or 0),
        }
        # 同一个人 + 同一条影响原文视为重复
        for c in self.character_impacts:
            if c.get("name") == name and c.get("impact") == impact:
                c.update(entry)
                return
        self.character_impacts.append(entry)
        if len(self.character_impacts) > 60:
            self.character_impacts = self.character_impacts[-60:]

    def build_context(self) -> str:
        """拼接完整的记忆上下文，用于注入 System Prompt。"""
        parts: list[str] = []

        # 摘要缓冲区
        if self.summary:
            parts.append(f"## 之前的故事摘要\n{self.summary}")

        # 大事件记忆（含影响）
        if self.major_events:
            parts.append("## 大事件记忆")
            for ev in self.major_events[-8:]:
                line = f"- [第{ev.get('turn', 0)}轮] {ev.get('title', '')}"
                if ev.get("description"):
                    line += f"：{ev['description']}"
                if ev.get("impact"):
                    line += f"（影响：{ev['impact']}）"
                parts.append(line)

        # 剧情暗线进度（只列未完成/进行中的暗线，控制 token）
        active_threads = [h for h in self.hidden_threads
                          if h.get("status") in ("未触发", "进行中")]
        if active_threads:
            parts.append("## 暗线进度")
            for h in active_threads[-6:]:
                line = f"- {h.get('key', '')} [{h.get('status', '未触发')}]"
                if h.get("description"):
                    line += f"：{h['description']}"
                if h.get("progress"):
                    line += f"（最近：{h['progress']}）"
                parts.append(line)

        # 重要人物影响
        if self.character_impacts:
            parts.append("## 重要人物影响")
            for c in self.character_impacts[-10:]:
                line = f"- {c.get('name', '')}"
                if c.get("impact"):
                    line += f"：{c['impact']}"
                if c.get("event"):
                    line += f"（事件：{c['event']}）"
                parts.append(line)

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
