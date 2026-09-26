"""SRD/内置法术的播种与导入：经典法术补齐、知识库 SRD 导入、职业映射。

从 `media_spells` 拆出（那边只留 CRUD 与剧本同步），并在 `media_spells` 再导出，
`media_manager` 的既有 import 面不变。

**循环导入**：`_seed_classic_spells` 需要写库用的 `add_spell`，它在 `media_spells`；
这里在函数内延迟 import，避免模块级互相依赖。
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.media_spells_data import (
    CLASSIC_SPELLS,
    _CLASSIC_SPELL_NAMES,
    _CLASS_CN,
    _SCHOOL_CN,
)
from backend.media_spells_format import (
    _entries_to_text,
    _fmt_components,
    _fmt_duration,
    _fmt_range,
    _fmt_time,
)
from backend.media_store import _load_meta, _save_meta, _user_media_dir
from backend.srd_spell_classes import SRD_SPELL_CLASSES

def _deleted_builtin_path(username: str) -> Path:
    return _user_media_dir(username) / "deleted_builtin_spells.json"



def _load_deleted_builtin_spells(username: str) -> set[str]:
    p = _deleted_builtin_path(username)
    try:
        return set(json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return set()



def _mark_deleted_builtin_spell(username: str, name: str):
    if name not in _CLASSIC_SPELL_NAMES:
        return
    deleted = _load_deleted_builtin_spells(username)
    deleted.add(name)
    _deleted_builtin_path(username).write_text(
        json.dumps(sorted(deleted), ensure_ascii=False), encoding="utf-8"
    )

def _seed_classic_spells(username: str):
    """把内置经典法术写入用户法术图鉴（幂等，按名称补齐；用户删除过的经典法术不再补回）。"""
    from backend.media_spells import add_spell  # 延迟导入：避免与 media_spells 循环依赖
    existing = _load_meta(username, "spells")
    names = {i.get("name") for i in existing}
    deleted = _load_deleted_builtin_spells(username)
    for sp in CLASSIC_SPELLS:
        if sp["name"] in names or sp["name"] in deleted:
            continue
        add_spell(
            username=username,
            name=sp["name"],
            system="dnd5e",
            description=sp["description"],
            level=sp["level"],
            school=sp["school"],
            ritual=sp["ritual"],
            casting_time=sp["casting_time"],
            range_=sp["range"],
            components=sp["components"],
            duration=sp["duration"],
            classes=sp["classes"],
            scenario_id="",
            tags=["经典", "DND5e", "法术"],
        )



def _import_kb_spells(username: str):
    """从知识库自动抓取 SRD 法术 JSON，并转成统一格式写入用户法术图鉴（幂等，仅一次）。"""
    user_dir = _user_media_dir(username)
    user_dir.mkdir(parents=True, exist_ok=True)
    marker = user_dir / "kb_spells_imported.json"
    if marker.exists():
        return
    try:
        from backend.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        items = _load_meta(username, "spells")
        existing = {i.get("name") for i in items}
        imported = 0
        for doc in kb.documents:
            source = str(doc.get("source", ""))
            title = str(doc.get("title", ""))
            if "spells" not in source and "法术" not in title:
                continue
            try:
                data = json.loads(doc.get("content", ""))
            except Exception:
                continue
            for s in data.get("spell", []):
                name = str(s.get("name", ""))
                if not name or name in existing:
                    continue
                existing.add(name)
                classes_raw = (s.get("classes") or {}).get("fromClassList", []) if isinstance(s.get("classes"), dict) else []
                classes = [_CLASS_CN.get(str(c), str(c)) for c in classes_raw]
                if not classes:
                    classes = _srd_spell_classes(name)
                items.append({
                    "id": uuid.uuid4().hex[:16],
                    "name": name,
                    "system": "dnd5e",
                    "description": _entries_to_text(s.get("entries", [])),
                    "level": str(s.get("level", 0)),
                    "school": _SCHOOL_CN.get(str(s.get("school", "")), "未知"),
                    "ritual": bool(s.get("meta", {}).get("ritual", False)) if isinstance(s.get("meta"), dict) else False,
                    "casting_time": _fmt_time(s.get("time", [])),
                    "range": _fmt_range(s.get("range", {})),
                    "components": _fmt_components(s.get("components", {})),
                    "duration": _fmt_duration(s.get("duration", [])),
                    "classes": classes,
                    "scenario_id": "",
                    "tags": ["SRD", "知识库", "法术"],
                    "created_at": datetime.now().isoformat(),
                })
                imported += 1
        if imported:
            _save_meta(username, "spells", items)
        marker.write_text(json.dumps({"imported": imported}, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[MediaManager] 知识库法术导入失败: {e}")




def _norm_spell_classes(value: Any) -> list[str]:
    """把 classes 规范为字符串数组（兼容逗号/顿号字符串）。"""
    if isinstance(value, str):
        return [x.strip() for x in re.split(r"[,，、]", value) if x.strip()]
    if isinstance(value, list):
        return [str(x) for x in value if x]
    return []



def _srd_spell_classes(name: str) -> list[str]:
    """按名称查 SRD 职业映射，兼容大小写差异。"""
    if name in SRD_SPELL_CLASSES:
        return list(SRD_SPELL_CLASSES[name])
    lower = name.lower()
    for k, v in SRD_SPELL_CLASSES.items():
        if k.lower() == lower:
            return list(v)
    return []

def _fill_srd_spell_classes(username: str):
    """为旧导入的 SRD 法术补齐职业映射（离线映射表）。"""
    items = _load_meta(username, "spells")
    changed = False
    for item in items:
        if "SRD" in (item.get("tags") or []) and not item.get("classes"):
            mapped = _srd_spell_classes(item.get("name"))
            if mapped:
                item["classes"] = mapped
                changed = True
    if changed:
        _save_meta(username, "spells", items)


