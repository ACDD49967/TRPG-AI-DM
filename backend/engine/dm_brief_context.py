"""给子 Agent 的上下文装配：图谱摘要、世界/记忆/最近对话预算与战斗序列。

从 `backend/engine/dm_brief.py` 拆出；候选任务与结论聚合分别在 dm_brief_tasks / dm_brief。
"""
from __future__ import annotations

from typing import Any


def _build_graph_context_text(state, player_input: str) -> str:
    """为图谱顾问准备轻量检索结果；失败返回空串，不影响主流程。

    归属说明：原先在 `dm_turn`，随"给子 Agent 什么上下文"一起搬到简报层；
    `dm_turn` / `dm_agent` 仍可按旧名字导入（再导出）。
    """
    ws = getattr(state, "world_state", None)
    if ws is None:
        return ""
    try:
        from backend.engine.knowledge_graph import build_knowledge_graph, search_graph_nodes
        kg = build_knowledge_graph(ws)
        hits = search_graph_nodes(kg, player_input, top_k=6)
        lines = []
        for h in hits:
            n = h.get("node", {}) if isinstance(h, dict) else {}
            label = str(n.get("label", "") or "")
            ntype = str(n.get("type", "") or "")
            if label:
                lines.append(f"- {label} ({ntype}) score={h.get('score', 0)}")
        return "\n".join(lines)
    except Exception:
        return ""


def assemble_brief_context(state, *, player_input: str, module: str,
                           memory_override: str = "") -> dict:
    """装配 `build_dm_brief_tasks` 需要的上下文：世界 / 记忆 / 近期对话 / 图谱。

    从 `dm_turn` 的委派阶段搬出：这是纯装配（不调模型、不改状态），
    放在简报层才好被单独测试与演进；战斗模块额外附一份敌我名册，
    免得规则顾问去猜 HP/AC。
    """
    ws = getattr(state, "world_state", None)
    memory_text = memory_override or state.memory.build_essential_context()
    recent_text = "\n".join(
        f"- 玩家: {t.player_input}\n- DM: {str(t.dm_response)[:240]}"
        for t in state.memory.turns[-4:]
    )
    world_text = ws.to_context_string() if ws is not None else ""
    world_compact = ws.to_context_compact() if ws is not None else ""
    if module == "combat" and ws is not None:
        world_compact = world_compact + "\n" + combat_roster_text(ws, player_input)
    return {
        "memory_text": memory_text,
        "recent_text": recent_text,
        "world_text": world_text,
        "world_compact": world_compact,
        "graph_text": _build_graph_context_text(state, player_input),
    }


def combat_roster_text(ws, focus_text: str = "") -> str:
    """战斗单位名册（HP/AC/位置/态度/可行动）——纯后端事实，不含模型判断。

    用途有两处：子 Agent 的上下文，以及**主 DM 自己的提示词**。
    主 DM 拿到准确数值后，就不需要再让"战斗战术顾问"子 Agent 复述一遍名册
    （那是一次纯复述的模型往返，实测每轮 1.1-2.3 秒）。
    """
    if ws is None:
        return ""
    focus = str(focus_text or "")
    lines = ["### 战斗单位数值"]
    for n in getattr(ws, "npcs", None) or []:
        if n.attitude != "敌对" and n.name not in focus:
            continue
        cond = "可行动" if n.alive else "死亡"
        lines.append(
            f"- {n.name} | 存活:{n.alive} | HP:{n.hp}/{n.max_hp} | AC:{n.ac} | "
            f"位置:{n.location} | 态度:{n.attitude} | {cond}"
        )
    return "\n".join(lines) if len(lines) > 1 else ""

# ── 专业子 Agent 任务编排 ─────────────────────────────────────


def _retrieved_text(retrieved: list) -> str:
    lines = []
    for r in (retrieved or [])[:5]:
        if not isinstance(r, dict):
            continue
        title = str(r.get("title", "") or "")
        text = str(r.get("text", "") or "")[:600]
        source = str(r.get("source", "") or "")
        if title or text:
            lines.append(f"- [{title}]({source}) {text}")
    return "\n".join(lines) or "（无检索结果）"


def _recent_text(turns: list) -> str:
    lines = []
    for t in (turns or [])[-4:]:
        pi = str(getattr(t, "player_input", "") or "")
        dm = str(getattr(t, "dm_response", "") or "")[:240]
        if pi or dm:
            lines.append(f"- 玩家: {pi}\n- DM: {dm}")
    return "\n".join(lines) or "（无近期对话）"

# 子 Agent 上下文预算（字符）。实测：每回合 7-9 次子 Agent 调用，
# 每次 prompt 3-4k token，历史压缩前的冗余全文是主要开销来源。
# world_text 与 world_compact 内容高度重叠，精简版已够裁决用。
WORLD_TEXT_BUDGET = 3200
WORLD_COMPACT_BUDGET = 1800
MEMORY_TEXT_BUDGET = 3000
RECENT_TEXT_BUDGET = 1800
GRAPH_TEXT_BUDGET = 2000
