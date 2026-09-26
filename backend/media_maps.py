"""地图与城市：增删改查、剧本同步、知识库地点导入。

从 backend.media_manager 拆出；media_manager 反向再导出，既有 import 不变。
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict
from datetime import datetime

from backend.media_store import (
    _CACHE_TTL, _DEFAULT_CITY_NAMES, _MAPS_CACHE, _load_meta, _mark_deleted_builtin,
    _save_meta, _user_media_dir, ensure_seeded,
)




def add_map(username: str, name: str, description: str, image_path: str,
            locations: list[dict] | None = None, system: str = "custom",
            details: dict | None = None, scenario_id: str = "") -> dict:
    items = _load_meta(username, "maps")
    item = {
        "id": uuid.uuid4().hex[:16],
        "name": name or "未命名地图",
        "description": description or "",
        "image_path": image_path,
        "locations": locations or [],
        "system": system,
        "details": details or {},
        "scenario_id": scenario_id or "",
        "created_at": datetime.now().isoformat(),
    }
    items.append(item)
    _save_meta(username, "maps", items)
    return item



def update_map(username: str, name_or_id: str, changes: dict) -> dict | None:
    """按 ID 或名称更新地图；返回更新后的条目。"""
    items = _load_meta(username, "maps")
    for item in items:
        if item.get("id") != name_or_id and item.get("name") != name_or_id:
            continue
        for k, v in (changes or {}).items():
            item[k] = v
        _save_meta(username, "maps", items)
        return item
    return None



def list_maps_exact(username: str, scenario_id: str | None = None) -> list[dict]:
    """只返回指定作用域（当前剧本或通用）自己的地图，不合并通用参考。"""
    sid = str(scenario_id or "")
    items = list_maps(username, scenario_id or None)
    return [i for i in items if str(i.get("scenario_id") or "") == sid]



def find_map_exact(username: str, scenario_id: str | None, name: str) -> dict | None:
    """按名称查找同作用域地图；剧本内操作不会误改通用地图。"""
    for item in list_maps_exact(username, scenario_id):
        if str(item.get("name", "")) == name and not str(item.get("id", "")).startswith("kb-"):
            return item
    return None



def find_global_map(username: str, name: str) -> dict | None:
    """查找通用地图，用于给剧本地图复制图片/地点。"""
    for item in list_maps(username, None):
        if str(item.get("name", "")) == name and not str(item.get("id", "")).startswith("kb-"):
            return item
    return None



def _import_kb_locations(username: str):
    """从知识库自动抓取地点/城市条目并写入用户地图库（幂等，仅一次）。"""
    user_dir = _user_media_dir(username)
    user_dir.mkdir(parents=True, exist_ok=True)
    marker = user_dir / "kb_locations_imported.json"
    if marker.exists():
        return
    try:
        from backend.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        existing = {i.get("name") for i in _load_meta(username, "maps")}
        imported = 0
        for doc in kb.documents:
            tags = [str(t) for t in doc.get("tags", [])]
            is_location = any(("地点" in t) or ("城市" in t) or ("location" in t.lower()) for t in tags)
            content = str(doc.get("content", ""))
            data = None
            try:
                data = json.loads(content)
            except Exception:
                data = None
            if isinstance(data, dict) and any(k in data for k in ("locations", "cities", "city")):
                locs = data.get("locations") or data.get("cities") or []
                if data.get("city") and isinstance(data["city"], dict):
                    locs = [data["city"]] if not locs else locs
                for loc in locs if isinstance(locs, list) else []:
                    if not isinstance(loc, dict):
                        continue
                    name = str(loc.get("name") or "").strip()
                    if not name or name in existing:
                        continue
                    desc = str(loc.get("description") or loc.get("content") or "")[:500]
                    details = {"source": "知识库"}
                    if loc.get("type"): details["type"] = str(loc["type"])
                    if loc.get("status"): details["status"] = str(loc["status"])
                    if loc.get("culture"): details["culture"] = str(loc["culture"])
                    add_map(username, name, desc, "", [], doc.get("system", "custom"),
                            details=details, scenario_id="")
                    existing.add(name)
                    imported += 1
            elif is_location:
                name = str(doc.get("title", "")).strip()
                if not name or name in existing:
                    continue
                add_map(username, name, content[:500], "", [], doc.get("system", "custom"),
                        details={"source": "知识库"}, scenario_id="")
                existing.add(name)
                imported += 1
        marker.write_text(json.dumps({"imported": imported}, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[MediaManager] 知识库地点导入失败: {e}")



def _match_scenario(item: dict, scenario_id: str | None) -> bool:
    sid = str(item.get("scenario_id") or "")
    if scenario_id is None:
        # 全局/无剧本上下文：隐藏所有剧本内内容，避免跨剧本暴露
        return not sid
    # 指定剧本：显示当前剧本内容 + 全局通用参考；隐藏其它剧本内容
    return sid == scenario_id or not sid



def list_maps(username: str, scenario_id: str | None = None) -> list[dict]:
    cache_key = (username, scenario_id or "")
    now = time.time()
    cached = _MAPS_CACHE.get(cache_key)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]

    ensure_seeded(username)
    _import_kb_locations(username)
    items = _load_meta(username, "maps")
    # 剧本模式只读取该剧本自己的地图，不扫描全局知识库，避免拖慢开场
    if scenario_id is None:
        user_names = {i.get("name") for i in items}
        # 将知识库中标记为地点/城市的文档合并进地图（已导入的用户条目不再重复合并）
        try:
            from backend.knowledge_base import get_knowledge_base
            kb = get_knowledge_base()
            for d in kb.documents:
                tags = [str(t) for t in d.get("tags", [])]
                if any(("地点" in t) or ("城市" in t) or ("location" in t.lower()) for t in tags):
                    if d.get("title") in user_names:
                        continue
                    items.append({
                        "id": f"kb-{d['id']}",
                        "name": d.get("title", "未命名地点"),
                        "description": d.get("content", ""),
                        "image_path": "",
                        "locations": [],
                        "system": d.get("system", "custom"),
                        "details": {"source": "知识库"},
                        "scenario_id": "",
                        "created_at": d.get("created_at", ""),
                    })
        except Exception:
            pass
    result = [i for i in items if _match_scenario(i, scenario_id)]
    _MAPS_CACHE[cache_key] = (now, result)
    return result



def sync_scenario_maps(username: str, scenario_id: str, locations: list, system: str = "custom"):
    """把世界状态中的常驻地点同步到该剧本的地点图鉴（幂等）。

    兼容 LocationEntry 数据类与 dict 两种输入，避免把 dataclass repr 当成地点名。
    """
    if not scenario_id:
        return
    existing = {i.get("name") for i in list_maps_exact(username, scenario_id)}
    global_maps = {i.get("name"): i for i in list_maps(username, None)}
    for loc in locations:
        data = asdict(loc) if not isinstance(loc, dict) else dict(loc)
        name = str(data.get("name", "")).strip()
        if not name or name in existing:
            continue
        ref = global_maps.get(name)
        if ref:
            # 地点图鉴已有权威记录：将该记录以剧本身份复制到当前剧本
            add_map(
                username=username,
                name=name,
                description=str(ref.get("description", "") or ""),
                image_path=str(ref.get("image_path", "") or ""),
                locations=list(ref.get("locations", []) or []),
                system=system,
                details=dict(ref.get("details", {}) or {}),
                scenario_id=scenario_id,
            )
        else:
            add_map(
                username=username,
                name=name,
                description=str(data.get("description", "") or ""),
                image_path="",
                locations=[],
                system=system,
                details={
                    "type": str(data.get("type", "") or ""),
                    "status": str(data.get("status", "") or "可访问"),
                    "culture": str(data.get("culture", "") or ""),
                    "notable_figures": str(data.get("notable_figures", "") or ""),
                    "dangers": str(data.get("dangers", "") or ""),
                    "source": "剧本生成",
                },
                scenario_id=scenario_id,
            )
        existing.add(name)



def delete_map(username: str, map_id: str) -> bool:
    items = _load_meta(username, "maps")
    removed = next((i for i in items if i["id"] == map_id), None)
    new = [i for i in items if i["id"] != map_id]
    if len(new) == len(items):
        return False
    if removed and str(removed.get("name", "")) in _DEFAULT_CITY_NAMES:
        _mark_deleted_builtin(username, "maps", str(removed["name"]))
    _save_meta(username, "maps", new)
    return True
