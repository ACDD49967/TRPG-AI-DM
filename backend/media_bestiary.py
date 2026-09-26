"""生物图鉴：增删改查与剧本同步。

从 backend.media_manager 拆出；media_manager 反向再导出，既有 import 不变。
知识库/4e PDF 的批量导入在 `media_bestiary_import`，这里再导出。
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime

from backend.media_store import (
    _BESTIARY_CACHE, _CACHE_TTL, _DEFAULT_BESTIARY_NAMES, _load_meta, _mark_deleted_builtin,
    _save_meta, ensure_seeded,
)
from backend.media_maps import _match_scenario

# 批量导入器（知识库 5etools JSON / 4e PDF 文本）已拆到 media_bestiary_import
from backend.media_bestiary_import import (  # noqa: F401,E402
    _import_dnd4_pdf_monsters,
    _import_kb_monsters,
)




def sync_scenario_bestiary(username: str, scenario_id: str, creatures: list[dict], system: str = "custom"):
    """把世界状态中提取的生物同步到该剧本的生物图鉴（幂等）。"""
    if not scenario_id:
        return
    # 只认当前剧本自己的条目；通用图鉴同名条目只作为参考，不阻止建立剧本副本。
    existing = {i.get("name") for i in list_bestiary_exact(username, scenario_id)}
    global_bestiary = {i.get("name"): i for i in list_bestiary(username, None)}
    for c in creatures:
        name = str(c.get("name", "")).strip() if isinstance(c, dict) else str(c).strip()
        if not name or name in existing:
            continue
        ref = global_bestiary.get(name)
        if ref:
            add_bestiary(
                username=username,
                name=name,
                system=system,
                description=str(ref.get("description", "") or ""),
                stats=dict(ref.get("stats", {}) or {}),
                image_path=str(ref.get("image_path", "") or ""),
                tags=list(ref.get("tags", []) or []),
                details=dict(ref.get("details", {}) or {}),
                scenario_id=scenario_id,
            )
        else:
            add_bestiary(
                username=username,
                name=name,
                system=system,
                description=str(c.get("description", "")) if isinstance(c, dict) else "",
                stats=c.get("stats") if isinstance(c, dict) else {},
                image_path=str(c.get("image_path", "") or "") if isinstance(c, dict) else "",
                tags=c.get("tags") if isinstance(c, dict) else [],
                details={
                    **(c.get("details") if isinstance(c, dict) and isinstance(c.get("details"), dict) else {}),
                    "source": "剧本生成",
                },
                scenario_id=scenario_id,
            )
        existing.add(name)



def add_bestiary(username: str, name: str, system: str, description: str,
                 stats: dict | None = None, image_path: str = "", tags: list[str] | None = None,
                 details: dict | None = None, scenario_id: str = "") -> dict:
    items = _load_meta(username, "bestiary")
    item = {
        "id": uuid.uuid4().hex[:16],
        "name": name or "未命名生物",
        "system": system,
        "description": description or "",
        "stats": stats or {},
        "image_path": image_path,
        "tags": tags or [],
        "details": details or {},
        "scenario_id": scenario_id or "",
        "created_at": datetime.now().isoformat(),
    }
    items.append(item)
    _save_meta(username, "bestiary", items)
    return item



def update_bestiary(username: str, name: str, changes: dict) -> dict | None:
    """按 ID 或名称更新生物条目；仅更新传入字段，返回更新后的条目。"""
    items = _load_meta(username, "bestiary")
    for item in items:
        if item.get("id") != name and item.get("name") != name:
            continue
        for k, v in (changes or {}).items():
            if k == "stats" and isinstance(v, dict):
                item["stats"] = {**item.get("stats", {}), **v}
            else:
                item[k] = v
        _save_meta(username, "bestiary", items)
        return item
    return None






def list_bestiary(username: str, scenario_id: str | None = None) -> list[dict]:
    cache_key = (username, scenario_id or "")
    now = time.time()
    cached = _BESTIARY_CACHE.get(cache_key)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]

    ensure_seeded(username)
    _import_kb_monsters(username)
    _import_dnd4_pdf_monsters(username)
    items = _load_meta(username, "bestiary")
    # 剧本模式只读取该剧本自己的图鉴，不扫描全局知识库，避免拖慢开场
    if scenario_id is None:
        # 将知识库中标记为生物/怪物的文档合并进图鉴（保留完整内容，仅展示，不写入用户媒体）
        try:
            from backend.knowledge_base import get_knowledge_base
            kb = get_knowledge_base()
            for d in kb.documents:
                tags = [str(t) for t in d.get("tags", [])]
                source = d.get("source", "")
                title = d.get("title", "")
                if "srd:" in source or "compact" in source or "bestiary" in source or "怪物" in title:
                    continue
                if any(("生物" in t) or ("怪物" in t) or ("creature" in t.lower()) for t in tags):
                    items.append({
                        "id": f"kb-{d['id']}",
                        "name": d.get("title", "未命名生物"),
                        "system": d.get("system", "custom"),
                        "description": d.get("content", ""),
                        "stats": {},
                        "image_path": "",
                        "tags": tags,
                        "details": {"source": "知识库"},
                        "scenario_id": "",
                        "created_at": d.get("created_at", ""),
                    })
        except Exception:
            pass
    result = [i for i in items if _match_scenario(i, scenario_id)]
    _BESTIARY_CACHE[cache_key] = (now, result)
    return result



def list_bestiary_exact(username: str, scenario_id: str | None = None) -> list[dict]:
    """只返回指定作用域（当前剧本或通用）自己的图鉴条目，不合并通用参考。"""
    sid = str(scenario_id or "")
    items = list_bestiary(username, scenario_id or None)
    return [i for i in items if str(i.get("scenario_id") or "") == sid]



def find_bestiary_exact(username: str, scenario_id: str | None, name: str) -> dict | None:
    """按名称查找同作用域条目；剧本内操作不会误改通用图鉴。"""
    for item in list_bestiary_exact(username, scenario_id):
        if str(item.get("name", "")) == name and not str(item.get("id", "")).startswith("kb-"):
            return item
    return None



def find_global_bestiary(username: str, name: str) -> dict | None:
    """查找通用图鉴条目，用于给剧本图鉴复制基础数值/图片。"""
    for item in list_bestiary(username, None):
        if str(item.get("name", "")) == name and not str(item.get("id", "")).startswith("kb-"):
            return item
    return None



def delete_bestiary(username: str, beast_id: str) -> bool:
    items = _load_meta(username, "bestiary")
    removed = next((i for i in items if i["id"] == beast_id), None)
    new = [i for i in items if i["id"] != beast_id]
    if len(new) == len(items):
        return False
    if removed and str(removed.get("name", "")) in _DEFAULT_BESTIARY_NAMES:
        _mark_deleted_builtin(username, "bestiary", str(removed["name"]))
    _save_meta(username, "bestiary", new)
    return True
