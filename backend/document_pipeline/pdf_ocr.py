"""PDF OCR 与表格辅助：页面类型判断、表格提取/裁剪、PaddleOCR 结果解析。

从 `backend/document_pipeline/pdf_extractor.py` 拆出（那边只留 extract_pdf 主流程）。
"""
from __future__ import annotations

from typing import Any

import numpy as np

from backend.document_pipeline.optional_imports import get_pymupdf
from backend.document_pipeline.types import TableBlock


_OCR_MIN_TEXT = 8
_OCR_MIN_IMAGES = 1


def _page_type(page: Any, text_len: int, img_count: int) -> str:
    if text_len >= 60:
        if img_count >= 2:
            return "mixed"
        return "text"
    if img_count >= _OCR_MIN_IMAGES:
        return "scanned"
    return "text"


def _extract_table_page(pdfplumber, page) -> list[TableBlock]:
    try:
        tables = page.extract_tables()
    except Exception:
        return []
    out: list[TableBlock] = []
    for rows in tables or []:
        if not rows:
            continue
        nonempty = [r for r in rows if any(str(c or "").strip() for c in r)]
        if not nonempty:
            continue
        header = nonempty[0] if len(nonempty) > 1 else []
        data = nonempty[1:] if header and len(nonempty) > 1 else nonempty
        out.append(TableBlock(rows=[[str(c or "").strip() for c in r] for r in data],
                              headers=[str(c or "").strip() for c in header],
                              page_start=page.page_number,
                              page_end=page.page_number,
                              source="pdfplumber"))
    return out


def _apply_table_bboxes(page, page_tables: list[TableBlock]) -> list[TableBlock]:
    """对混合页用 find_tables 补充表格 bbox，仅按顺序粗略匹配。"""
    try:
        found = page.find_tables()
    except Exception:
        return page_tables
    if not found:
        return page_tables
    for i, tbl in enumerate(page_tables):
        if i < len(found):
            try:
                bbox = tuple(float(x) for x in found[i].bbox)
                tbl.bboxes[page.page_number] = bbox
            except Exception:
                pass
    return page_tables


def _pixmap_to_ndarray(pix: Any) -> np.ndarray:
    try:
        alpha = getattr(pix, "alpha", 0) or 0
        if pix.n - alpha > 3:
            # CMYK/灰度等非 RGB 像素需要先转 csRGB；fitz 走可选依赖加载
            fitz = get_pymupdf()
            if fitz is None:
                return np.array([], dtype=np.uint8)
            pix = fitz.Pixmap(fitz.csRGB, pix)
        data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n).copy()
        return data
    except Exception:
        return np.array([], dtype=np.uint8)


def _extract_ocr_result_texts(result: Any) -> str:
    """兼容 PaddleOCR 3.x predict/OCRResult 与旧版 ocr 列表结构。"""
    if result is None:
        return ""
    texts: list[str] = []

    def append_texts(values: Any):
        for v in values or []:
            s = str(v).strip()
            if s:
                texts.append(s)

    if isinstance(result, dict):
        if "rec_texts" in result:
            append_texts(result["rec_texts"])
        else:
            for line in result.get("data", []) or []:
                if not line:
                    continue
                for item in line:
                    if item and len(item) >= 2:
                        texts.append(str(item[1][0]))
        return "\n".join(texts)

    if hasattr(result, "rec_texts"):
        append_texts(result.rec_texts)
        return "\n".join(texts)

    for line in result or []:
        if line is None:
            continue
        # PaddleOCR 3.x predict 返回 [OCRResult, ...]
        if hasattr(line, "rec_texts"):
            append_texts(line.rec_texts)
            continue
        if isinstance(line, dict):
            if "rec_texts" in line:
                append_texts(line["rec_texts"])
                continue
            if "data" in line:
                for item in line["data"] or []:
                    if item and len(item) >= 2:
                        texts.append(str(item[1][0]))
                continue
        # 旧版 ocr 返回 [[[box, text, score], ...], ...]
        try:
            for item in line:
                if item and len(item) >= 2:
                    texts.append(str(item[1][0]))
        except Exception:
            continue
    return "\n".join(texts)


def _paddle_ocr_page(PaddleOCR: Any, ocr_engine: Any, image: Any) -> str:
    """对单页图像执行 OCR。PaddleOCR 3.x 优先 predict，兼容旧版 ocr。"""
    try:
        result = ocr_engine.predict(image)
        return _extract_ocr_result_texts(result)
    except Exception:
        pass
    try:
        result = ocr_engine.ocr(image)
        return _extract_ocr_result_texts(result)
    except Exception:
        return ""


def _bbox_intersect(a: tuple, b: tuple) -> bool:
    try:
        return bool(a and b and not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]))
    except Exception:
        return False


def _filter_text_with_tables(page: Any, raw_text: str, page_tables: list[TableBlock]) -> tuple[str, list[str]]:
    """区域级融合：去掉落在表格 bbox 内的 PyMuPDF 文本块，避免与 pdfplumber 表格重复。"""
    boxes = []
    for t in page_tables:
        for b in t.bboxes.values():
            if b:
                boxes.append(tuple(float(x) for x in b))
    if not boxes:
        return raw_text, []
    try:
        blocks = page.get_text("blocks") or []
    except Exception:
        return raw_text, []
    kept: list[str] = []
    for b in blocks:
        try:
            if len(b) < 5:
                continue
            x0, y0, x1, y1 = float(b[0]), float(b[1]), float(b[2]), float(b[3])
            text_b = str(b[4] or "").strip()
            if not text_b:
                continue
            in_table = any(_bbox_intersect((x0, y0, x1, y1), tb) for tb in boxes)
            if not in_table:
                kept.append(text_b)
        except Exception:
            continue
    if kept:
        return "\n".join(kept), kept
    return raw_text, []
