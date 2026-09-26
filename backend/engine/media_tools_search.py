"""内容库检索类工具：图鉴/地点检索与图鉴数值微调。

从 `media_tools` 拆出（那边只留门面与再导出）。
"""
from __future__ import annotations

from backend.engine.session import GameSessionState, push_event

async def _exec_search_bestiary(args: dict, state: GameSessionState) -> str:
    from backend.media_manager import list_bestiary
    query = str(args.get("query", "")).strip().lower()
    top_k = max(1, min(5, int(args.get("top_k", 3) or 3)))
    scenario_id = state.character_info.get("scenario_id", "")
    scenario_id_str = str(scenario_id or "")
    items = list_bestiary(state.username or "default", scenario_id or None)
    # 同名时优先当前剧本自己的条目，避免通用参考掩盖剧本数值。
    deduped: dict[str, dict] = {}
    for it in items:
        key = str(it.get("name", ""))
        if not key:
            continue
        prev = deduped.get(key)
        if prev is None or (scenario_id_str and str(it.get("scenario_id") or "") == scenario_id_str):
            deduped[key] = it
    items = list(deduped.values())
    # 合并本局临时覆写，使 adjust_bestiary 的改动对搜索也可见
    overrides = getattr(state, "bestiary_overrides", {}) or {}
    if overrides:
        merged = []
        seen_names = set()
        for it in items:
            name = str(it.get("name", ""))
            seen_names.add(name)
            ov = overrides.get(name)
            if ov:
                stats = dict(it.get("stats") or {})
                stats.update(ov.get("stats") or {})
                it = {**it, "stats": stats}
                if ov.get("description"):
                    it["description"] = str(ov["description"])
            merged.append(it)
        for name, ov in overrides.items():
            if name not in seen_names:
                merged.append({"name": name, "description": ov.get("description", ""), "tags": ov.get("tags", []), "stats": ov.get("stats", {})})
        items = merged
    if not query:
        picked = items[:top_k]
    else:
        scored = []
        for it in items:
            hay = " ".join([
                it.get("name", ""), it.get("description_zh", "") or "", it.get("description", ""),
                " ".join(it.get("tags", [])), " ".join(str(v) for v in (it.get("stats") or {}).values()),
            ]).lower()
            scored.append((hay.count(query), it))
        scored.sort(key=lambda x: x[0], reverse=True)
        picked = [it for _, it in scored if _ > 0][:top_k]
    if not picked:
        return "图鉴中没有匹配的生物"
    return "\n".join(
        f"- [{'当前剧本' if scenario_id_str and str(it.get('scenario_id') or '') == scenario_id_str else '通用'}] "
        f"{it.get('name','')}: {str(it.get('description_zh','') or it.get('description',''))[:80]}"
        + (f" | {it.get('stats',{}).get('HP','')}" if it.get('stats',{}).get('HP') else "")
        for it in picked
    )


async def _exec_search_locations(args: dict, state: GameSessionState) -> str:
    from backend.media_manager import list_maps
    query = str(args.get("query", "")).strip().lower()
    top_k = max(1, min(5, int(args.get("top_k", 3) or 3)))
    scenario_id = state.character_info.get("scenario_id", "")
    items = list_maps(state.username or "default", scenario_id or None)
    if not query:
        picked = items[:top_k]
    else:
        scored = []
        for it in items:
            hay = " ".join([
                it.get("name", ""), it.get("description_zh", "") or "", it.get("description", ""),
                " ".join(str(l.get("name","")) for l in it.get("locations", [])),
            ]).lower()
            scored.append((hay.count(query), it))
        scored.sort(key=lambda x: x[0], reverse=True)
        picked = [it for _, it in scored if _ > 0][:top_k]
    if not picked:
        return "地点图鉴中没有匹配的地点"
    return "\n".join(
        f"- {it.get('name','')}: {str(it.get('description_zh','') or it.get('description',''))[:80]}"
        for it in picked
    )












async def _exec_adjust_bestiary(args: dict, state: GameSessionState) -> str:
    name = str(args.get("name", "")).strip()
    field = str(args.get("field", "")).strip()
    delta = int(args.get("delta", 0) or 0)
    if not name or not field:
        return "⚠ 需要 name 与 field"
    # 只从“同作用域”图鉴取现值；剧本局找不到就只写本局临时覆写，绝不改通用图鉴。
    current_stats: dict = {}
    target_id: str | None = None
    try:
        from backend.media_manager import list_bestiary, update_bestiary
        scenario_id = state.character_info.get("scenario_id", "") or ""
        for item in list_bestiary(state.username or "default", scenario_id or None):
            if str(item.get("scenario_id") or "") != scenario_id:
                continue
            if str(item.get("id", "")).startswith("kb-"):
                continue
            if item.get("name") == name or item.get("id") == name:
                current_stats = dict(item.get("stats") or {})
                target_id = item.get("id", name)
                break
    except Exception:
        target_id = None
    override = dict(state.bestiary_overrides.get(name, {}))
    if not current_stats:
        current_stats = dict(override.get("stats", {}))
    try:
        new_value = max(0, int(str(current_stats.get(field, 0)).replace("+", "") or 0) + delta)
    except (TypeError, ValueError):
        new_value = max(0, delta)
    merged_stats = {**current_stats, field: str(new_value)}
    override["stats"] = merged_stats
    state.bestiary_overrides[name] = override
    # 只有同作用域条目才落盘；通用图鉴在剧本局只通过临时覆写生效。
    if target_id:
        try:
            update_bestiary(state.username or "default", target_id, {"stats": {field: str(new_value)}})
        except Exception:
            pass
    await push_event(state, "bestiary_updated", {})
    return f"✅ 生物 {name} {field}: {new_value}"
