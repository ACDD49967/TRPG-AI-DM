"""WorldState 的角色笔记、后台事件与实体关系（从 world_state 拆出）。

方法只读写 `self.character_notes / relations / ...`，不依赖路径或 IO。
"""
from __future__ import annotations

from backend.engine.world_models import CharacterNote


class WorldNoteMixin:
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


    def add_background_event(self, event: dict):
        """记录一条幕后剧情事件，并自动落盘。"""
        event = dict(event or {})
        event.setdefault("turn", self.turn_count)
        self.background_events.append(event)
        # 只保留最近 100 条，避免存档无限膨胀
        if len(self.background_events) > 100:
            self.background_events = self.background_events[-100:]
        self.save()


    def add_or_update_relation(
        self,
        source: str,
        target: str,
        relation: str = "related",
        strength: float | None = None,
        confidence: float | None = None,
        notes: str = "",
    ) -> dict:
        """新增/更新一条显式关系边（亲密度 0-100，置信度 0-1）。"""
        source = (source or "").strip()
        target = (target or "").strip()
        if not source or not target or source == target:
            return {}
        relation = (relation or "related").strip()
        try:
            strength = None if strength is None else max(0.0, min(100.0, float(strength)))
        except (TypeError, ValueError):
            strength = None
        try:
            confidence = None if confidence is None else max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = None
        for rel in self.relations:
            if rel.get("source") == source and rel.get("target") == target and rel.get("relation") == relation:
                if strength is not None:
                    rel["strength"] = strength
                if confidence is not None:
                    rel["confidence"] = confidence
                if notes:
                    rel["notes"] = notes
                rel["turn_updated"] = self.turn_count
                self.save()
                return rel
        rel = {
            "source": source,
            "target": target,
            "relation": relation,
            "strength": strength if strength is not None else 50.0,
            "confidence": confidence if confidence is not None else 0.5,
            "notes": notes or "",
            "turn_added": self.turn_count,
            "turn_updated": self.turn_count,
        }
        self.relations.append(rel)
        self.save()
        return rel

    def get_relations_for(self, name: str) -> list[dict]:
        """返回与某实体相关的所有显式关系边。"""
        name = (name or "").strip()
        if not name:
            return []
        return [r for r in self.relations
                if r.get("source") == name or r.get("target") == name]
