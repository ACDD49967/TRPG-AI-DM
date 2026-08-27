"""基于 LangGraph 的轻量专业AGENT流程编排。

用于“字段提取→严格校验→错误回传修正”的循环，提升健壮性。
"""
from __future__ import annotations

from typing import Any, Callable, TypedDict

try:
    from langgraph.graph import END, START, StateGraph
except Exception:  # pragma: no cover - langgraph 未安装时回退
    END = "__end__"
    START = "__start__"
    StateGraph = None


class AgentState(TypedDict, total=False):
    extract_fn: Callable[[], Any]
    fix_fn: Callable[[dict, list[str]], Any]
    validate_fn: Callable[[dict], list[str]]
    state_data: dict
    errors: list[str]
    attempts: int


async def _extract_node(state: AgentState) -> dict:
    return {"state_data": await state["extract_fn"]()}


async def _validate_node(state: AgentState) -> dict:
    errors = state["validate_fn"](state.get("state_data", {}))
    return {"errors": errors}


async def _fix_node(state: AgentState) -> dict:
    data = await state["fix_fn"](state.get("state_data", {}), state.get("errors", []))
    return {"state_data": data, "attempts": state.get("attempts", 0) + 1}


def _route(state: AgentState) -> str:
    if state.get("errors") and state.get("attempts", 0) < 2:
        return "fix"
    return END


def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("extract", _extract_node)
    g.add_node("validate", _validate_node)
    g.add_node("fix", _fix_node)
    g.add_edge(START, "extract")
    g.add_edge("extract", "validate")
    g.add_conditional_edges("validate", _route, {"fix": "fix", END: END})
    g.add_edge("fix", "validate")
    return g.compile()


async def run_extraction_agent(
    extract_fn: Callable[[], Any],
    validate_fn: Callable[[dict], list[str]],
    fix_fn: Callable[[dict, list[str]], Any],
    max_retries: int = 2,
) -> dict:
    """运行专业AGENT流程：提取→校验→修正→再校验，返回最终 state_data。"""
    if StateGraph is None:
        # 无 langgraph 时降级为普通循环
        data = await extract_fn()
        errors = validate_fn(data)
        attempts = 0
        while errors and attempts < max_retries:
            data = await fix_fn(data, errors)
            errors = validate_fn(data)
            attempts += 1
        return {"state_data": data, "errors": errors, "attempts": attempts}

    graph = _build_graph()
    result = await graph.ainvoke({
        "extract_fn": extract_fn,
        "fix_fn": fix_fn,
        "validate_fn": validate_fn,
        "state_data": {},
        "errors": [],
        "attempts": 0,
    })
    return result
