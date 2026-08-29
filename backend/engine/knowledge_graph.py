"""类知识图谱：把世界状态中的角色/地点/生物/剧情组织成节点与关系。

- 节点来自 npcs/locations/creatures/plot_flags；
- 边来自结构化 related_* 字段 + 显式关系表（含亲密度/置信度）；
- 支持局部子图查询与向量化检索。
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any


def _norm_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.replace("、", ",").split(",") if v.strip()]
    return [str(v).strip() for v in value if str(v).strip()]


def _relation_index(ws: Any) -> dict[tuple[str, str, str], dict]:
    """把显式关系表转成查询索引。"""
    idx: dict[tuple[str, str, str], dict] = {}
    for rel in getattr(ws, "relations", []) or []:
        key = (str(rel.get("source", "")).strip(),
               str(rel.get("target", "")).strip(),
               str(rel.get("relation", "")).strip())
        if key[0] and key[1]:
            idx[key] = rel
    return idx


def _add_edge(edges: set, src: str, dst: str, rel: str,
              rel_index: dict[tuple[str, str, str], dict] | None = None):
    src = str(src or "").strip()
    dst = str(dst or "").strip()
    if not src or not dst or src == dst:
        return
    meta = {}
    if rel_index is not None:
        meta_rel = rel_index.get((src, dst, rel)) or rel_index.get((dst, src, rel))
        if meta_rel:
            meta = {
                "strength": meta_rel.get("strength"),
                "confidence": meta_rel.get("confidence"),
                "notes": meta_rel.get("notes", ""),
            }
    edges.add((src, dst, rel, tuple(sorted(meta.items()))))


def build_knowledge_graph(ws: Any) -> dict:
    """从 WorldState 构建完整知识图谱（含显式关系权重）。"""
    nodes: dict[str, dict] = {}
    edges: set[tuple[str, str, str, tuple]] = set()
    rel_index = _relation_index(ws)

    def add_node(kind: str, name: str, extra: str = ""):
        name = str(name or "").strip()
        if not name:
            return
        nodes[name] = {"id": name, "type": kind, "label": name, "extra": extra}

    def add_edge(src: str, dst: str, rel: str):
        _add_edge(edges, src, dst, rel, rel_index)

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

    for cr in getattr(ws, "creatures", []) or []:
        if isinstance(cr, dict):
            name = str(cr.get("name", "")).strip()
            add_node("creature", name, str(cr.get("description", ""))[:40])
            for loc in _norm_list(cr.get("related_locations", [])):
                add_node("location", loc)
                add_edge(name, loc, "appears_in")
            for npc in _norm_list(cr.get("related_npcs", [])):
                add_node("npc", npc)
                add_edge(name, npc, "related_npc")
            for other in _norm_list(cr.get("related_creatures", [])):
                add_node("creature", other)
                add_edge(name, other, "related_creature")

    for f in getattr(ws, "plot_flags", []) or []:
        add_node("plot", f.key, f.status)

    # 显式关系表中的节点也进入图（例如剧情暗线与NPC的显式关系）
    for rel in getattr(ws, "relations", []) or []:
        src = str(rel.get("source", "")).strip()
        dst = str(rel.get("target", "")).strip()
        if src and src not in nodes:
            add_node("entity", src)
        if dst and dst not in nodes:
            add_node("entity", dst)
        _add_edge(edges, src, dst, str(rel.get("relation", "related")), rel_index)

    return {
        "nodes": list(nodes.values()),
        "edges": [
            {
                "source": s,
                "target": t,
                "relation": r,
                **({k: v for k, v in meta if v is not None}),
            }
            for s, t, r, meta in edges
        ],
    }


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


def _tokenize(text: str) -> list[str]:
    text = str(text or "").lower()
    try:
        import jieba
        return [t.strip() for t in jieba.cut(text) if t.strip()]
    except Exception:
        return re.findall(r"[\u4e00-\u9fff]|[a-z0-9]+", text)


def _vectorize_nodes(nodes: list[dict], edges: list[dict] | None = None) -> dict[str, Counter]:
    """构建节点向量：节点自身文本 + 相邻边的关系/备注（支持按关系语义检索）。"""
    edge_text: dict[str, str] = {n.get("id", ""): "" for n in nodes}
    for e in edges or []:
        rel = str(e.get("relation", ""))
        notes = str(e.get("notes", ""))
        extra = f" {rel} {notes}" if (rel or notes) else ""
        if not extra.strip():
            continue
        for key in (e.get("source"), e.get("target")):
            if key in edge_text:
                edge_text[key] += extra
    vectors: dict[str, Counter] = {}
    for n in nodes:
        text = f"{n.get('label', '')} {n.get('type', '')} {n.get('extra', '')} {edge_text.get(n.get('id', ''), '')}"
        vectors[n.get("id", "")] = Counter(_tokenize(text))
    return vectors


def search_graph_nodes(graph: dict, query: str, top_k: int = 5) -> list[dict]:
    """对图谱节点做向量化检索（TF-IDF + 余弦相似度）。"""
    query = (query or "").strip()
    if not query or not graph.get("nodes"):
        return []
    nodes = graph["nodes"]
    vectors = _vectorize_nodes(nodes, graph.get("edges") or [])
    df: Counter = Counter()
    for vec in vectors.values():
        for token in vec:
            df[token] += 1
    total = max(1, len(nodes))

    def idf(token: str) -> float:
        return math.log((total + 1) / (df.get(token, 0) + 1)) + 1.0

    def to_tfidf(vec: Counter) -> dict[str, float]:
        total_tokens = sum(vec.values()) or 1
        return {t: (cnt / total_tokens) * idf(t) for t, cnt in vec.items()}

    q_vec = to_tfidf(Counter(_tokenize(query)))
    scored = []
    for node in nodes:
        n_vec = to_tfidf(vectors.get(node.get("id", ""), Counter()))
        dot = sum(w * q_vec.get(t, 0.0) for t, w in n_vec.items())
        norm_q = math.sqrt(sum(w * w for w in q_vec.values())) or 1.0
        norm_n = math.sqrt(sum(w * w for w in n_vec.values())) or 1.0
        score = dot / (norm_q * norm_n)
        if score > 0:
            scored.append({"node": node, "score": round(score, 4)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:max(1, int(top_k))]
