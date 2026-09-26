"""知识图谱的文本化与检索：DM 摘要、TF-IDF 节点检索。

从 `backend/engine/knowledge_graph.py` 拆出；构建在 graph_build，子图查询在 graph_query。
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from backend.engine.graph_build import build_knowledge_graph


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

def graph_to_context(ws: Any, max_nodes: int = 40) -> str:
    """把世界状态压缩成 DM 可读的关系图谱摘要。"""
    try:
        graph = build_knowledge_graph(ws)
    except Exception:
        return ""
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    if not nodes:
        return ""
    degree: Counter = Counter()
    adjacency: dict[str, list[dict]] = {}
    for e in edges:
        src = str(e.get("source", ""))
        tgt = str(e.get("target", ""))
        degree[src] += 1
        degree[tgt] += 1
        adjacency.setdefault(src, []).append({"direction": "→", "other": tgt,
                                              "relation": e.get("relation", "related")})
        adjacency.setdefault(tgt, []).append({"direction": "←", "other": src,
                                              "relation": e.get("relation", "related")})
    top = sorted(nodes, key=lambda n: degree.get(str(n.get("id", "")), 0), reverse=True)[:max_nodes]
    lines = [f"## 关系图谱摘要（节点 {len(nodes)} / 关系 {len(edges)}）"]
    for n in top:
        nid = str(n.get("id", ""))
        label = str(n.get("label") or nid)
        ntype = str(n.get("type", ""))
        rels = adjacency.get(nid, [])[:5]
        rel_text = "；".join(f"{r['direction']}{r['relation']} {r['other']}" for r in rels) or "暂无显式关系"
        lines.append(f"- {label}（{ntype}，度 {degree.get(nid, 0)}）：{rel_text}")
    return "\n".join(lines)

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
