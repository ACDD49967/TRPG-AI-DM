"""DM Agent 模块化调度（LangGraph + LangChain Core）。

设计目标：
- 用一个轻量“主 Agent”路由玩家行动，分发到专用模块；
- 每个模块只准备本回合真正需要的上下文，减少 tokens；
- 输出一个 DispatchPlan，供 build_system_prompt 注入焦点上下文；
- 不改变现有 Function Calling 工具循环，保持稳定性。

这不是把每一句话都拆成多个 LLM 调用，而是把 DM Agent 的职责拆成
“路由 + 上下文装配 + 行为策略”的模块化图；LLM 主体调用保持一次。
"""
from __future__ import annotations

import re
from typing import Any, TypedDict

try:
    from langchain_core.runnables import RunnableLambda
except Exception:  # pragma: no cover - langchain_core 未安装时回退
    RunnableLambda = None

try:
    from langgraph.graph import END, START, StateGraph
except Exception:  # pragma: no cover - langgraph 未安装时回退
    END = "__end__"
    START = "__start__"
    StateGraph = None


class DMDispatchState(TypedDict, total=False):
    player_input: str
    module: str
    focus_context: str
    tool_hint: str
    omit_full_world: bool
    char_compact: str
    scene_compact: str
    memory_compact: str
    retrieved_chunks: list[dict]
    graph_context: str


# ── 主 Agent 路由 ─────────────────────────────────────────────
_PATTERNS: dict[str, list[str]] = {
    "rules": [
        r"检定", r"豁免", r"法术", r"施法", r"dc\b", r"ac\b", r"属性", r"技能",
        r"等级", r"升级", r"经验", r"金币", r"骰", r"规则", r"长休", r"短休",
        r"购买", r"卖", r"装备", r"卸下", r"治疗", r"伤害", r"资源",
    ],
    "combat": [
        r"攻击", r"战斗", r"打", r"砍", r"射", r"突袭", r"偷袭", r"逃跑",
        r"撤退", r"hp\b", r"ac\b", r"先攻", r"武器",
    ],
    "scene": [
        r"去", r"前往", r"进入", r"离开", r"回到", r"探索", r"查看", r"检查",
        r"搜索", r"张望", r"听", r"闻", r"环境", r"天气", r"时间", r"地图",
        r"位置", r"附近", r"周围",
    ],
    "social": [
        r"询问", r"问", r"聊天", r"说服", r"威吓", r"欺瞒", r"交易", r"谈",
        r"结识", r"招募", r"威胁", r"求助", r"介绍", r"寒暄",
    ],
    "memory": [
        r"之前", r"上次", r"刚才", r"记得", r"回忆", r"线索", r"为什么",
        r"暗线", r"伏笔", r"发生过", r"记录",
    ],
    "graph": [
        r"关系", r"联系", r"关联", r"知道谁", r"是谁", r"人物关系", r"线索链",
        r"图谱", r"路径", r"背景关系",
    ],
}


def _classify(player_input: str) -> str:
    text = str(player_input or "").lower()
    scores: dict[str, int] = {}
    for module, pats in _PATTERNS.items():
        s = sum(1 for p in pats if re.search(p, text))
        if s:
            scores[module] = s
    if not scores:
        return "narrative"
    # 优先级：combat/rules 场景通常比纯叙事更明确
    for m in ("combat", "rules", "graph", "scene", "social", "memory"):
        if scores.get(m):
            return m
    return "narrative"


def route_node(state: DMDispatchState) -> dict:
    """主 Agent：决定本回合分发到哪个模块。"""
    if RunnableLambda is not None:
        module = RunnableLambda(_classify).invoke(state.get("player_input", ""))
    else:
        module = _classify(state.get("player_input", ""))
    return {"module": module}


# ── 模块节点 ─────────────────────────────────────────────────
def _chunk_text(chunks: list[dict], limit: int = 3, chars: int = 350) -> str:
    parts = []
    for c in (chunks or [])[:limit]:
        title = str(c.get("title", "") or "")
        text = str(c.get("text", "") or "")[:chars]
        if title or text:
            parts.append(f"- [{title}] {text}")
    return "\n".join(parts)


def rules_node(state: DMDispatchState) -> dict:
    chunks = state.get("retrieved_chunks", []) or []
    ctx = "### 规则/判定模块\n- 本回合优先处理规则、数值、资源与判定。\n"
    c = _chunk_text(chunks, limit=3, chars=300)
    if c:
        ctx += "- 相关规则片段：\n" + c + "\n"
    ctx += "- 行为策略：先判定，再叙事；不确定时调用 search_knowledge / dice_roll。"
    return {"focus_context": ctx, "tool_hint": "dice_roll / search_knowledge / update_world_state", "omit_full_world": True}


def combat_node(state: DMDispatchState) -> dict:
    ctx = "### 战斗模块\n- 本回合优先处理攻击/防御/伤害/先攻。\n"
    if state.get("char_compact"):
        ctx += "- 角色关键数值：\n" + state["char_compact"] + "\n"
    if state.get("scene_compact"):
        ctx += "- 场景约束：\n" + state["scene_compact"][:500] + "\n"
    ctx += (
        "- 行为策略：先查卡/查状态，再 dice_roll / combat_round；避免凭空生成数值。\n"
        "- 敌方主动性：敌人攻击使用 enemy_attack 工具，在敌人自己的回合/剧情中主动发起；combat_round 只结算玩家行动，不做自动反伤。\n"
        "- 不要机械地每轮强制反击：根据行动轮、敌人状态与战术合理决定敌人是否行动。\n"
        "- 多敌拆分：不要把“两个地精”“三只狼”等当成一个实体；应拆成地精1、地精2等独立单位逐个处理。\n"
        "- 多敌展示：调用 combat_round 时用 enemy_names 传入当前战斗全部敌人名单（单个敌人可省略），enemy_name 仍是本轮玩家实际攻击目标；敌人回合逐个调用 enemy_attack。"
    )
    return {"focus_context": ctx, "tool_hint": "search_npcs / search_bestiary / dice_roll / combat_round / update_world_state", "omit_full_world": True}


def scene_node(state: DMDispatchState) -> dict:
    ctx = "### 场景模块\n- 本回合优先处理移动、探索、时间、天气与环境变化。\n"
    if state.get("scene_compact"):
        ctx += "- 当前场景：\n" + state["scene_compact"][:800] + "\n"
    ctx += "- 行为策略：位置/时间/在场 NPC 变化时必须 update_scene。"
    return {"focus_context": ctx, "tool_hint": "update_scene / update_world_state", "omit_full_world": True}


def social_node(state: DMDispatchState) -> dict:
    ctx = "### 社交模块\n- 本回合优先处理对话、说服、交易与关系变化。\n"
    if state.get("scene_compact"):
        ctx += "- 在场/场景约束：\n" + state["scene_compact"][:500] + "\n"
    ctx += "- 行为策略：重要评价/关系变化后 add_character_note；不要替玩家决定态度。"
    return {"focus_context": ctx, "tool_hint": "add_character_note / update_world_state", "omit_full_world": True}


def memory_node(state: DMDispatchState) -> dict:
    ctx = "### 记忆模块\n- 本回合优先处理回忆、线索与剧情连续性。\n"
    if state.get("memory_compact"):
        ctx += "- 相关记忆：\n" + state["memory_compact"][:900] + "\n"
    ctx += "- 行为策略：优先使用既有记忆，不要重写已确认事实。"
    return {"focus_context": ctx, "tool_hint": "search_knowledge / update_world_state", "omit_full_world": True}


def graph_node(state: DMDispatchState) -> dict:
    ctx = "### 关系图谱模块\n- 本回合优先处理实体关系、线索链与背景联系。\n"
    if state.get("graph_context"):
        ctx += "- 图谱线索：\n" + state["graph_context"][:1200] + "\n"
    ctx += "- 行为策略：需要精确关系时调用 get_entity_graph / get_graph_path。"
    return {"focus_context": ctx, "tool_hint": "get_entity_graph / get_graph_path / update_world_state", "omit_full_world": True}


def narrative_node(state: DMDispatchState) -> dict:
    return {"focus_context": "", "tool_hint": "", "omit_full_world": False}


# ── Graph 编排 ───────────────────────────────────────────────
_NODES = {
    "rules": rules_node,
    "combat": combat_node,
    "scene": scene_node,
    "social": social_node,
    "memory": memory_node,
    "graph": graph_node,
    "narrative": narrative_node,
}


def _build_dispatch_graph():
    g = StateGraph(DMDispatchState)
    g.add_node("route", route_node)

    for name in _NODES:
        g.add_node(name, _NODES[name])

    def route_after_router(state: DMDispatchState) -> str:
        return state.get("module", "narrative")

    g.add_edge(START, "route")
    g.add_conditional_edges("route", route_after_router, {name: name for name in _NODES})
    for name in _NODES:
        g.add_edge(name, END)
    return g.compile()


async def run_dm_dispatch(state: Any, player_input: str) -> dict:
    """运行主 Agent 调度图，返回 DispatchPlan dict。"""
    ws = getattr(state, "world_state", None)
    scene_compact = ws.to_context_compact() if ws else ""
    mem = getattr(state, "memory", None)
    memory_compact = mem.build_context() if mem else ""
    char_compact = ""
    try:
        from backend.engine.dm_agent import build_character_info
        char_compact = build_character_info(state)
    except Exception:
        char_compact = ""

    graph_context = ""
    try:
        from backend.engine.knowledge_graph import build_knowledge_graph, search_graph_nodes
        if ws:
            kg = build_knowledge_graph(ws)
            hits = search_graph_nodes(kg, player_input, top_k=5)
            lines = []
            for h in hits:
                n = h.get("node", {})
                lines.append(f"- {n.get('label', '')} ({n.get('type', '')}) score={h.get('score', 0)}")
            graph_context = "\n".join(lines)
    except Exception:
        graph_context = ""

    base_state: DMDispatchState = {
        "player_input": str(player_input or ""),
        "char_compact": char_compact,
        "scene_compact": scene_compact,
        "memory_compact": memory_compact,
        "graph_context": graph_context,
        "retrieved_chunks": [],
        "module": "narrative",
        "focus_context": "",
        "tool_hint": "",
        "omit_full_world": False,
    }

    if StateGraph is None:
        module = _classify(base_state["player_input"])
        plan = _NODES[module](base_state)
        plan["module"] = module
        return plan

    graph = _build_dispatch_graph()
    result = await graph.ainvoke(base_state)
    return {
        "module": result.get("module", "narrative"),
        "focus_context": result.get("focus_context", ""),
        "tool_hint": result.get("tool_hint", ""),
        "omit_full_world": bool(result.get("omit_full_world", False)),
    }
