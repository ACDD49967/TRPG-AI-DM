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

from backend.document_pipeline.pdf_ocr import (  # noqa: E402,F401
    _apply_table_bboxes, _bbox_intersect, _extract_ocr_result_texts, _extract_table_page,
    _filter_text_with_tables, _page_type, _paddle_ocr_page, _pixmap_to_ndarray,
)


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
