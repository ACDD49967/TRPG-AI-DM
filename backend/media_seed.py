"""内置内容播种：把经典图鉴/城市写入用户媒体库（幂等，按 seeded.json 版本升级）。

从 `media_store` 拆出——那边只留存储原语（路径、元数据读写、删改标记、图片落盘），
播种策略独立成模块。`media_store` 仍以同名函数**惰性转发**，
`media_manager` / `media_bestiary` / `media_maps` / `media_spells` 的 import 面不变。

依赖方向：本模块在模块级 import `media_store` 的存储原语（`media_store` 不 import 本模块），
所以没有循环依赖；这些原语内部读 `media_store.MEDIA_ROOT`，测试 patch 该属性依然生效。
`_SEED_VERSION` 的单一事实来源仍在 `media_store`。
"""
from __future__ import annotations

from pathlib import Path

from backend.default_content import CLASSIC_BESTIARY, COMMON_CITIES
from backend.media_store import (
    _SEED_VERSION,
    _default_bestiary_details,
    _default_city_details,
    _load_deleted_builtin,
    _load_meta,
    _localize_default_name,
    _match_default_item,
    _normalize_default_bestiary,
    _save_meta,
    _user_media_dir,
)

def _seed_marker_version(user_dir: Path) -> int:
    """读取 seeded.json 的版本；旧文件内容 "1" 视为版本 1。"""
    marker = user_dir / "seeded.json"
    if not marker.exists():
        return 0
    try:
        raw = marker.read_text(encoding="utf-8").strip()
        if not raw:
            return 0
        if raw.startswith("{"):
            import json as _json
            return int(_json.loads(raw).get("version", 1) or 1)
        return int(raw or 0)
    except Exception:
        return 1



def _dedupe_builtin_items(username: str, kind: str, default_names: set[str]) -> int:
    """清理内置条目的同名重复项：每（名称, 系统, 剧本作用域）保留字段最全的一条。

    只处理名称命中内置列表且 scenario_id 为空的条目，避免误删用户自建内容。
    """
    items = _load_meta(username, kind)
    groups: dict[tuple[str, str], list[dict]] = {}
    for item in items:
        sid = str(item.get("scenario_id") or "")
        name = str(item.get("name") or "")
        if sid or name not in default_names:
            continue
        groups.setdefault((name, str(item.get("system") or "")), []).append(item)
    removed_ids: set[str] = set()
    for (_, _), group in groups.items():
        if len(group) <= 1:
            continue
        def _score(it: dict) -> tuple:
            return (
                bool(it.get("image_path")),
                len(str(it.get("description") or "")),
                len(it.get("stats") or {}),
                len(it.get("details") or {}),
                1 if it.get("tags") else 0,
            )
        group_sorted = sorted(group, key=_score, reverse=True)
        keep = group_sorted[0]
        merged_stats = dict(keep.get("stats") or {})
        merged_details = dict(keep.get("details") or {})
        merged_tags = list(keep.get("tags") or [])
        for other in group_sorted[1:]:
            removed_ids.add(str(other.get("id") or ""))
            merged_stats.update({k: v for k, v in (other.get("stats") or {}).items()
                                 if k not in merged_stats or not merged_stats.get(k)})
            merged_details.update({k: v for k, v in (other.get("details") or {}).items()
                                   if k not in merged_details or not merged_details.get(k)})
            for tag in other.get("tags") or []:
                if tag not in merged_tags:
                    merged_tags.append(tag)
        keep["stats"] = merged_stats
        keep["details"] = merged_details
        keep["tags"] = merged_tags
    if not removed_ids:
        return 0
    _save_meta(username, kind, [i for i in items if str(i.get("id") or "") not in removed_ids])
    return len(removed_ids)



def ensure_seeded(username: str):
    """写入/升级内置经典生物与城市背景：新条目补充，已有旧默认条目升级缺失字段。"""
    # 域模块反向依赖本模块（它们调用 ensure_seeded），这里惰性导入避免循环
    from backend.media_bestiary import add_bestiary, update_bestiary
    from backend.media_maps import add_map, update_map

    user_dir = _user_media_dir(username)
    user_dir.mkdir(parents=True, exist_ok=True)
    if _seed_marker_version(user_dir) >= _SEED_VERSION:
        return
    beasts = _load_meta(username, "bestiary")
    cities = _load_meta(username, "maps")
    deleted_beasts = _load_deleted_builtin(username, "bestiary")
    deleted_cities = _load_deleted_builtin(username, "maps")

    for beast in CLASSIC_BESTIARY:
        if beast["name"] in deleted_beasts:
            continue
        localized_name = _localize_default_name(beast["name"])
        name_en = (beast.get("details") or {}).get("name_en", beast["name"])
        existing = _match_default_item(beasts, localized_name, name_en, beast["system"])
        full_stats = _normalize_default_bestiary(beast)
        full_details = _default_bestiary_details(beast, localized_name)
        if existing:
            # 升级旧默认条目：只补缺失字段，不覆盖已有非空值
            old_stats = dict(existing.get("stats") or {})
            merged_stats = {**full_stats, **{k: v for k, v in old_stats.items() if v not in ("", None)}}
            old_details = dict(existing.get("details") or {})
            merged_details = {**full_details, **{k: v for k, v in old_details.items() if v not in ("", None, [])}}
            update_bestiary(username, existing["id"], {
                "name": localized_name,
                "stats": merged_stats,
                "details": merged_details,
                "tags": existing.get("tags") or beast.get("tags", []),
                "scenario_id": existing.get("scenario_id", ""),
            })
        else:
            add_bestiary(
                username=username,
                name=localized_name,
                system=beast["system"],
                description=beast["description"],
                stats=full_stats,
                image_path="",
                tags=beast.get("tags", []),
                details=full_details,
            )
    for city in COMMON_CITIES:
        if city["name"] in deleted_cities:
            continue
        localized_name = _localize_default_name(city["name"])
        name_en = (city.get("details") or {}).get("name_en", city["name"])
        existing = _match_default_item(cities, localized_name, name_en, city.get("system", "custom"))
        full_details = _default_city_details(city, localized_name)
        if existing:
            old_details = dict(existing.get("details") or {})
            merged_details = {**full_details, **{k: v for k, v in old_details.items() if v not in ("", None, [])}}
            update_map(username, existing["id"], {
                "name": localized_name,
                "description": city["description"],
                "locations": existing.get("locations") or city.get("locations", []),
                "system": city.get("system", "custom"),
                "details": merged_details,
                "scenario_id": existing.get("scenario_id", ""),
            })
        else:
            add_map(
                username=username,
                name=localized_name,
                description=city["description"],
                image_path="",
                locations=city.get("locations", []),
                system=city.get("system", "custom"),
                details=full_details,
            )
    # 一次性清理旧版本遗留的内置同名重复条目（只处理 scenario_id 为空的经典条目）
    try:
        beast_names = {_localize_default_name(b["name"]) for b in CLASSIC_BESTIARY}
        beast_names |= {b["name"] for b in CLASSIC_BESTIARY}
        city_names = {_localize_default_name(c["name"]) for c in COMMON_CITIES}
        city_names |= {c["name"] for c in COMMON_CITIES}
        _dedupe_builtin_items(username, "bestiary", beast_names)
        _dedupe_builtin_items(username, "maps", city_names)
    except Exception:
        pass
    (user_dir / "seeded.json").write_text('{"version": %d}' % _SEED_VERSION, encoding="utf-8")
