"""跨页表格探测与合并。

常见场景：
- 第 A 页表格在底部未结束
- 第 B 页顶部是同一表格的延续，且不重复表头
- 两页表格列数一致、表头一致或下一页无表头
"""
from __future__ import annotations

from backend.document_pipeline.types import DocumentPage, TableBlock


def _col_count(t: TableBlock) -> int:
    if t.headers:
        return len(t.headers)
    if t.rows:
        return max((len(r) for r in t.rows), default=0)
    return 0


def _same_table(prev: TableBlock, cur: TableBlock) -> bool:
    if prev.page_end != cur.page_start - 1:
        return False
    pc, cc = _col_count(prev), _col_count(cur)
    if pc == 0 or cc == 0 or pc != cc:
        return False
    # 如果当前有表头且表头与上一页表头不一致，视为新表
    if cur.headers and prev.headers:
        return [str(h).strip() for h in cur.headers if str(h).strip()] == \
               [str(h).strip() for h in prev.headers if str(h).strip()]
    return True


def merge_cross_page_tables(pages: list[DocumentPage]) -> list[DocumentPage]:
    """原地合并跨页表格。"""
    last_open: TableBlock | None = None
    for page in pages:
        new_tables: list[TableBlock] = []
        for t in list(page.tables):
            if last_open is not None and _same_table(last_open, t):
                # 继承上一页表头
                if not t.headers and last_open.headers:
                    t.headers = list(last_open.headers)
                last_open.rows.extend(t.rows)
                last_open.page_end = t.page_start
                last_open.bboxes.update(t.bboxes)
                # 不把当前页表格单独加入 new_tables，因为已并入 last_open
                continue
            # 尝试寻找当前页顶部能延续 last_open 的表格
            new_tables.append(t)
            last_open = t
        page.tables = new_tables
    return pages
