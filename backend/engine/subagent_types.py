"""子 Agent 的公共类型：执行结果、写型工具集合与结论完成判定。

单独成模块是为了让 focused_subagents（运行层）与 dm_brief（简报层）都能引用，
而不产生循环导入。
"""
from __future__ import annotations

from dataclasses import dataclass, field

# P1-15: 会修改世界/角色/图鉴状态、需要整段串行化的工具
_WRITE_TOOL_NAMES = {
    "update_state", "combat_round", "enemy_attack", "death_saving_throw", "take_rest",
    "equip_item", "update_world_state", "update_scene", "reveal_info",
    "update_bestiary_entry", "update_city_entry", "add_scenario_bestiary",
    "add_scenario_map", "add_scenario_spell", "adjust_npc", "adjust_bestiary",
    "promote_npc", "learn_spell", "forget_spell", "cast_spell",
    "update_knowledge_graph", "add_memory", "record_plot_memory", "add_character_note",
}


@dataclass
class ToolAgentResult:
    """保留完成状态与执行记录，部分失败不能伪装成已完成的简报。"""
    status: str = "incomplete"
    content: str = ""
    observations: list[str] = field(default_factory=list)
    successful_tools: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def completed(self) -> bool:
        return self.status == "completed" and bool(self.content.strip())

def is_agent_result_complete(value: str | ToolAgentResult | None) -> bool:
    if isinstance(value, ToolAgentResult):
        return value.completed
    text = str(value or "").strip()
    return bool(text) and not text.startswith(("[子Agent失败]", "[子Agent超时]", "[子Agent未返回结论]"))
