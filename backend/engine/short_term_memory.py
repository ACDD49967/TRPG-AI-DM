"""短期记忆装配图（LangGraph）。

每一轮玩家行动前，把“短期工作记忆”装配成一个确定性的流水线：

    split_turns      → 取最近 N 轮完整对话
    extract_entities → 从玩家行动 + 最近叙事中识别相关实体
    retrieve_long_term → 检索 EverOS Markdown 长期记忆库
    assemble         → 生成 essential/full 上下文与长期记忆简报

主 DM 与记忆检索子 Agent 都消费这个结果，避免每处重复拼装记忆。
"""

from __future__ import annotations

import re
from typing import Any, TypedDict

try:
    from langgraph.graph import END, START, StateGraph
except Exception:  # pragma: no cover - 未安装时回退顺序执行
    END = "__end__"
    START = "__start__"
    StateGraph = None


class MemoryGraphState(TypedDict, total=False):
    username: str
    player_input: str
    focused: bool
    summary: str
    recent_turns: list[dict]
    world_facts: list[str]
    major_events: list[dict]
    hidden_threads: list[dict]
    character_impacts: list[dict]
    entities: list[str]
    _candidate_entities: list[str]
    retrieved: list[dict]
    essential_context: str
    full_context: str
    brief: str


def _collect_entity_names(state: Any) -> list[str]:
    names: list[str] = []
    ws = getattr(state, "world_state", None)
    if ws is not None:
        names += [n.name for n in getattr(ws, "npcs", []) if getattr(n, "name", "")]
        names += [l.name for l in getattr(ws, "locations", []) if getattr(l, "name", "")]
        names += [f.key for f in getattr(ws, "plot_flags", []) if getattr(f, "key", "")]
    mem = getattr(state, "memory", None)
    if mem is not None:
        for ev in getattr(mem, "major_events", []):
            names += [str(x) for x in (ev.get("npcs") or [])]
            names += [str(x) for x in (ev.get("locations") or [])]
        for ht in getattr(mem, "hidden_threads", []):
            names.append(str(ht.get("key") or ""))
            names += [str(x) for x in (ht.get("related_npcs") or [])]
            names += [str(x) for x in (ht.get("related_locations") or [])]
        for c in getattr(mem, "character_impacts", []):
            names.append(str(c.get("name") or ""))
    return list(dict.fromkeys([n.strip() for n in names if str(n).strip()]))


def _split_turns(state: MemoryGraphState) -> MemoryGraphState:
    return {"recent_turns": state.get("recent_turns") or []}


def _extract_entities(state: MemoryGraphState) -> MemoryGraphState:
    text = str(state.get("player_input") or "")
    for t in (state.get("recent_turns") or [])[-2:]:
        text += "\n" + str(t.get("player_input") or "") + "\n" + str(t.get("dm_response") or "")[:300]
    candidates = state.get("_candidate_entities") or []  # type: ignore[attr-defined]
    found = [n for n in candidates if n and n in text]
    # 补充：最近事件/暗线标题本身命中玩家输入时也作为实体
    for ev in (state.get("major_events") or [])[-6:]:
        title = str(ev.get("title") or "")
        if title and title in text and title not in found:
            found.append(title)
    for ht in (state.get("hidden_threads") or [])[-6:]:
        key = str(ht.get("key") or "")
        if key and key in text and key not in found:
            found.append(key)
    return {"entities": found[:20]}


def _build_brief(retrieved: list[dict]) -> str:
    if not retrieved:
        return ""
    lines = ["## 长期记忆检索（EverOS Markdown 记忆库）"]
    for m in retrieved:
        mtype = str(m.get("memory_type") or "semantic")
        score = float(m.get("score") or 0.0)
        summary = str(m.get("summary") or "").strip()
        content = str(m.get("content") or "").strip()
        text = summary or content
        if len(text) > 220:
            text = text[:220] + "…"
        lines.append(f"- [{mtype} {score:.2f}] {text}")
    return "\n".join(lines)


def _build_contexts(state: MemoryGraphState) -> MemoryGraphState:
    parts: list[str] = []
    if state.get("summary"):
        parts.append(f"## 之前的故事摘要\n{state['summary']}")
    major = state.get("major_events") or []
    if major:
        parts.append("## 大事件记忆")
        for ev in major[-8:]:
            line = f"- [第{ev.get('turn', 0)}轮] {ev.get('title', '')}"
            if ev.get("description"):
                line += f"：{ev['description']}"
            if ev.get("impact"):
                line += f"（影响：{ev['impact']}）"
            parts.append(line)
    threads = [h for h in (state.get("hidden_threads") or [])
               if h.get("status") in ("未触发", "进行中")]
    if threads:
        parts.append("## 暗线进度")
        for h in threads[-6:]:
            line = f"- {h.get('key', '')} [{h.get('status', '未触发')}]"
            if h.get("description"):
                line += f"：{h['description']}"
            if h.get("progress"):
                line += f"（最近：{h['progress']}）"
            parts.append(line)
    impacts = state.get("character_impacts") or []
    if impacts:
        parts.append("## 重要人物影响")
        for c in impacts[-10:]:
            line = f"- {c.get('name', '')}"
            if c.get("impact"):
                line += f"：{c['impact']}"
            if c.get("event"):
                line += f"（事件：{c['event']}）"
            parts.append(line)
    facts = state.get("world_facts") or []
    if facts:
        parts.append("## 重要世界事实\n" + "\n".join(f"- {f}" for f in facts))
    brief = state.get("brief") or ""
    if brief:
        parts.append(brief)

    essential = "\n".join(parts)
    full_parts = list(parts)
    recent = state.get("recent_turns") or []
    if recent:
        full_parts.append("## 最近发生的事")
        for i, turn in enumerate(recent, 1):
            full_parts.append(f"第{i}轮:")
            full_parts.append(f"  玩家: {turn.get('player_input', '')}")
            full_parts.append(f"  DM: {str(turn.get('dm_response', ''))[:200]}...")
            if turn.get("events"):
                full_parts.append(f"  事件: {', '.join(turn['events'])}")
            full_parts.append("")
    return {
        "essential_context": essential,
        "full_context": "\n".join(full_parts),
    }


def _fallback_pipeline(initial: MemoryGraphState) -> MemoryGraphState:
    state = dict(initial)  # type: ignore[assignment]
    state.update(_split_turns(state))
    state.update(_extract_entities(state))
    # 顺序回退时不主动检索长期记忆，由上层 short_term_memory 补
    state.update(_build_contexts(state))
    return state  # type: ignore[return-value]


def _build_graph():
    if StateGraph is None:
        return None
    g = StateGraph(MemoryGraphState)
    g.add_node("split_turns", _split_turns)
    g.add_node("extract_entities", _extract_entities)
    g.add_node("build_contexts", _build_contexts)
    g.add_edge(START, "split_turns")
    g.add_edge("split_turns", "extract_entities")
    g.add_edge("extract_entities", "build_contexts")
    g.add_edge("build_contexts", END)
    return g.compile()


_GRAPH = _build_graph()


async def build_memory_context(state: Any, player_input: str, focused: bool = False) -> dict[str, Any]:
    """运行短期记忆图，返回 context / brief / entities / retrieved。"""
    mem = getattr(state, "memory", None)
    if mem is None:
        return {"context": "", "brief": "", "entities": [], "retrieved": []}

    recent = [
        {
            "player_input": t.player_input,
            "dm_response": t.dm_response,
            "events": list(t.events or []),
        }
        for t in mem.turns[-mem.max_active_turns:]
    ]
    initial: MemoryGraphState = {
        "username": getattr(state, "username", "default"),
        "player_input": player_input,
        "focused": focused,
        "summary": mem.summary,
        "recent_turns": recent,
        "world_facts": list(mem.world_facts),
        "major_events": list(mem.major_events),
        "hidden_threads": list(mem.hidden_threads),
        "character_impacts": list(mem.character_impacts),
    }
    # 实体候选不进入图状态字段，通过临时键传给节点
    initial["_candidate_entities"] = _collect_entity_names(state)  # type: ignore[typeddict-unknown-key]

    if _GRAPH is not None:
        result = await _GRAPH.ainvoke(initial)
    else:
        result = _fallback_pipeline(initial)

    # 长期记忆检索：用玩家行动 + 最近 DM 回复作为查询
    query = player_input
    if recent:
        query += "\n" + str(recent[-1].get("dm_response") or "")[:300]
    entities = list(result.get("entities") or [])
    retrieved: list[dict] = []
    try:
        from backend.long_term_memory import retrieve_memories
        import asyncio
        retrieved = await asyncio.to_thread(
            retrieve_memories,
            getattr(state, "username", "default"),
            query,
            entities=entities,
            top_k=5,
        )
    except Exception:
        retrieved = []

    brief = _build_brief(retrieved)
    # 把长期记忆简报并回上下文
    result = dict(result)
    result["retrieved"] = retrieved
    result["brief"] = brief
    base_essential = str(result.get("essential_context") or "")
    base_full = str(result.get("full_context") or "")
    if brief:
        result["essential_context"] = base_essential + ("\n\n" if base_essential else "") + brief
        result["full_context"] = base_full + ("\n\n" if base_full else "") + brief
    result["context"] = result["full_context"] if not focused else result["essential_context"]
    return result
