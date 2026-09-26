"""DM 简报层：候选任务装配、结论聚合、委派完成判定与给玩家的总结。

按职责拆三段，这里只做再导出，`dm_turn` / `focused_subagents` / `dm_agent` 的 import 面不变：
- `dm_brief_context`：上下文装配（图谱、世界/记忆/最近对话预算、战斗序列）
- `dm_brief_tasks`：候选任务装配（build_dm_brief_tasks）
- 本模块：结论聚合、完成判定与执行记录
"""
from __future__ import annotations

from backend.engine.subagent_types import (
    ToolAgentResult,
    _WRITE_TOOL_NAMES,
    is_agent_result_complete,
)

from backend.engine.dm_brief_context import (  # noqa: F401
    GRAPH_TEXT_BUDGET, MEMORY_TEXT_BUDGET, RECENT_TEXT_BUDGET, WORLD_COMPACT_BUDGET,
    WORLD_TEXT_BUDGET, _build_graph_context_text, _recent_text, _retrieved_text,
    assemble_brief_context, combat_roster_text,
)
from backend.engine.dm_brief_tasks import (  # noqa: F401
    _SKILL_FOR_TASK_KEY, _apply_skill_packs, build_dm_brief_tasks, get_skill_instruction,
)


_SECTION_TITLES = {
    "rules": "规则顾问结论",
    "combat": "战斗战术顾问结论",
    "world": "世界/场景顾问结论",
    "memory": "剧情连续性顾问结论",
    "graph": "关系图谱顾问结论",
}

def delegation_is_complete(tasks: list[dict], results: dict[str, ToolAgentResult], module: str) -> bool:
    """没有结果、任务遗漏、部分失败、仅有建议时都保留主 DM 工具。"""
    if not tasks:
        return False
    selected = [results.get(str(task.get("key", ""))) for task in tasks]
    if any(not isinstance(r, ToolAgentResult) or not r.completed for r in selected):
        return False
    # 规则/战斗需要真实结算证据，战术或场景的文字结论不能替代它。
    if module in ("combat", "rules"):
        rules = results.get("rules")
        return bool(rules and rules.completed and set(rules.successful_tools) & {
            "dice_roll", "combat_round", "cast_spell", "death_saving_throw", "take_rest",
        })
    # 仅查询/建议不等于已操控世界，主 DM 仍可能需要完成移动、资源等变化。
    return any(set(r.successful_tools) & _WRITE_TOOL_NAMES for r in selected)


def format_dm_brief(results: dict[str, str | ToolAgentResult]) -> str:
    """结论与完成状态一起传递；失败任务的已执行记录也必须保留。"""
    parts: list[str] = []
    for key, result in results.items():
        if isinstance(result, ToolAgentResult):
            value = f"任务状态：{result.status}\n{result.content}\n{result.error}".strip()
        else:
            value = str(result or "").strip()
            if not is_agent_result_complete(value):
                continue
        parts.append(f"### {_SECTION_TITLES.get(key, key)}\n{value[:900]}")
    return "\n\n".join(parts)


def delegation_execution_context(results: dict[str, ToolAgentResult]) -> str:
    """执行记录单独传递，不经过简报截断，防止接手时重复扣血或消费资源。"""
    lines = []
    for key, result in results.items():
        lines.append(f"任务 {key}: {result.status}; {result.error}")
        lines.extend(result.observations)
    return "\n".join(lines)
