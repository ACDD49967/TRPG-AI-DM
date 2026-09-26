"""知识图谱构建：把世界状态的 npcs/locations/creatures/plot_flags 织成节点与关系。

从 `backend/engine/knowledge_graph.py` 拆出；那边只做再导出，既有 import 不用改。
"""
from __future__ import annotations

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

def _resolve_player_node(ws: Any, node: dict) -> tuple[str, str]:
    """返回 (label, extra) 的玩家安全版本；未暴露信息一律用 ??? 代替。"""
    name = str(node.get("id", "")).strip()
    kind = str(node.get("type", "")).strip()

    # NPC：未发现或名字隐藏时显示 ???
    for n in getattr(ws, "npcs", []) or []:
        if n.name == name:
            if not getattr(n, "discovered", True):
                return "???", "???"
            v = n.to_player_view()
            label = v.get("name") or "???"
            role = v.get("role") or "???"
            attitude = str(getattr(n, "attitude", "") or "")
            extra = f"{role} · {attitude}" if role != "???" else "???"
            return label, extra

    # 地点：未发现时显示 ???
    for l in getattr(ws, "locations", []) or []:
        if l.name == name:
            if not getattr(l, "discovered", True):
                return "???", "未知"
            v = l.to_player_view()
            t = str(v.get("type", "") or "")
            st = str(v.get("status", "") or "")
            extra = " · ".join(x for x in (t, st) if x)
            return v.get("name") or "???", extra or ""

    # 剧情旗标：暗线/隐藏时显示 ???
    for f in getattr(ws, "plot_flags", []) or []:
        if f.key == name:
            if not getattr(f, "visible", True):
                return "???", "???"
            return f.key, str(f.status or "")

    # 生物/其他实体：暂未提供玩家可见度标记，一律按未暴露处理
    return "???", "???"

def build_player_graph(ws: Any) -> dict:
    """生成只暴露玩家已知信息的图谱；隐藏但必须显示的节点/边用 ??? 代替，且不泄露原始 id。"""
    full = build_knowledge_graph(ws)
    exposed: set[str] = set()
    id_map: dict[str, str] = {}
    nodes = []
    hidden_count = 0
    for n in full.get("nodes", []):
        original_id = str(n.get("id", ""))
        label, extra = _resolve_player_node(ws, n)
        # 隐藏实体不再逐个生成 ???N 占位节点，否则节点数量与连边拓扑可被推断。
        if label == "???":
            hidden_count += 1
            continue
        safe_id = original_id
        exposed.add(original_id)
        id_map[original_id] = safe_id
        nodes.append({**n, "id": safe_id, "label": label, "extra": extra})

    edges = []
    for e in full.get("edges", []):
        src = str(e.get("source", ""))
        tgt = str(e.get("target", ""))
        # 只保留两端都已暴露的关系；涉及隐藏实体的边整条丢弃。
        if src in exposed and tgt in exposed:
            edges.append({
                "source": id_map.get(src, src),
                "target": id_map.get(tgt, tgt),
                "relation": e.get("relation", "related"),
                **({k: v for k, v in e.items() if k not in ("source", "target", "relation") and v is not None}),
            })

    if hidden_count:
        # 只提示存在未暴露信息；不泄露数量、名称或连边。
        nodes.append({
            "id": "__hidden__",
            "type": "unknown",
            "label": "???",
            "extra": "",
        })

    return {"nodes": nodes, "edges": edges}
