"""文本清洗：页眉、页脚、页码、控制字符、重复噪声、注释合并。"""
from __future__ import annotations

import re
from collections import Counter

from backend.document_pipeline.types import DocumentPage, TextBlock

_PAGE_NUMBER_RE = re.compile(r"^\s*(?:第\s*\d+\s*页|[-—–_.\s]*\d{1,4}[-—–_.\s]*|\d{1,4}\s*/\s*\d{1,4})\s*$")


def clean_text_block(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _line_without_page_number(line: str) -> bool:
    return bool(_PAGE_NUMBER_RE.search(line))


def _candidate_lines(pages: list[DocumentPage]) -> list[str]:
    """收集每页首尾行，作为页眉页脚候选。"""
    cand = []
    for p in pages:
        lines = [l.strip() for l in (p.text or "").split("\n") if l.strip()]
        if len(lines) >= 4:
            cand.extend(lines[:2])
            cand.extend(lines[-2:])
    return [c for c in cand if len(c) >= 4 and not _line_without_page_number(c)]


def _repeated_lines(pages: list[DocumentPage], min_ratio: float = 0.5) -> set[str]:
    if not pages:
        return set()
    lines = _candidate_lines(pages)
    cnt = Counter(lines)
    threshold = max(2, int(len(pages) * min_ratio))
    return {line for line, n in cnt.items() if n >= threshold}


def clean_pages(pages: list[DocumentPage]) -> list[DocumentPage]:
    """清理页眉/页脚/页码，并重建块列表与文本。"""
    header_footer = _repeated_lines(pages)
    cleaned = []
    for p in pages:
        lines = [l for l in (p.text or "").split("\n") if l.strip()]
        out_lines = []
        for raw in lines:
            l = raw.strip()
            if _line_without_page_number(l):
                continue
            if l in header_footer:
                continue
            out_lines.append(l)
        text = "\n".join(out_lines)
        blocks = []
        for line in out_lines:
            blocks.append(TextBlock(
                text=line,
                page_no=p.page_no,
                kind="heading" if re.match(r"^#{1,6}\s+", line) else "text",
            ))
        p.text = text
        p.blocks = blocks
        p.meta["cleaned"] = True
        cleaned.append(p)
    return cleaned


def merge_annotations(pages: list[DocumentPage]) -> list[DocumentPage]:
    """将简单编号注释/脚注识别为正文关联提示。

    目前只做轻量处理：
    - 把以“注”“注释”“脚注”开头的孤立行标记为 note
    - 如果页面存在编号注释，尝试附加到对应正文块
    """
    for p in pages:
        if not p.blocks:
            continue
        note_blocks = []
        for b in p.blocks:
            s = b.text.strip()
            if re.match(r"^(注|注释|脚注|备注)[：:\d]", s) or re.match(r"^【注", s):
                b.kind = "note"
                note_blocks.append(b)
        if note_blocks:
            first_note_line = note_blocks[0].text.strip()
            # 附加到第一个文本块，便于保留关联
            for b in p.blocks:
                if b.kind == "text" and b not in note_blocks:
                    b.text = b.text.rstrip() + f"\n【注释】{first_note_line}"
                    break
    return pages
