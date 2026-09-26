"""知识图谱查询：局部子图（BFS）与两点间路径。

从 `backend/engine/knowledge_graph.py` 拆出；构建部分在 graph_build。
"""
from __future__ import annotations

from typing import Any

from backend.engine.graph_build import build_knowledge_graph


def get_local_subgraph(ws: Any, name: str, depth: int = 1) -> dict:
    """返回以某实体为中心的局部子图（BFS，按深度扩展）。"""
    name = (name or "").strip()
    if not name:
        return {"nodes": [], "edges": []}
    full = build_knowledge_graph(ws)
    adjacency: dict[str, list[int]] = {}
    for i, e in enumerate(full["edges"]):
        adjacency.setdefault(e["source"], []).append(i)
        adjacency.setdefault(e["target"], []).append(i)

    keep_nodes: set[str] = {name}
    keep_edges: set[int] = set()
    frontier = {name}
    for _ in range(max(1, min(2, int(depth or 1)))):
        next_frontier: set[str] = set()
        for node in frontier:
            for ei in adjacency.get(node, []):
                keep_edges.add(ei)
                e = full["edges"][ei]
                other = e["target"] if e["source"] == node else e["source"]
                if other not in keep_nodes:
                    next_frontier.add(other)
        keep_nodes.update(next_frontier)
        frontier = next_frontier

    nodes = [n for n in full["nodes"] if n["id"] in keep_nodes]
    edges = [full["edges"][i] for i in sorted(keep_edges)]
    return {"nodes": nodes, "edges": edges}

def get_local_subgraph_from_graph(graph: dict, name: str, depth: int = 1) -> dict:
    """从已构建（可已掩码）的图谱中提取以某实体为中心的局部子图。"""
    name = (name or "").strip()
    if not name or not graph.get("nodes"):
        return {"nodes": [], "edges": []}
    adjacency: dict[str, list[int]] = {}
    for i, e in enumerate(graph.get("edges", [])):
        adjacency.setdefault(e["source"], []).append(i)
        adjacency.setdefault(e["target"], []).append(i)

    keep_nodes: set[str] = {name}
    keep_edges: set[int] = set()
    frontier = {name}
    for _ in range(max(1, min(2, int(depth or 1)))):
        next_frontier: set[str] = set()
        for node in frontier:
            for ei in adjacency.get(node, []):
                keep_edges.add(ei)
                e = graph["edges"][ei]
                other = e["target"] if e["source"] == node else e["source"]
                if other not in keep_nodes:
                    next_frontier.add(other)
        keep_nodes.update(next_frontier)
        frontier = next_frontier

    nodes = [n for n in graph["nodes"] if n["id"] in keep_nodes]
    edges = [graph["edges"][i] for i in sorted(keep_edges)]
    return {"nodes": nodes, "edges": edges}

def get_graph_path(ws: Any, source: str, target: str, max_depth: int = 4) -> list[dict]:
    """返回 source -> target 的最短路径（边列表），找不到返回空列表。"""
    source = (source or "").strip()
    target = (target or "").strip()
    if not source or not target or source == target:
        return []
    full = build_knowledge_graph(ws)
    adjacency: dict[str, list[tuple[str, dict]]] = {}
    for e in full["edges"]:
        adjacency.setdefault(e["source"], []).append((e["target"], e))
        adjacency.setdefault(e["target"], []).append((e["source"], e))

    from collections import deque
    queue = deque([source])
    parent: dict[str, tuple[str, dict] | None] = {source: None}
    visited = {source}
    for _ in range(max(1, min(6, int(max_depth or 1)))):
        for _ in range(len(queue)):
            cur = queue.popleft()
            for nxt, edge in adjacency.get(cur, []):
                if nxt in visited:
                    continue
                visited.add(nxt)
                parent[nxt] = (cur, edge)
                if nxt == target:
                    # 重建路径
                    path: list[dict] = []
                    node = target
                    while node != source:
                        prev, edge = parent[node]
                        path.append(edge)
                        node = prev
                    path.reverse()
                    return path
                queue.append(nxt)
    return []
