"""剧本持久化存储——保存/加载/列表，区分新剧本与老剧本开新局"""

import json, os, uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime


SCENARIO_DIR = "scenarios"


@dataclass
class ScenarioMeta:
    """剧本元数据。"""
    id: str = ""                    # 唯一ID
    title: str = ""                 # 剧本标题
    description: str = ""           # 简短描述
    summary: str = ""               # 400字左右的剧本总结
    tone: str = "史诗奇幻"          # 基调
    character_name: str = ""        # 创建时的角色名（参考）
    race: str = ""
    char_class: str = ""
    level: int = 1
    score: int = 0                  # 评分
    created_at: str = ""            # 创建时间
    total_sessions: int = 0         # 使用该剧本的游戏次数
    last_played: str = ""           # 最后游玩时间
    tags: list[str] = field(default_factory=list)  # 玩家自定义标签

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("id", None)  # id is the filename
        return d


@dataclass
class Scenario:
    """完整剧本——大纲+世界状态+元数据。"""
    id: str = ""
    meta: ScenarioMeta = field(default_factory=ScenarioMeta)
    world_outline: str = ""         # 完整世界大纲文本
    world_state_json: str = ""      # 结构化世界状态JSON
    reference_script: str = ""      # 玩家原始参考
    source_chunks: list[str] = field(default_factory=list)  # 导入剧本切分后的分块
    notes: str = ""                 # 玩家备注

    @classmethod
    def load(cls, sid: str) -> "Scenario | None":
        path = os.path.join(SCENARIO_DIR, f"{sid}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        s = cls(id=sid)
        s.world_outline = data.get("world_outline", "")
        s.world_state_json = data.get("world_state_json", "")
        s.reference_script = data.get("reference_script", "")
        s.source_chunks = data.get("source_chunks", []) or []
        s.notes = data.get("notes", "")
        meta_data = data.get("meta", {})
        s.meta = ScenarioMeta(
            id=sid,
            title=meta_data.get("title", ""),
            description=meta_data.get("description", ""),
            summary=meta_data.get("summary", ""),
            tone=meta_data.get("tone", "史诗奇幻"),
            character_name=meta_data.get("character_name", ""),
            race=meta_data.get("race", ""),
            char_class=meta_data.get("char_class", ""),
            level=meta_data.get("level", 1),
            score=meta_data.get("score", 0),
            created_at=meta_data.get("created_at", ""),
            total_sessions=meta_data.get("total_sessions", 0),
            last_played=meta_data.get("last_played", ""),
            tags=meta_data.get("tags", []),
        )
        return s

    def save(self):
        os.makedirs(SCENARIO_DIR, exist_ok=True)
        path = os.path.join(SCENARIO_DIR, f"{self.id}.json")
        data = {
            "world_outline": self.world_outline,
            "world_state_json": self.world_state_json,
            "reference_script": self.reference_script,
            "source_chunks": self.source_chunks,
            "notes": self.notes,
            "meta": self.meta.to_dict(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def record_play(self):
        """记录一次游玩。"""
        self.meta.total_sessions += 1
        self.meta.last_played = datetime.now().isoformat()
        self.save()


def list_scenarios() -> list[dict]:
    """列出所有已保存的剧本。"""
    os.makedirs(SCENARIO_DIR, exist_ok=True)
    scenarios = []
    for fname in sorted(os.listdir(SCENARIO_DIR), reverse=True):
        if not fname.endswith(".json"):
            continue
        sid = fname[:-5]
        s = Scenario.load(sid)
        if s:
            scenarios.append({
                "id": sid,
                "title": s.meta.title or "(无标题)",
                "description": s.meta.description or "",
                "summary": s.meta.summary or "",
                "tone": s.meta.tone,
                "score": s.meta.score,
                "created_at": s.meta.created_at,
                "total_sessions": s.meta.total_sessions,
                "last_played": s.meta.last_played,
                "character_name": s.meta.character_name,
                "race": s.meta.race,
                "char_class": s.meta.char_class,
                "tags": s.meta.tags,
            })
    return scenarios


def delete_scenario(sid: str) -> bool:
    """删除剧本。"""
    path = os.path.join(SCENARIO_DIR, f"{sid}.json")
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def create_scenario(world_outline: str = "", world_state_json: str = "",
                    reference_script: str = "", source_chunks: list[str] | None = None,
                    notes: str = "",
                    title: str = "", description: str = "", summary: str = "", tone: str = "",
                    character_name: str = "", race: str = "", char_class: str = "",
                    level: int = 1, score: int = 0) -> Scenario:
    """创建并保存新剧本。"""
    sid = uuid.uuid4().hex[:16]
    s = Scenario(
        id=sid,
        world_outline=world_outline,
        world_state_json=world_state_json,
        reference_script=reference_script,
        source_chunks=source_chunks or [],
        notes=notes,
        meta=ScenarioMeta(
            id=sid, title=title or "未命名冒险",
            description=description, summary=summary, tone=tone, score=score,
            character_name=character_name, race=race, char_class=char_class,
            level=level, created_at=datetime.now().isoformat(),
            total_sessions=0, last_played="",
        ),
    )
    s.save()
    return s
