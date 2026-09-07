"""递归父子切块。

结构：
- ParentChunk：完整语义，表格/图片/标题完整保留。
- ChildChunk：用于检索的子块，带 15% 上下文重叠。
- 表格父块完整；子块按行组切分并继承表头作为上下文。
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from backend.document_pipeline.types import ChildChunk, DocumentResult, ParentChunk


def _cut_sentences(text: str, max_len: int, overlap: float = 0.15) -> list[str]:
    """按句子切分并生成带重叠的片段。"""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_len:
        return [text]

    sentences = re.findall(r"[^。！？!?；;\n]+[。！？!?；;\n]?", text)
    chunks: list[str] = []
    buf = ""
    for sent in sentences:
        if len(buf) + len(sent) > max_len and buf.strip():
            chunks.append(buf.strip())
            # 保留前一段尾部 overlap
            overlap_len = int(len(buf) * overlap)
            buf = buf[-overlap_len:] if overlap_len else ""
        buf += sent
    if buf.strip():
        chunks.append(buf.strip())
    return chunks


def _split_parent_to_children(parent: ParentChunk, max_chars: int = 800,
                              overlap_ratio: float = 0.15, doc_id: str = "") -> list[ChildChunk]:
    content = parent.content
    if not content:
        return []

    # 表格父块：每行作为子块，表头作为上下文，保持完整表结构
    if parent.type == "table" and parent.metadata.get("headers"):
        lines = content.split("\n")
        header_line = lines[0] if lines else ""
        out: list[ChildChunk] = []
        for i, row in enumerate(lines[1:], 1):
            if not row.strip():
                continue
            out.append(ChildChunk(
                id=uuid.uuid4().hex[:16], doc_id=doc_id, parent_id=parent.id,
                role="child", content=(header_line + "\n" + row).strip(),
                context=content, type="table", page_no=parent.page_no,
                metadata={"row_index": i, **parent.metadata},
            ))
        return out

    chunks = _cut_sentences(content, max_len=max_chars, overlap=overlap_ratio)
    out: list[ChildChunk] = []
    for i, c in enumerate(chunks):
        # context = 父块中该子块前后各 7.5% 内容，保证整体接近 15%
        context = ""
        if len(content) > max_chars:
            start = content.find(c)
            if start >= 0:
                half = int(len(c) * overlap_ratio / 2)
                context = content[max(0, start - half):min(len(content), start + len(c) + half)]
        out.append(ChildChunk(
            id=uuid.uuid4().hex[:16],
            doc_id=doc_id,
            parent_id=parent.id,
            role="child",
            content=c,
            context=context or c,
            type=parent.type,
            page_no=parent.page_no,
            metadata={"parent_index": i, **parent.metadata},
        ))
    return out


def _build_text_parents(pages: list, doc_id: str, max_chars: int = 4000) -> list[ParentChunk]:
    parents: list[ParentChunk] = []
    buf = ""
    cur_page = 1
    heading = ""

    def flush():
        nonlocal buf
        if buf.strip():
            parents.append(ParentChunk(
                id=uuid.uuid4().hex[:16], doc_id=doc_id, role="parent",
                content=buf.strip(), type="text", page_no=cur_page,
                metadata={"heading": heading},
            ))
        buf = ""

    for page in pages:
        cur_page = page.page_no
        for block in getattr(page, "blocks", []) or []:
            line = block.text.strip()
            if not line:
                continue
            if re.match(r"^#{1,6}\s+", line):
                flush()
                heading = line.lstrip("#").strip()
            buf += line + "\n"
            if len(buf) >= max_chars:
                flush()
        if len(buf) >= max_chars:
            flush()
    flush()
    return parents


def _build_table_parents(pages: list, doc_id: str) -> list[ParentChunk]:
    parents: list[ParentChunk] = []
    for page in pages:
        for tbl in getattr(page, "tables", []) or []:
            parents.append(ParentChunk(
                id=uuid.uuid4().hex[:16], doc_id=doc_id, role="parent",
                content=tbl.to_text(), type="table", page_no=tbl.page_start,
                table_id=str(id(tbl)),
                metadata={"headers": tbl.headers, "rows": len(tbl.rows),
                          "page_start": tbl.page_start, "page_end": tbl.page_end},
            ))
    return parents


def _build_image_parents(images: list, doc_id: str) -> list[ParentChunk]:
    parents = []
    for img in images or []:
        context = img.context_text or img.caption or ""
        content = f"[图片] {img.url}\n{context}".strip()
        parents.append(ParentChunk(
            id=uuid.uuid4().hex[:16], doc_id=doc_id, role="parent",
            content=content, type="image", page_no=img.page_no,
            image_id=str(id(img)),
            metadata={"url": img.url, "caption": img.caption, "auto_type": img.auto_type},
        ))
    return parents


def build_parent_child_chunks(result: DocumentResult, doc_id: str,
                              parent_max_chars: int = 4000,
                              child_max_chars: int = 800,
                              overlap_ratio: float = 0.15) -> tuple[list[ParentChunk], list[ChildChunk]]:
    """从 DocumentResult 构建父子块。"""
    parents: list[ParentChunk] = []
    parents.extend(_build_text_parents(result.pages, doc_id, max_chars=parent_max_chars))
    parents.extend(_build_table_parents(result.pages, doc_id))
    parents.extend(_build_image_parents(result.images, doc_id))

    children: list[ChildChunk] = []
    seen_parents: set[str] = set()
    for p in parents:
        if p.id in seen_parents:
            continue
        seen_parents.add(p.id)
        children.extend(_split_parent_to_children(p, max_chars=child_max_chars,
                                                  overlap_ratio=overlap_ratio, doc_id=doc_id))
    return parents, children
