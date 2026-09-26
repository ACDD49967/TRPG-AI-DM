"""法术库：增删改查与剧本同步。

从 backend.media_manager 拆出；media_manager 反向再导出，既有 import 不变。
内置 SRD 播种/导入与职业映射在 `media_spells_srd`，这里再导出。
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime

from backend.media_store import (
    _CACHE_TTL, _SPELLS_CACHE, _load_meta, _save_meta, ensure_seeded,
)
from backend.media_maps import _match_scenario



# ── 法术/仪式 ──

# 内置法术数据（学派/职业中文名 + 经典法术表）的归属模块，这里只做再导出
from backend.media_spells_data import (  # noqa: F401
    CLASSIC_SPELLS,
    _CLASSIC_SPELL_NAMES,
    _CLASS_CN,
    _SCHOOL_CN,
)



# 条目格式化函数（5etools 标签清洗、时间/距离/成分/持续时间）的归属模块
from backend.media_spells_format import (  # noqa: F401
    _DND5_ENTRY_RE,
    _DND5_SPELL_RE,
    _entries_to_text,
    _fmt_components,
    _fmt_duration,
    _fmt_range,
    _fmt_time,
)

# SRD/内置法术的播种与导入（含职业映射）已拆到 media_spells_srd，这里再导出，
# media_manager 的 import 面不变。
from backend.media_spells_srd import (  # noqa: F401,E402
    _deleted_builtin_path,
    _fill_srd_spell_classes,
    _import_kb_spells,
    _load_deleted_builtin_spells,
    _mark_deleted_builtin_spell,
    _norm_spell_classes,
    _seed_classic_spells,
    _srd_spell_classes,
)




def add_spell(username: str, name: str, system: str, description: str,
              level: str = "0", school: str = "", ritual: bool = False,
              casting_time: str = "", range_: str = "", components: str = "",
              duration: str = "", classes: list[str] | None = None,
              scenario_id: str = "", tags: list[str] | None = None) -> dict:
    items = _load_meta(username, "spells")
    item = {
        "id": uuid.uuid4().hex[:16],
        "name": name or "未命名法术",
        "system": system,
        "description": description or "",
        "level": str(level),
        "school": school or "",
        "ritual": bool(ritual),
        "casting_time": casting_time or "",
        "range": range_ or "",
        "components": components or "",
        "duration": duration or "",
        "classes": _norm_spell_classes(classes),
        "scenario_id": scenario_id or "",
        "tags": tags or [],
        "created_at": datetime.now().isoformat(),
    }
    items.append(item)
    _save_meta(username, "spells", items)
    return item



def update_spell(username: str, name_or_id: str, changes: dict) -> dict | None:
    """按 ID 或名称更新法术/仪式条目。"""
    items = _load_meta(username, "spells")
    for item in items:
        if item.get("id") != name_or_id and item.get("name") != name_or_id:
            continue
        for k, v in (changes or {}).items():
            item[k] = v
        _save_meta(username, "spells", items)
        return item
    return None



def list_spells(username: str, scenario_id: str | None = None) -> list[dict]:
    cache_key = (username, scenario_id or "")
    now = time.time()
    cached = _SPELLS_CACHE.get(cache_key)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]

    ensure_seeded(username)
    _seed_classic_spells(username)
    _import_kb_spells(username)
    _fill_srd_spell_classes(username)
    items = _load_meta(username, "spells")
    # 兼容旧数据/外部写入：classes 统一为数组
    changed = False
    for item in items:
        norm = _norm_spell_classes(item.get("classes"))
        if norm != item.get("classes"):
            item["classes"] = norm
            changed = True
    if changed:
        _save_meta(username, "spells", items)
    result = [i for i in items if _match_scenario(i, scenario_id)]
    _SPELLS_CACHE[cache_key] = (now, result)
    return result



def list_spells_exact(username: str, scenario_id: str | None = None) -> list[dict]:
    """只返回指定作用域（当前剧本或通用）自己的法术，不合并通用参考。"""
    sid = str(scenario_id or "")
    items = list_spells(username, scenario_id or None)
    return [i for i in items if str(i.get("scenario_id") or "") == sid]



def find_spell_exact(username: str, scenario_id: str | None, name: str) -> dict | None:
    """按名称查找同作用域法术；剧本内操作不会误改通用法术。"""
    for item in list_spells_exact(username, scenario_id):
        if str(item.get("name", "")) == name:
            return item
    return None



def find_global_spell(username: str, name: str) -> dict | None:
    """查找通用法术，用于给剧本法术复制基础字段。"""
    for item in list_spells(username, None):
        if str(item.get("name", "")) == name:
            return item
    return None



def delete_spell(username: str, spell_id: str) -> bool:
    items = _load_meta(username, "spells")
    removed = next((i for i in items if i["id"] == spell_id), None)
    new = [i for i in items if i["id"] != spell_id]
    if len(new) == len(items):
        return False
    if removed:
        _mark_deleted_builtin_spell(username, str(removed.get("name", "")))
    _save_meta(username, "spells", new)
    return True



def sync_scenario_spells(username: str, scenario_id: str, spells: list[dict], system: str = "custom"):
    """把世界状态中提取的法术/仪式同步到该剧本的法术图鉴（幂等）。"""
    if not scenario_id:
        return
    existing = {i.get("name") for i in list_spells_exact(username, scenario_id)}
    global_spells = {i.get("name"): i for i in list_spells(username, None)}
    for s in spells:
        name = str(s.get("name", "")).strip() if isinstance(s, dict) else str(s).strip()
        if not name or name in existing:
            continue
        ref = global_spells.get(name)
        if ref:
            add_spell(
                username=username,
                name=name,
                system=system,
                description=str(ref.get("description", "") or ""),
                level=str(ref.get("level", "0") or "0"),
                school=str(ref.get("school", "") or ""),
                ritual=bool(ref.get("ritual", False)),
                casting_time=str(ref.get("casting_time", "") or ""),
                range_=str(ref.get("range", "") or ""),
                components=str(ref.get("components", "") or ""),
                duration=str(ref.get("duration", "") or ""),
                classes=list(ref.get("classes", []) or []),
                scenario_id=scenario_id,
            )
        else:
            add_spell(
                username=username,
                name=name,
                system=system,
                description=str(s.get("description", "")) if isinstance(s, dict) else "",
                level=str(s.get("level", "0")) if isinstance(s, dict) else "0",
                school=str(s.get("school", "")) if isinstance(s, dict) else "",
                ritual=bool(s.get("ritual", False)) if isinstance(s, dict) else False,
                casting_time=str(s.get("casting_time", "")) if isinstance(s, dict) else "",
                range_=str(s.get("range", "")) if isinstance(s, dict) else "",
                components=str(s.get("components", "")) if isinstance(s, dict) else "",
                duration=str(s.get("duration", "")) if isinstance(s, dict) else "",
                classes=list(s.get("classes", [])) if isinstance(s, dict) else [],
                scenario_id=scenario_id,
            )
        existing.add(name)
