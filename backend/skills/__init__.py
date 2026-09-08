"""AI 技能包系统。

两类技能包统一由 `SKILL.md` 标准化定义：

1. 规则系统技能包（dnd5e / dnd4e / coc / custom）
   - Frontmatter 定义引擎参数：system_prompt、tools、max_tokens、temperature 等；
   - Markdown 正文作为该规则系统的主持要点补充给主 DM。

2. 专业能力技能包（rules-advisor / combat-tactics / world-scene / ...）
   - Frontmatter 定义 name、description、role 等元数据；
   - Markdown 正文是子 Agent 的工作说明，由 `focused_subagents.py` 按需加载。

兼容旧调用：`get_skill(system_id)` 仍然返回规则系统技能包对象。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.engine.tools import DM_TOOLS
from backend.skills.loader import (
    SkillPack,
    get_skill_pack,
    list_skill_packs,
    reload_skill_packs,
)


@dataclass(frozen=True)
class SystemSkill:
    """规则系统技能包（引擎参数 + 主持要点）。"""

    id: str
    name: str
    system_prompt: str | None
    tools: list[dict[str, Any]]
    max_tokens: int
    temperature: float
    history_rounds: int
    rag_top_k: int
    outline_limit: int
    summary_limit: int
    instructions: str = ""


# 兼容旧代码：Skill 仍然可用
Skill = SystemSkill


_SYSTEM_PROMPT_ALIASES: dict[str, str | None] = {
    "default": None,
    "dnd4e": "DND4E",
    "coc": "COC",
    "custom": "CUSTOM",
}

_FALLBACK_SYSTEM_PACKS: dict[str, dict[str, Any]] = {
    "dnd5e": {
        "name": "D&D 5e",
        "system_prompt": "default",
        "tools": {"mode": "all"},
        "max_tokens": 4096,
        "temperature": 0.9,
        "history_rounds": 10,
        "rag_top_k": 5,
        "outline_limit": 2000,
        "summary_limit": 600,
    },
    "dnd4e": {
        "name": "D&D 4e",
        "system_prompt": "dnd4e",
        "tools": {"mode": "all"},
        "max_tokens": 4096,
        "temperature": 0.85,
        "history_rounds": 10,
        "rag_top_k": 5,
        "outline_limit": 2000,
        "summary_limit": 600,
    },
    "coc": {
        "name": "COC 7e",
        "system_prompt": "coc",
        "tools": {"mode": "all", "exclude": ["death_saving_throw"]},
        "max_tokens": 4096,
        "temperature": 0.8,
        "history_rounds": 10,
        "rag_top_k": 5,
        "outline_limit": 2000,
        "summary_limit": 600,
    },
    "custom": {
        "name": "自定义 / 其他",
        "system_prompt": "custom",
        "tools": {"mode": "all"},
        "max_tokens": 3072,
        "temperature": 0.8,
        "history_rounds": 8,
        "rag_top_k": 4,
        "outline_limit": 1500,
        "summary_limit": 500,
    },
}


def _coerce_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _coerce_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _resolve_prompt(raw: Any) -> str | None:
    if raw is None:
        return None
    key = str(raw).strip().lower()
    if key == "":
        return None
    if key in _SYSTEM_PROMPT_ALIASES:
        return _SYSTEM_PROMPT_ALIASES[key]
    return str(raw)


def _normalize_tool_spec(spec: Any) -> dict[str, Any]:
    if spec is None:
        return {"mode": "all"}
    if isinstance(spec, str):
        return {"mode": spec}
    if isinstance(spec, list):
        return {"mode": "include", "include": spec}
    if isinstance(spec, dict):
        return spec
    return {"mode": "all"}


def _resolve_tools(spec: Any) -> list[dict[str, Any]]:
    """按 all / include / none 三种模式解析实际下发的工具列表。"""
    normalized = _normalize_tool_spec(spec)
    mode = str(normalized.get("mode", "all")).strip().lower()
    exclude = set(normalized.get("exclude") or [])
    include = set(normalized.get("include") or [])

    def _tool_name(tool: dict[str, Any]) -> str:
        return str(tool.get("function", {}).get("name", ""))

    all_names = {_tool_name(t) for t in DM_TOOLS}
    if mode == "none":
        return []
    if mode == "include":
        missing = include - all_names
        if missing:
            print(f"[Skills] 技能包引用了不存在的工具，已忽略: {sorted(missing)}")
        return [t for t in DM_TOOLS if _tool_name(t) in include]
    missing_exclude = exclude - all_names
    if missing_exclude:
        print(f"[Skills] 技能包 exclude 了不存在的工具，已忽略: {sorted(missing_exclude)}")
    return [t for t in DM_TOOLS if _tool_name(t) not in exclude]


def _build_system_skill(pack_name: str, fallback: dict[str, Any]) -> SystemSkill:
    pack = get_skill_pack(pack_name)
    meta = dict(fallback)
    instructions = ""
    if pack is not None:
        instructions = pack.content
        for k, v in pack.metadata.items():
            # name 是技能唯一 ID，不覆盖展示名；展示名用 display_name 或回退值
            if k == "name":
                continue
            meta[k] = v
    return SystemSkill(
        id=pack_name,
        name=str(meta.get("display_name") or fallback.get("name") or pack_name),
        system_prompt=_resolve_prompt(meta.get("system_prompt", "default")),
        tools=_resolve_tools(meta.get("tools", {"mode": "all"})),
        max_tokens=_coerce_int(meta.get("max_tokens"), 4096),
        temperature=_coerce_float(meta.get("temperature"), 0.9),
        history_rounds=_coerce_int(meta.get("history_rounds"), 10),
        rag_top_k=_coerce_int(meta.get("rag_top_k"), 5),
        outline_limit=_coerce_int(meta.get("outline_limit"), 2000),
        summary_limit=_coerce_int(meta.get("summary_limit"), 600),
        instructions=instructions,
    )


def _load_system_skills() -> dict[str, SystemSkill]:
    return {
        pack_name: _build_system_skill(pack_name, fallback)
        for pack_name, fallback in _FALLBACK_SYSTEM_PACKS.items()
    }


_SKILLS = _load_system_skills()

DND5E_SKILL = _SKILLS["dnd5e"]
DND4E_SKILL = _SKILLS["dnd4e"]
COC_SKILL = _SKILLS["coc"]
CUSTOM_SKILL = _SKILLS["custom"]


def get_skill(system_id: str) -> SystemSkill:
    """返回规则系统技能包（兼容旧接口）。"""
    return _SKILLS.get(system_id, DND5E_SKILL)


def get_agent_skill(name: str) -> SkillPack | None:
    """按需加载一个 AI 专业能力技能包。"""
    return get_skill_pack(name)


def list_agent_skills() -> list[dict[str, Any]]:
    """列出所有非规则系统的专业能力技能包元数据。"""
    return [
        item for item in list_skill_packs()
        if item.get("name") not in _FALLBACK_SYSTEM_PACKS
    ]


def reload_skills() -> dict[str, SystemSkill]:
    """开发/热更新用：重新扫描 SKILL.md 并重建规则系统技能包。"""
    global _SKILLS, DND5E_SKILL, DND4E_SKILL, COC_SKILL, CUSTOM_SKILL
    reload_skill_packs()
    _SKILLS = _load_system_skills()
    DND5E_SKILL = _SKILLS["dnd5e"]
    DND4E_SKILL = _SKILLS["dnd4e"]
    COC_SKILL = _SKILLS["coc"]
    CUSTOM_SKILL = _SKILLS["custom"]
    return _SKILLS
