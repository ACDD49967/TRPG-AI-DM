"""图片自动登记：把抽取到的图片按上下文挂到图鉴条目、地图与媒体库。

从 `backend/document_pipeline/image_processor.py` 拆出。
"""
from __future__ import annotations

from backend.document_pipeline.image_text import (
    _extract_entity_name, _extract_stats_from_context,
)
from backend.document_pipeline.types import ImageBlock


def auto_register_bestiary_images(
    username: str,
    scenario_id: str,
    images: list[ImageBlock],
    system: str = "dnd4e",
) -> int:
    """将识别为生物图谱的图片自动写入图鉴，返回新增数量。

    修复：
    - 名称只取实体名，不再把整段上下文塞进名称；
    - 尽可能从页面上下文提取 HP/AC/等级/六维等属性。
    """
    try:
        from backend.media_manager import add_bestiary, _load_meta
    except Exception:
        return 0
    count = 0
    try:
        existing = _load_meta(username, "bestiary")
    except Exception:
        existing = []
    # 幂等：只和同作用域（当前剧本或通用）比较，避免通用图鉴同名图片阻止剧本副本。
    sid = str(scenario_id or "")
    scoped_existing = [i for i in existing if str(i.get("scenario_id") or "") == sid]
    existing_paths = {str(i.get("image_path") or "") for i in scoped_existing}
    existing_auto_pages = {
        ((i.get("details") or {}).get("source_page", ""), str(i.get("image_path") or ""))
        for i in scoped_existing if (i.get("details") or {}).get("auto")
    }
    for img in images or []:
        if img.auto_type != "bestiary":
            continue
        name = _extract_entity_name(img.context_text, img.caption, img.page_no, "bestiary")
        # 幂等：同一图片 URL 或同一页同图不重复写入
        if img.url in existing_paths or (img.page_no, img.url) in existing_auto_pages:
            continue
        stats = _extract_stats_from_context(img.context_text)
        add_bestiary(
            username=username,
            name=name,
            system=system,
            description=(img.context_text or "")[:300],
            stats=stats,
            image_path=img.url,
            tags=["自动识别", "怪物库", "图谱"],
            details={"source_page": img.page_no, "auto": True,
                     "source_text": (img.context_text or "")[:500]},
            scenario_id=scenario_id,
        )
        existing_paths.add(img.url)
        existing_auto_pages.add((img.page_no, img.url))
        count += 1
    return count


def auto_register_map_images(
    username: str,
    scenario_id: str,
    images: list[ImageBlock],
) -> int:
    """将识别为地图的图片自动写入地图图鉴，返回新增数量。"""
    try:
        from backend.media_manager import add_map, _load_meta
    except Exception:
        return 0
    count = 0
    try:
        existing = _load_meta(username, "maps")
    except Exception:
        existing = []
    # 幂等：只和同作用域（当前剧本或通用）比较。
    sid = str(scenario_id or "")
    existing_paths = {
        str(i.get("image_path") or "")
        for i in existing if str(i.get("scenario_id") or "") == sid
    }
    for img in images or []:
        if img.auto_type != "map":
            continue
        if img.url in existing_paths:
            continue
        name = _extract_entity_name(img.context_text, img.caption, img.page_no, "map")
        add_map(
            username=username,
            name=name,
            description=(img.context_text or "")[:300],
            image_path=img.url,
            locations=[],
            system="custom",
            details={"source_page": img.page_no, "auto": True,
                     "source_text": (img.context_text or "")[:500]},
            scenario_id=scenario_id,
        )
        existing_paths.add(img.url)
        count += 1
    return count


def auto_register_media_images(
    username: str,
    scenario_id: str,
    images: list[ImageBlock],
    system: str = "dnd4e",
) -> dict[str, int]:
    """统一注册生物/地图图片到图鉴，返回 {bestiary, map} 新增数。"""
    return {
        "bestiary": auto_register_bestiary_images(username, scenario_id, images, system=system),
        "map": auto_register_map_images(username, scenario_id, images),
    }
