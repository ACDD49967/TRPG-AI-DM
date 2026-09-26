"""记忆系统的剧情记忆层：世界事实、大事件、暗线与人物影响。

从 `memory` 拆出（那边只留 DialogueTurn 与对话轮次/压缩）。
由 `MemorySystem` 组合使用，方法名与语义不变。
"""
from __future__ import annotations


class PlotMemoryMixin:
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

