"""统一文档管线：入口。

支持：
- txt / md / markdown / docx / doc / pdf / 扫描PDF
- 页级识别
- 表格提取与跨页合并
- 页眉页脚清洗
- 注释合并
- 图片提取与上下文标注
- 递归父子切块
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from backend.document_pipeline.cleaner import clean_pages, merge_annotations
from backend.document_pipeline.image_processor import extract_and_process_images, extract_and_process_single_image
from backend.document_pipeline.office_extractor import extract_plain
from backend.document_pipeline.pdf_extractor import extract_pdf
from backend.document_pipeline.recursive_splitter import build_parent_child_chunks
from backend.document_pipeline.table_merger import merge_cross_page_tables
from backend.document_pipeline.table_semantic import semanticize_pages
from backend.document_pipeline.types import (
    DocumentPage, DocumentPipelineCancelled, DocumentResult,
)


def _detect_doc_type(filename: str, data: bytes, magic: str) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in (".pdf",):
        return "pdf"
    if ext in (".docx",):
        return "docx"
    if ext in (".doc",):
        return "doc"
    if ext in (".md", ".markdown"):
        return "markdown"
    if ext in (".txt",):
        return "text"
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
        return "image"
    if data[:4] == b"%PDF":
        return "pdf"
    if data[:2] == b"PK" and b"[Content_Types].xml" in data[:4096]:
        return "docx"
    return "text"


def run_document_pipeline(
    data: bytes,
    filename: str,
    doc_id: str = "",
    username: str = "default",
    media_root: str = "media",
    progress_callback: Callable | None = None,
    parent_max_chars: int = 4000,
    child_max_chars: int = 800,
    overlap_ratio: float = 0.15,
    ocr_first_page: int = 0,
    ocr_last_page: int = 0,
    max_ocr_pages: int = 20,
    ocr_enabled: bool = True,
    splitter: str = "recursive",
    region_fusion: bool | None = None,
    cancel_callback: Callable[[], bool] | None = None,
) -> DocumentResult:
    """执行完整文档管线。

    cancel_callback 返回 True 时，在阶段边界抛出 DocumentPipelineCancelled，
    让前端取消能够中断长文档处理。
    """
    def _check_cancel() -> None:
        if cancel_callback is not None and cancel_callback():
            raise DocumentPipelineCancelled("文档管线已取消")

    magic = (data or b"")[:8]
    doc_type = _detect_doc_type(filename, data, magic)
    pages = []
    warnings: list[str] = []
    images = []

    _check_cancel()
    if doc_type == "pdf":
        pages = extract_pdf(data, filename, progress_callback=progress_callback,
                            ocr_first_page=ocr_first_page, ocr_last_page=ocr_last_page,
                            max_ocr_pages=max_ocr_pages, ocr_enabled=ocr_enabled,
                            region_fusion=region_fusion)
        try:
            images = extract_and_process_images(data, pages, doc_id or "doc", username, media_root)
        except Exception as e:
            warnings.append(f"图片提取失败: {e}")
    elif doc_type == "image":
        img = extract_and_process_single_image(data, filename, doc_id or "doc", username, media_root)
        if img is not None:
            pages = [DocumentPage(page_no=1, text=img.context_text or img.caption or "",
                                  page_type="image")]
            images = [img]
        else:
            warnings.append(f"无法处理图片 {filename}")
    else:
        pages = extract_plain(data, filename)
        if not pages:
            warnings.append(f"无法提取 {filename} 的文本")

    _check_cancel()
    try:
        pages = clean_pages(pages)
    except Exception as e:
        warnings.append(f"清洗失败: {e}")
    _check_cancel()
    try:
        pages = merge_annotations(pages)
    except Exception as e:
        warnings.append(f"注释合并失败: {e}")
    _check_cancel()
    try:
        pages = merge_cross_page_tables(pages)
    except Exception as e:
        warnings.append(f"跨页表格合并失败: {e}")
    _check_cancel()
    try:
        semanticize_pages(pages)
    except Exception as e:
        warnings.append(f"表格语义化失败: {e}")

    _check_cancel()
    result = DocumentResult(
        source=filename or "",
        title=Path(filename or "未命名").stem,
        doc_type=doc_type,
        pages=pages,
        images=images,
        warnings=warnings,
        cleaned_text="\n\n".join(p.text for p in pages if p.text),
    )
    result.tables = [t for p in pages for t in p.tables]

    _check_cancel()
    parent_chunks, child_chunks = build_parent_child_chunks(
        result, doc_id or "doc",
        parent_max_chars=parent_max_chars,
        child_max_chars=child_max_chars,
        overlap_ratio=overlap_ratio,
    )
    result.parent_chunks = parent_chunks
    result.child_chunks = child_chunks
    result.metadata = {
        "doc_type": doc_type,
        "page_count": len(pages),
        "table_count": len(result.tables),
        "image_count": len(images),
        "parent_chunk_count": len(parent_chunks),
        "child_chunk_count": len(child_chunks),
        "overlap_ratio": overlap_ratio,
        "ocr_used_pages": sum(1 for p in pages if getattr(p, "ocr_used", False)),
        "max_ocr_pages": max_ocr_pages,
        "ocr_enabled": ocr_enabled,
        "splitter": splitter,
        "region_fusion": region_fusion,
    }
    return result
