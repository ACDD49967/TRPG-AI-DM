"""类知识图谱化：把世界状态中的角色/地点/生物/剧情组织成节点与关系，供DM上下文使用。"""
from __future__ import annotations

from typing import Any


def _norm_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.replace("、", ",").split(",") if v.strip()]
    return [str(v).strip() for v in value if str(v).strip()]


def build_knowledge_graph(ws: Any) -> dict:
    """从 WorldState 构建轻量知识图谱。"""
    nodes: dict[str, dict] = {}
    edges: set[tuple[str, str, str]] = set()

    def add_node(kind: str, name: str, extra: str = ""):
        name = str(name or "").strip()
        if not name:
            return
        nodes[name] = {"id": name, "type": kind, "label": name, "extra": extra}

    def add_edge(src: str, dst: str, rel: str):
        src = str(src or "").strip()
        dst = str(dst or "").strip()
        if src and dst and src != dst:
            edges.add((src, dst, rel))

    for n in getattr(ws, "npcs", []) or []:
        add_node("npc", n.name, f"{n.role} · {n.attitude}")
        for loc in _norm_list(getattr(n, "related_locations", [])):
            add_node("location", loc)
            add_edge(n.name, loc, "related_location")
        for other in _norm_list(getattr(n, "related_npcs", [])):
            add_node("npc", other)
            add_edge(n.name, other, "related_npc")
        for creature in _norm_list(getattr(n, "related_creatures", [])):
            add_node("creature", creature)
            add_edge(n.name, creature, "related_creature")

    for l in getattr(ws, "locations", []) or []:
        add_node("location", l.name, f"{l.type} · {l.status}")
        for loc in _norm_list(getattr(l, "related_locations", [])):
            add_node("location", loc)
            add_edge(l.name, loc, "adjacent")
        for npc in _norm_list(getattr(l, "related_npcs", [])):
            add_node("npc", npc)
            add_edge(l.name, npc, "has_npc")
        for creature in _norm_list(getattr(l, "related_creatures", [])):
            add_node("creature", creature)
            add_edge(l.name, creature, "has_creature")

    for c in getattr(ws, "creatures", []) or []:
        if isinstance(c, dict):
            name = str(c.get("name", "")).strip()
            add_node("creature", name, str(c.get("description", ""))[:40])
            for loc in _norm_list(c.get("related_locations", [])):
                add_node("location", loc)
                add_edge(name, loc, "appears_in")
            for npc in _norm_list(c.get("related_npcs", [])):
                add_node("npc", npc)
                add_edge(name, npc, "related_npc")
            for other in _norm_list(c.get("related_creatures", [])):
                add_node("creature", other)
                add_edge(name, other, "related_creature")

    for f in getattr(ws, "plot_flags", []) or []:
        add_node("plot", f.key, f.status)

    return {
        "nodes": list(nodes.values()),
        "edges": [{"source": s, "target": t, "relation": r} for s, t, r in edges],
    }


def graph_to_context(ws: Any, max_nodes: int = 20, max_edges: int = 30) -> str:
    """生成供AI使用的知识图谱文本。"""
    graph = build_knowledge_graph(ws)
    nodes = graph["nodes"][:max_nodes]
    edges = graph["edges"][:max_edges]
    lines = ["## 世界知识图谱（关系网络）"]
    if not nodes:
        return ""
    lines.append("### 节点")
    for n in nodes:
        extra = f" ({n['extra']})" if n.get("extra") else ""
        lines.append(f"- [{n['type']}] {n['label']}{extra}")
    if edges:
        lines.append("### 关系")
        for e in edges:
            lines.append(f"- {e['source']} --{e['relation']}--> {e['target']}")
    return "\n".join(lines)
