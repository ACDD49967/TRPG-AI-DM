"""媒体库共享设施：目录/元数据读写、缓存、内置内容播种标记、图片落盘。

从 backend.media_manager 拆出；media_manager 反向再导出，既有 import 不变。
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from backend.default_content import CLASSIC_BESTIARY, COMMON_CITIES






_DEFAULT_BESTIARY_NAMES = {b["name"] for b in CLASSIC_BESTIARY}

_DEFAULT_CITY_NAMES = {c["name"] for c in COMMON_CITIES}


MEDIA_ROOT = Path("media")


_MAPS_CACHE: dict[tuple, tuple[float, list[dict]]] = {}

_BESTIARY_CACHE: dict[tuple, tuple[float, list[dict]]] = {}

_SPELLS_CACHE: dict[tuple, tuple[float, list[dict]]] = {}

_CACHE_TTL = 3.0



def _user_media_dir(username: str) -> Path:
    from backend.paths import safe_username
    return MEDIA_ROOT / safe_username(username)



def _images_dir(username: str) -> Path:
    d = _user_media_dir(username) / "images"
    d.mkdir(parents=True, exist_ok=True)
    return d



def _meta_path(username: str, kind: str) -> Path:
    return _user_media_dir(username) / f"{kind}.json"



def _load_meta(username: str, kind: str) -> list[dict]:
    p = _meta_path(username, kind)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []



def _save_meta(username: str, kind: str, items: list[dict]):
    p = _meta_path(username, kind)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    # 新增/修改/删除后立即失效对应缓存，避免列表接口继续返回旧数据。
    if kind == "bestiary":
        _BESTIARY_CACHE.clear()
    elif kind == "maps":
        _MAPS_CACHE.clear()
    elif kind == "spells":
        _SPELLS_CACHE.clear()



def _deleted_builtin_kind_path(username: str, kind: str) -> Path:
    return _user_media_dir(username) / f"deleted_builtin_{kind}.json"



def _load_deleted_builtin(username: str, kind: str) -> set[str]:
    p = _deleted_builtin_kind_path(username, kind)
    try:
        return set(json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return set()



def _mark_deleted_builtin(username: str, kind: str, name: str):
    names = _load_deleted_builtin(username, kind)
    names.add(name)
    _deleted_builtin_kind_path(username, kind).write_text(
        json.dumps(sorted(names), ensure_ascii=False), encoding="utf-8"
    )



def _localize_default_name(name: str) -> str:
    """把默认图鉴名称中的英文括号去除，只保留中文名（如 地精（Goblin）→ 地精）。"""
    import re as _re
    m = _re.match(r"^(.*?)（[^）]*）$", name.strip())
    return m.group(1).strip() if m else name.strip()



def _normalize_default_bestiary(item: dict) -> dict:
    """返回默认生物的完整 stats（已含官方/已有数据，缺失字段补为空串而非猜测）。"""
    stats = dict(item.get("stats") or {})
    for k in ("HP", "AC", "速度", "力量", "敏捷", "体质", "智力", "感知", "魅力", "技能", "特性", "动作", "挑战等级"):
        stats.setdefault(k, "")
    return stats



def _default_bestiary_details(item: dict, localized_name: str) -> dict:
    """返回默认生物的完整 details。"""
    details = dict(item.get("details") or {})
    details.setdefault("habits", "")
    details.setdefault("habitat", "")
    details.setdefault("lore", "")
    details.setdefault("weakness", "")
    details.setdefault("related_locations", [])
    details.setdefault("related_npcs", [])
    details.setdefault("related_creatures", [])
    details.setdefault("name_en", item.get("name", localized_name))
    details.setdefault("source", "内置经典内容")
    return details



def _normalize_default_city(item: dict) -> dict:
    """返回默认地点的完整 details。"""
    details = dict(item.get("details") or {})
    for k in ("type", "status", "culture", "districts", "notable_figures", "dangers", "secret",
              "related_locations", "related_npcs", "related_creatures"):
        if k == "districts":
            details.setdefault(k, [])
        elif k.startswith("related_"):
            details.setdefault(k, [])
        else:
            details.setdefault(k, "")
    return details



def _default_city_details(item: dict, localized_name: str) -> dict:
    """返回默认地点的完整 details（含 name_en/source）。"""
    details = _normalize_default_city(item)
    details.setdefault("name_en", item.get("name", localized_name))
    details.setdefault("source", "内置经典内容")
    return details



def _match_default_item(items: list[dict], default_name: str, default_name_en: str, system: str):
    """按本地化中文名 / name_en / 系统匹配已有条目。"""
    localized = _localize_default_name(default_name)
    for it in items:
        if it.get("system") != system:
            continue
        it_name = it.get("name", "")
        it_en = (it.get("details") or {}).get("name_en", "")
        if it_name == localized or it_name == default_name or _localize_default_name(it_name) == localized or it_en == default_name_en:
            return it
    return None



_SEED_VERSION = 2




_SEED_VERSION = 2

# ── 播种（实现见 media_seed）─────────────────────────────────
# `_SEED_VERSION` 留在这里作为单一事实来源；播种函数惰性转发到 media_seed，
# 这样 media_store 不必在模块级 import media_seed（避免与域模块的循环依赖）。


def _seed_marker_version(user_dir):
    from backend.media_seed import _seed_marker_version as _impl
    return _impl(user_dir)


def _dedupe_builtin_items(username: str, kind: str, default_names: set[str]) -> int:
    from backend.media_seed import _dedupe_builtin_items as _impl
    return _impl(username, kind, default_names)


def ensure_seeded(username: str):
    from backend.media_seed import ensure_seeded as _impl
    return _impl(username)



def save_image(username: str, data: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower() or ".png"
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        ext = ".png"
    img_id = uuid.uuid4().hex[:16]
    path = _images_dir(username) / f"{img_id}{ext}"
    path.write_bytes(data)
    return f"/media/{_user_media_dir(username).name}/images/{img_id}{ext}"
