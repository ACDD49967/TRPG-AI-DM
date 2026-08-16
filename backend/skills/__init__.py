"""规则系统技能包——为不同规则系统特化 LLM 行为、提示词与工具集。

目的：
- D&D 5e / D&D 4e / COC / 自定义 拥有不同游戏体验
- 避免把 D&D 5e 的巨型规则提示词发给 COC / DND4e / 自定义，降低 token 消耗
- 对 LLM 操作进行细粒度控制：历史轮数、RAG top_k、温度、最大输出、工具集
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.engine.tools import DM_TOOLS


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    system_prompt: str | None  # None 表示使用 D&D 5e 完整 SYSTEM_PROMPT
    tools: list[dict[str, Any]]
    max_tokens: int
    temperature: float
    history_rounds: int
    rag_top_k: int
    outline_limit: int
    summary_limit: int


# COC 不需要 D&D 死亡豁免工具，减少工具定义 token
_COC_TOOLS = [t for t in DM_TOOLS if t["function"]["name"] != "death_saving_throw"]

DND5E_SKILL = Skill(
    id="dnd5e",
    name="D&D 5e",
    system_prompt=None,
    tools=DM_TOOLS,
    max_tokens=4096,
    temperature=0.9,
    history_rounds=10,
    rag_top_k=5,
    outline_limit=2000,
    summary_limit=600,
)

DND4E_SKILL = Skill(
    id="dnd4e",
    name="D&D 4e",
    system_prompt="DND4E",
    tools=DM_TOOLS,
    max_tokens=4096,
    temperature=0.85,
    history_rounds=10,
    rag_top_k=5,
    outline_limit=2000,
    summary_limit=600,
)

COC_SKILL = Skill(
    id="coc",
    name="克苏鲁的呼唤 7e",
    system_prompt="COC",
    tools=_COC_TOOLS,
    max_tokens=4096,
    temperature=0.8,
    history_rounds=10,
    rag_top_k=5,
    outline_limit=2000,
    summary_limit=600,
)

CUSTOM_SKILL = Skill(
    id="custom",
    name="自定义 / 其他",
    system_prompt="CUSTOM",
    tools=DM_TOOLS,
    max_tokens=3072,
    temperature=0.8,
    history_rounds=8,
    rag_top_k=4,
    outline_limit=1500,
    summary_limit=500,
)

_SKILLS = {
    "dnd5e": DND5E_SKILL,
    "dnd4e": DND4E_SKILL,
    "coc": COC_SKILL,
    "custom": CUSTOM_SKILL,
}


def get_skill(system_id: str) -> Skill:
    return _SKILLS.get(system_id, DND5E_SKILL)
