"""PDF 页级识别与提取：PyMuPDF + pdfplumber + 可选 PaddleOCR。

策略：
1. 先用 PyMuPDF 读取文本层与图片。
2. 根据文本密度判断文本页 / 扫描页 / 混合页。
3. 文本页直接取文本；扫描页走 OCR；混合页文本 + OCR + 表格。
4. 用 pdfplumber 提取任何表格。
5. 图片元数据交给 pipeline/image_processor 进一步处理。
"""
from __future__ import annotations

import io
import math
import re
from typing import Any, Callable

import numpy as np

from backend.config import settings
from backend.document_pipeline.layout_analyzer import analyze_page_image, layout_available
from backend.document_pipeline.optional_imports import get_paddleocr, get_pdfplumber, get_pymupdf
from backend.document_pipeline.types import DocumentPage, TableBlock, TextBlock

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


def extract_pdf(data: bytes, filename: str = "", progress_callback: Callable | None = None,
                ocr_first_page: int = 0, ocr_last_page: int = 0,
                max_ocr_pages: int = 20, ocr_enabled: bool = True,
                region_fusion: bool | None = None) -> list[DocumentPage]:
    """从 PDF bytes 提取页级结果。region_fusion=None 时取全局配置。"""
    if region_fusion is None:
        region_fusion = settings.PIPELINE_REGION_FUSION
    fitz = get_pymupdf()
    pdfplumber = get_pdfplumber()
    PaddleOCR = get_paddleocr()
    if fitz is None:
        # 回退 pypdf 仅文本
        return _fallback_pypdf(data)

    pdf = fitz.open(stream=data, filetype="pdf")
    pages: list[DocumentPage] = []
    ocr_engine = None
    ocr_engine_failed = False
    ocr_kwargs = dict(
        lang="ch",
        enable_mkldnn=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )

    pdfplumber_doc = None
    if pdfplumber is not None:
        try:
            pdfplumber_doc = pdfplumber.open(io.BytesIO(data))
        except Exception:
            pdfplumber_doc = None

    ocr_attempts = 0
    for pno, page in enumerate(pdf, start=1):
        try:
            raw_text = page.get_text("text") or ""
            text = re.sub(r"[ \t]+\n", "\n", raw_text)
            imgs = page.get_images(full=True) or []
            ptype = _page_type(page, len(text.strip()), len(imgs))

            page_tables: list[TableBlock] = []
            if pdfplumber_doc is not None and pno <= len(pdfplumber_doc.pages):
                try:
                    page_tables = _extract_table_page(pdfplumber, pdfplumber_doc.pages[pno - 1])
                    if region_fusion and page_tables and ptype in ("mixed", "scanned"):
                        page_tables = _apply_table_bboxes(pdfplumber_doc.pages[pno - 1], page_tables)
                except Exception:
                    page_tables = []

            ocr_text = ""
            layout_regions: list[dict] = []
            ocr_candidate = ptype == "scanned" or (ptype == "mixed" and (ocr_first_page or ocr_last_page))
            in_range = (not ocr_first_page or pno >= ocr_first_page) and (not ocr_last_page or pno <= ocr_last_page)
            if (ocr_enabled and ocr_candidate and PaddleOCR is not None and in_range
                    and (max_ocr_pages == 0 or ocr_attempts < max_ocr_pages)):
                if ocr_engine is None and not ocr_engine_failed:
                    try:
                        ocr_engine = PaddleOCR(**ocr_kwargs)
                    except Exception:
                        try:
                            ocr_engine = PaddleOCR(use_angle_cls=False, lang="ch", show_log=False, enable_mkldnn=False)
                        except Exception:
                            ocr_engine_failed = True
                            ocr_engine = None
                if ocr_engine is not None:
                    pix = page.get_pixmap(dpi=200)
                    ocr_text = _paddle_ocr_page(PaddleOCR, ocr_engine, _pixmap_to_ndarray(pix))
                    ocr_attempts += 1
                    if ocr_text.strip():
                        ptype = "mixed" if text.strip() else "scanned"

            if layout_available() and ptype in ("mixed", "scanned"):
                try:
                    lpix = page.get_pixmap(dpi=150)
                    layout_regions = analyze_page_image(_pixmap_to_ndarray(lpix), pno)
                except Exception:
                    layout_regions = []

            if region_fusion and page_tables:
                filtered_text, kept_blocks = _filter_text_with_tables(page, text, page_tables)
            else:
                filtered_text, kept_blocks = text, []
            page_text = filtered_text.strip()
            if ocr_text and not page_text:
                page_text = ocr_text.strip()
            elif ocr_text:
                page_text = page_text + "\n\n" + ocr_text.strip()

            blocks: list[TextBlock] = []
            for line in page_text.split("\n"):
                s = line.strip()
                if not s:
                    continue
                kind = "heading" if re.match(r"^#{1,6}\s+", s) else "text"
                blocks.append(TextBlock(text=s, page_no=pno, kind=kind))

            pages.append(DocumentPage(
                page_no=pno,
                text=page_text,
                page_type=ptype,
                tables=page_tables,
                images=[],
                blocks=blocks,
                raw_text=raw_text,
                ocr_used=bool(ocr_text),
                meta={"image_count": len(imgs), "char_count": len(page_text),
                      "text_block_count": len(kept_blocks), "table_count": len(page_tables),
                      "layout_regions": layout_regions},
            ))
        except Exception as e:
            pages.append(DocumentPage(page_no=pno, text="", page_type="text",
                                      warnings=[f"page {pno} extraction failed: {e}"]))
            print(f"[PDF] page {pno} failed: {e}")
        if progress_callback:
            progress_callback(pno, len(pdf), ptype)

    if pdfplumber_doc is not None:
        try:
            pdfplumber_doc.close()
        except Exception:
            pass
    try:
        pdf.close()
    except Exception:
        pass
    return pages


def _fallback_pypdf(data: bytes) -> list[DocumentPage]:
    from backend.document_pipeline.optional_imports import get_pypdf
    pypdf = get_pypdf()
    if pypdf is None:
        return []
    try:
        import io
        reader = pypdf.PdfReader(io.BytesIO(data))
    except Exception:
        return []
    pages = []
    for i, p in enumerate(reader.pages, 1):
        try:
            t = p.extract_text() or ""
        except Exception:
            t = ""
        pages.append(DocumentPage(page_no=i, text=t.strip(), page_type="text"))
    return pages


def extract_pdf_images(fitz_doc, page_no: int) -> list[dict]:
    """返回该页图片元数据（后续交给 image_processor 提取字节）。"""
    try:
        page = fitz_doc.load_page(page_no - 1)
    except Exception:
        return []
    out = []
    for img in page.get_images(full=True) or []:
        xref = img[0]
        try:
            w = img[2] or 0
            h = img[3] or 0
        except Exception:
            w = h = 0
        out.append({"xref": xref, "width": w, "height": h})
    return out
