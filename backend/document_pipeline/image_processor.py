"""文档图片处理：从 PDF 页面抽取图片并落盘，供图鉴/地图/媒体引用。

按职责拆三段，这里只做再导出，`pipeline` / `knowledge` / `knowledge_tasks` /
`routers/scenarios_import` 的 import 面不变：
- `image_text`：上下文与实体名/数值解析、图片类别判断
- `image_register`：按内容自动登记到图鉴/地图/媒体
- 本模块：单图与整页抽取
"""
from __future__ import annotations

import hashlib
import os
import re
import uuid
from pathlib import Path
from typing import Any

from backend.document_pipeline.optional_imports import get_pymupdf
from backend.document_pipeline.types import ImageBlock

from backend.document_pipeline.image_text import (  # noqa: F401
    _BESTIARY_KEYWORDS, _IMAGE_EXT, _MAX_IMAGES_PER_PAGE, _MIN_HEIGHT, _MIN_WIDTH,
    _clean_entity_name, _context_from_page, _extract_entity_name,
    _extract_stats_from_context, _is_header_line, detect_image_type,
)
from backend.document_pipeline.image_register import (  # noqa: F401
    auto_register_bestiary_images, auto_register_map_images, auto_register_media_images,
)


def extract_and_process_single_image(
    data: bytes,
    filename: str,
    doc_id: str,
    username: str = "default",
    media_root: str = "media",
) -> ImageBlock | None:
    """处理单张图片（PNG/JPG 地图、展示材料等），生成 ImageBlock。"""
    if not data:
        return None
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(data))
        w, h = img.size
        if (w or 0) < _MIN_WIDTH or (h or 0) < _MIN_HEIGHT:
            return None
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        else:
            img = img.convert("RGB")
        raw = img.tobytes()
        digest = hashlib.md5(raw).hexdigest()
        base = Path(media_root) / "documents" / (doc_id or "tmp") / "images"
        base.mkdir(parents=True, exist_ok=True)
        fname = f"page_1_1_{digest[:8]}.png"
        path = base / fname
        img.save(path, "PNG")
        url = f"/media/documents/{doc_id}/images/{fname}"
        stem = Path(filename or "图片").stem
        context = _context_from_page(stem, limit=200)
        auto_type = detect_image_type(stem)
        return ImageBlock(
            image_path=str(path),
            url=url,
            page_no=1,
            width=w,
            height=h,
            context_text=context,
            caption=stem,
            ocr_text="",
            auto_type=auto_type,
            meta={"doc_id": doc_id, "username": username, "md5": digest, "single_image": True},
        )
    except Exception:
        return None


def extract_and_process_images(
    pdf_data: bytes,
    pages_meta: list[Any],
    doc_id: str,
    username: str = "default",
    media_root: str = "media",
) -> list[ImageBlock]:
    """从 PDF 提取图片，写入 media/documents/{doc_id}/images，并返回 ImageBlock。"""
    fitz = get_pymupdf()
    if fitz is None:
        return []
    blocks: list[ImageBlock] = []
    seen: set[str] = set()
    try:
        doc = fitz.open(stream=pdf_data, filetype="pdf")
    except Exception:
        return []
    base = Path(media_root) / "documents" / (doc_id or "tmp") / "images"
    base.mkdir(parents=True, exist_ok=True)

    page_texts = {p.page_no: p.text or "" for p in pages_meta if hasattr(p, "page_no")}

    for pno, page in enumerate(doc, start=1):
        if pno > len(pages_meta):
            break
        imgs = page.get_images(full=True) or []
        count = 0
        for img in imgs[: _MAX_IMAGES_PER_PAGE * 2]:
            if count >= _MAX_IMAGES_PER_PAGE:
                break
            try:
                xref = img[0]
                ext = _IMAGE_EXT.get(int(img[1] or 0), "png")
                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha > 3:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                raw = pix.tobytes(ext if ext != "jpeg" else "png")
                w, h = pix.width, pix.height
                pix = None
            except Exception:
                continue
            if w < _MIN_WIDTH or h < _MIN_HEIGHT:
                continue
            digest = hashlib.md5(raw).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)

            fname = f"page_{pno}_{count + 1}_{digest[:8]}.png"
            path = base / fname
            path.write_bytes(raw)
            url = f"/media/documents/{doc_id}/images/{fname}"

            context = _context_from_page(page_texts.get(pno, ""))
            caption = ""
            m = re.search(r"(?:图|figure|FIG)[^。\n]{0,80}", context, re.I)
            if m:
                caption = m.group(0).strip()

            auto_type = detect_image_type(context)
            blocks.append(ImageBlock(
                image_path=str(path),
                url=url,
                page_no=pno,
                width=w,
                height=h,
                context_text=context,
                caption=caption,
                ocr_text="",
                auto_type=auto_type,
                meta={"doc_id": doc_id, "username": username, "md5": digest},
            ))
            count += 1
        # 超页保护
        if len(blocks) > 500:
            break
    try:
        doc.close()
    except Exception:
        pass
    return blocks
