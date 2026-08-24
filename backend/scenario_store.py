"""剧本持久化存储——保存/加载/列表，区分新剧本与老剧本开新局。

隔离规则：新剧本保存到 scenarios/{username}/ 目录；
历史遗留的 scenarios/{id}.json 仅对 default 用户可见，作为迁移前的兼容层。
"""

import json
import os
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime


SCENARIO_DIR = "scenarios"


def _safe_username(username: str | None) -> str:
    """用户名转安全目录名。"""
    name = re.sub(r"[^0-9A-Za-z\u4e00-\u9fa5_-]", "_", (username or "").strip())
    if not name or name in (".", ".."):
        return "default"
    return name[:64]


def _user_scenario_dir(username: str | None) -> str:
    return os.path.join(SCENARIO_DIR, _safe_username(username or "default"))


def _candidate_paths(sid: str, username: str | None) -> list[str]:
    """按用户名返回剧本文件候选路径（先用户目录，后 legacy 兼容目录）。"""
    paths = []
    if username:
        paths.append(os.path.join(_user_scenario_dir(username), f"{sid}.json"))
        if _safe_username(username) == "default":
            paths.append(os.path.join(SCENARIO_DIR, f"{sid}.json"))
    else:
        paths.append(os.path.join(SCENARIO_DIR, f"{sid}.json"))
    return paths


@dataclass
class ScenarioMeta:
    """剧本元数据。"""
    id: str = ""                    # 唯一ID
    title: str = ""                 # 剧本标题
    description: str = ""           # 简短描述
    summary: str = ""               # 400字左右的剧本总结
    system: str = "dnd5e"           # 规则系统: dnd5e/dnd4e/coc/custom
    tone: str = "史诗奇幻"          # 基调
    character_name: str = ""        # 创建时的角色名（参考）
    race: str = ""
    char_class: str = ""
    level: int = 1
    score: int = 0                  # 评分
    created_at: str = ""            # 创建时间
    total_sessions: int = 0         # 使用该剧本的游戏次数
    last_played: str = ""           # 最后游玩时间
    username: str = ""              # 所属用户（空=legacy 未隔离数据）
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
    custom_rules: str = ""          # 自定义规则文本（system=custom 时使用）
    custom_classes: list[str] = field(default_factory=list)   # 剧本专属职业/身份
    custom_skills: list[str] = field(default_factory=list)    # 剧本专属技能
    extra_attributes: dict = field(default_factory=dict)      # 额外属性/规则特色字段
    notes: str = ""                 # 玩家备注

    @classmethod
    def load(cls, sid: str, username: str | None = None) -> "Scenario | None":
        """加载剧本。指定 username 时仅查找该用户的目录（default 兼容 legacy 根目录）。"""
        for path in _candidate_paths(sid, username):
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            s = cls(id=sid)
            s.world_outline = data.get("world_outline", "")
            s.world_state_json = data.get("world_state_json", "")
            s.reference_script = data.get("reference_script", "")
            s.source_chunks = data.get("source_chunks", []) or []
            s.custom_rules = data.get("custom_rules", "")
            s.custom_classes = data.get("custom_classes", []) or []
            s.custom_skills = data.get("custom_skills", []) or []
            s.extra_attributes = data.get("extra_attributes", {}) or {}
            s.notes = data.get("notes", "")
            meta_data = data.get("meta", {})
            s.meta = ScenarioMeta(
                id=sid,
                title=meta_data.get("title", ""),
                description=meta_data.get("description", ""),
                summary=meta_data.get("summary", ""),
                system=meta_data.get("system", "dnd5e"),
                tone=meta_data.get("tone", "史诗奇幻"),
                character_name=meta_data.get("character_name", ""),
                race=meta_data.get("race", ""),
                char_class=meta_data.get("char_class", ""),
                level=meta_data.get("level", 1),
                score=meta_data.get("score", 0),
                created_at=meta_data.get("created_at", ""),
                total_sessions=meta_data.get("total_sessions", 0),
                last_played=meta_data.get("last_played", ""),
                username=meta_data.get("username", ""),
                tags=meta_data.get("tags", []),
            )
            return s
        return None

    def save(self):
        if self.meta.username:
            directory = _user_scenario_dir(self.meta.username)
        else:
            directory = SCENARIO_DIR
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, f"{self.id}.json")
        data = {
            "world_outline": self.world_outline,
            "world_state_json": self.world_state_json,
            "reference_script": self.reference_script,
            "source_chunks": self.source_chunks,
            "custom_rules": self.custom_rules,
            "custom_classes": self.custom_classes,
            "custom_skills": self.custom_skills,
            "extra_attributes": self.extra_attributes,
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


def _migrate_legacy_scenarios(username: str):
    """把 legacy 根目录剧本迁移到当前用户目录，使已有剧本立即可见。"""
    safe = _safe_username(username)
    if safe == "default" or not os.path.isdir(SCENARIO_DIR):
        return
    for fname in os.listdir(SCENARIO_DIR):
        if not fname.endswith(".json"):
            continue
        legacy = os.path.join(SCENARIO_DIR, fname)
        try:
            with open(legacy, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        owner = (data.get("meta") or {}).get("username", "")
        if owner and owner != username:
            continue
        data.setdefault("meta", {})["username"] = username
        target_dir = _user_scenario_dir(username)
        os.makedirs(target_dir, exist_ok=True)
        with open(os.path.join(target_dir, fname), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        try:
            os.remove(legacy)
        except Exception:
            pass


def list_scenarios(username: str | None = None) -> list[dict]:
    """列出用户可见的剧本。default 用户同时可见 legacy 根目录剧本。"""
    os.makedirs(SCENARIO_DIR, exist_ok=True)
    if username:
        _migrate_legacy_scenarios(username)
    directories: list[str] = []
    if username:
        directories.append(_user_scenario_dir(username))
        if _safe_username(username) == "default":
            directories.append(SCENARIO_DIR)
    else:
        directories.append(SCENARIO_DIR)

    seen: set[str] = set()
    scenarios = []
    for directory in directories:
        if not os.path.isdir(directory):
            continue
        for fname in sorted(os.listdir(directory), reverse=True):
            if not fname.endswith(".json"):
                continue
            sid = fname[:-5]
            if sid in seen:
                continue
            seen.add(sid)
            s = Scenario.load(sid, username)
            if s:
                scenarios.append({
                    "id": sid,
                    "title": s.meta.title or "(无标题)",
                    "description": s.meta.description or "",
                    "summary": s.meta.summary or "",
                    "system": s.meta.system or "dnd5e",
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


def delete_scenario(sid: str, username: str | None = None) -> bool:
    """删除剧本（仅用户可见路径）。"""
    for path in _candidate_paths(sid, username):
        if os.path.exists(path):
            os.remove(path)
            return True
    return False


def create_scenario(world_outline: str = "", world_state_json: str = "",
                    reference_script: str = "", source_chunks: list[str] | None = None,
                    custom_rules: str = "", custom_classes: list[str] | None = None,
                    custom_skills: list[str] | None = None,
                    extra_attributes: dict | None = None,
                    notes: str = "",
                    title: str = "", description: str = "", summary: str = "",
                    system: str = "dnd5e", tone: str = "",
                    character_name: str = "", race: str = "", char_class: str = "",
                    level: int = 1, score: int = 0,
                    username: str | None = None) -> Scenario:
    """创建并保存新剧本（按用户名隔离）。"""
    sid = uuid.uuid4().hex[:16]
    s = Scenario(
        id=sid,
        world_outline=world_outline,
        world_state_json=world_state_json,
        reference_script=reference_script,
        source_chunks=source_chunks or [],
        custom_rules=custom_rules,
        custom_classes=custom_classes or [],
        custom_skills=custom_skills or [],
        extra_attributes=extra_attributes or {},
        notes=notes,
        meta=ScenarioMeta(
            id=sid, title=title or "未命名冒险",
            description=description, summary=summary, system=system, tone=tone, score=score,
            character_name=character_name, race=race, char_class=char_class,
            level=level, created_at=datetime.now().isoformat(),
            total_sessions=0, last_played="",
            username=(username or "").strip(),
        ),
    )
    s.save()
    return s
