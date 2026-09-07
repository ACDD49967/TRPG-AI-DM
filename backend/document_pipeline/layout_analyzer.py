# -*- coding: utf-8 -*-
"""可选 PaddleLayout / PP-StructureV3 版面分析器。

当前实现为可选链路：
- 优先使用 `paddlex.create_pipeline("PP-StructureV3")`；
- 若未安装 `paddlex[ocr]` 额外依赖或模型不可用，返回空结果，不影响主流程；
- 后续可替换为 LayoutLM，保持 region 输出结构不变。
"""
from __future__ import annotations

from typing import Any

from backend.config import settings

_LAYOUT_PIPELINE = None
_LAYOUT_TRIED = False

# 区域类型 -> 统一标签
_REGION_LABELS = {
    "text": "text",
    "title": "title",
    "header": "header",
    "footer": "footer",
    "page_number": "page_number",
    "sidebar": "sidebar",
    "caption": "caption",
    "table": "table",
    "image": "image",
    "formula": "formula",
}


def get_layout_pipeline():
    global _LAYOUT_PIPELINE, _LAYOUT_TRIED
    if _LAYOUT_TRIED:
        return _LAYOUT_PIPELINE
    _LAYOUT_TRIED = True
    if not settings.PIPELINE_LAYOUT_ENABLED:
        return None
    try:
        import paddlex
        try:
            _LAYOUT_PIPELINE = paddlex.create_pipeline("PP-StructureV3")
        except Exception:
            _LAYOUT_PIPELINE = None
    except Exception:
        _LAYOUT_PIPELINE = None
    return _LAYOUT_PIPELINE


def _normalize_label(label: Any) -> str:
    s = str(label or "").strip().lower()
    if s in _REGION_LABELS:
        return _REGION_LABELS[s]
    if "header" in s:
        return "header"
    if "footer" in s or "page" in s:
        return "footer"
    if "table" in s:
        return "table"
    if "image" in s or "figure" in s or "picture" in s:
        return "image"
    if "text" in s:
        return "text"
    return "other"


def _region_from_item(item: Any, page_no: int = 1) -> dict | None:
    """尝试从 PP-Structure 结果中提取统一 region dict。"""
    try:
        if isinstance(item, dict):
            boxes = item.get("layout_boxes") or item.get("boxes") or []
        elif hasattr(item, "layout_boxes"):
            boxes = item.layout_boxes or []
        elif hasattr(item, "boxes"):
            boxes = item.boxes or []
        else:
            boxes = []
        if not boxes:
            return None
        for box in boxes:
            if isinstance(box, dict):
                label = _normalize_label(box.get("label") or box.get("type") or "")
                bbox = box.get("bbox") or box.get("box")
            elif isinstance(box, (list, tuple)) and len(box) >= 5:
                label = _normalize_label(box[4] if len(box) > 4 else "")
                bbox = box[:4]
            else:
                continue
            if bbox:
                return {
                    "page_no": page_no,
                    "label": label,
                    "bbox": [float(x) for x in bbox],
                    "text": (box.get("text") if isinstance(box, dict) else "") or "",
                    "engine": "paddlelayout",
                }
    except Exception:
        return None
    return None


def analyze_page_image(image: Any, page_no: int = 1) -> list[dict]:
    """对单页图像做版面分析；失败返回空列表。"""
    pipeline = get_layout_pipeline()
    if pipeline is None or image is None:
        return []
    try:
        result = pipeline.predict(image)
    except Exception:
        return []
    regions: list[dict] = []
    try:
        items = result if isinstance(result, list) else [result]
        for item in items:
            r = _region_from_item(item, page_no=page_no)
            if r:
                regions.append(r)
    except Exception:
        pass
    return regions


def layout_available() -> bool:
    return get_layout_pipeline() is not None
