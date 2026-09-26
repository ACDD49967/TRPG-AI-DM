"""记忆上下文的渲染：把三层记忆拼成注入 System Prompt 的文本块。

从 `memory` 拆出（那边只留 DialogueTurn 与对话轮次/压缩），并把两段共有渲染
（摘要/大事件/暗线/人物影响/世界事实）抽成 `_render_shared_blocks`——
原来 `build_essential_context` 与 `build_context` 各维护一份相同逻辑，容易改漏。
"""
from __future__ import annotations


class MemoryContextMixin:
    def _render_shared_blocks(self) -> list[str]:
        """两段上下文共有的部分（不含最近对话）。"""
        parts: list[str] = []

        if self.summary:
            parts.append(f"## 之前的故事摘要\n{self.summary}")

        if self.major_events:
            parts.append("## 大事件记忆")
            for ev in self.major_events[-8:]:
                line = f"- [第{ev.get('turn', 0)}轮] {ev.get('title', '')}"
                if ev.get("description"):
                    line += f"：{ev['description']}"
                if ev.get("impact"):
                    line += f"（影响：{ev['impact']}）"
                parts.append(line)

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

        if self.character_impacts:
            parts.append("## 重要人物影响")
            for c in self.character_impacts[-10:]:
                line = f"- {c.get('name', '')}"
                if c.get("impact"):
                    line += f"：{c['impact']}"
                if c.get("event"):
                    line += f"（事件：{c['event']}）"
                parts.append(line)

        if self.world_facts:
            parts.append("## 重要世界事实\n" + "\n".join(f"- {f}" for f in self.world_facts))

        return parts

    def build_essential_context(self) -> str:
        """构建不包含“最近发生的事”的核心记忆上下文。

        用于模块化 DM 回合：
        - 保留摘要、大事件、暗线、人物影响与世界事实；
        - 不重复注入最近对话（这些已经作为 messages 注入）；
        - 在显著减少 tokens 的同时避免剧情记忆缺失。
        """
        return "\n".join(self._render_shared_blocks())

    def build_context(self) -> str:
        """拼接完整的记忆上下文，用于注入 System Prompt。"""
        parts = self._render_shared_blocks()

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
