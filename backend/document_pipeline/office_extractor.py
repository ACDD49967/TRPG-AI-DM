"""TXT / Markdown / DOCX / DOC 提取与页化。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from backend.document_pipeline.optional_imports import has_module, try_import
from backend.document_pipeline.types import DocumentPage, TableBlock, TextBlock


def normalize_text(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_txt(data: bytes, filename: str) -> list[DocumentPage]:
    text = ""
    for enc in ("utf-8", "gb18030", "gbk", "big5"):
        try:
            text = data.decode(enc)
            break
        except Exception:
            continue
    text = normalize_text(text)
    return [_text_page(text, 1)]


def extract_markdown(data: bytes, filename: str) -> list[DocumentPage]:
    text = ""
    for enc in ("utf-8", "gb18030", "gbk"):
        try:
            text = data.decode(enc)
            break
        except Exception:
            continue
    text = normalize_text(text)
    # 按二级/一级标题切分成页，便于后续父子切块保标题层级
    headings = list(re.finditer(r"(?m)^#{1,3}\s+.*$", text))
    if not headings:
        return [_text_page(text, 1)]
    pages: list[DocumentPage] = []
    for idx, m in enumerate(headings):
        start = m.start()
        end = headings[idx + 1].start() if idx + 1 < len(headings) else len(text)
        seg = text[start:end].strip()
        if seg:
            blocks = _plain_blocks(seg)
            pages.append(DocumentPage(page_no=idx + 1, text=seg, page_type="text", blocks=blocks))
    return pages


def _plain_blocks(text: str) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            blocks.append(TextBlock(text=s, kind="heading"))
        else:
            blocks.append(TextBlock(text=s, kind="paragraph"))
    return blocks


def _text_page(text: str, page_no: int) -> DocumentPage:
    return DocumentPage(page_no=page_no, text=text, page_type="text", blocks=_plain_blocks(text))


def extract_docx(data: bytes, filename: str) -> list[DocumentPage]:
    doc = None
    try:
        from docx import Document
        import io
        doc = Document(io.BytesIO(data))
    except Exception:
        return []
    paragraphs: list[TextBlock] = []
    for p in doc.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        paragraphs.append(TextBlock(text=t, kind="text"))
    # DOCX 表格
    tables = []
    table_texts: list[str] = []
    for tbl in doc.tables:
        rows = [[cell.text.strip() for cell in row.cells] for row in tbl.rows]
        if rows:
            headers = rows[0] if len(rows) > 1 else []
            data = rows[1:] if headers and len(rows) > 1 else rows
            tables.append(TableBlock(rows=data, headers=headers, page_start=1, page_end=1, source="python-docx"))
            table_texts.append("\n".join(" | ".join(r) for r in rows))
    text = "\n\n".join([p.text for p in paragraphs] + table_texts)
    page = _text_page(text, 1)
    page.tables = tables
    return [page]


def _extract_doc_win32(data: bytes) -> str:
    """Windows 下通过 Word COM 提取 .doc 文本（pywin32 可选）。"""
    import os
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as f:
        f.write(data)
        tmp = f.name
    word = None
    try:
        import win32com.client  # type: ignore
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        word.DisplayAlerts = False
        doc = word.Documents.Open(tmp, ReadOnly=True)
        try:
            text = str(doc.Content.Text or "")
        finally:
            doc.Close(False)
        return text
    except Exception:
        return ""
    finally:
        try:
            if word is not None:
                word.Quit()
        except Exception:
            pass
        try:
            os.unlink(tmp)
        except Exception:
            pass


def extract_doc(data: bytes, filename: str) -> list[DocumentPage]:
    text = ""
    try:
        import subprocess, tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as f:
            f.write(data)
            tmp = f.name
        # 尝试 antiword / catdoc
        for cmd in (["antiword", tmp], ["catdoc", tmp]):
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=20)
                if r.returncode == 0:
                    text = r.stdout.decode("utf-8", errors="replace")
                    break
            except Exception:
                continue
        os.unlink(tmp)
    except Exception:
        text = ""
    if not text.strip():
        text = _extract_doc_win32(data)
    if not text.strip():
        return []
    return [_text_page(text, 1)]


def extract_plain(data: bytes, filename: str) -> list[DocumentPage]:
    ext = Path(filename or "").suffix.lower()
    if ext == ".docx":
        pages = extract_docx(data, filename)
        if pages:
            return pages
    if ext in (".doc",):
        pages = extract_doc(data, filename)
        if pages:
            return pages
    if ext in (".md", ".markdown"):
        return extract_markdown(data, filename)
    return extract_txt(data, filename)
