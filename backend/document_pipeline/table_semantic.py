# -*- coding: utf-8 -*-
"""表格语义化：表头树、合并单元格展开、Markdown/JSON 输出。"""
from __future__ import annotations

import json
import re
from typing import Any


def build_header_tree(headers: list[str]) -> list[dict]:
    """将扁平表头转为简单树结构。

    输入例子：["名称", "值", "备注"]
    输出： [{"name":"名称","children":[]}, ...]
    多级表头可通过“ > ”分隔符表达，例如 "属性 > 力量"。
    """
    tree: list[dict] = []
    for h in headers or []:
        h = str(h or "").strip()
        if not h:
            continue
        parts = [p.strip() for p in re.split(r"\s*>\s*", h) if p.strip()]
        node = tree
        for i, part in enumerate(parts):
            child = next((n for n in node if n.get("name") == part), None)
            if child is None:
                child = {"name": part, "children": []}
                node.append(child)
            if i == len(parts) - 1:
                child.setdefault("leaf", True)
            node = child["children"]
    return tree


def expand_merged_rows(rows: list[list[str]], headers: list[str]) -> list[list[str]]:
    """近似展开合并单元格：空单元格继承同列上一行非空值。"""
    expanded: list[list[str]] = []
    last_values: list[str] = [""] * len(headers or [])
    for row in rows or []:
        cur: list[str] = []
        for i, cell in enumerate(row):
            val = str(cell or "").strip()
            if not val and i < len(last_values):
                val = last_values[i]
            cur.append(val)
            if val and i < len(last_values):
                last_values[i] = val
        expanded.append(cur)
    return expanded


def to_markdown(headers: list[str], rows: list[list[str]]) -> str:
    if not headers and not rows:
        return ""
    lines: list[str] = []
    if headers:
        lines.append("| " + " | ".join(str(h or "") for h in headers) + " |")
        lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows or []:
        lines.append("| " + " | ".join(str(c or "") for c in row) + " |")
    return "\n".join(lines)


def to_json(headers: list[str], rows: list[list[str]]) -> dict:
    headers = [str(h or "") for h in (headers or [])]
    if not headers:
        headers = [f"col{i+1}" for i in range(max((len(r) for r in rows or []), default=0))]
    data = []
    for row in rows or []:
        item = {}
        for i, h in enumerate(headers):
            item[h] = str(row[i] or "") if i < len(row) else ""
        data.append(item)
    return {"headers": headers, "rows": data}


def analyze_table(headers: list[str], rows: list[list[str]]) -> dict[str, Any]:
    """一次性生成表头树、合并展开、Markdown/JSON。"""
    if not headers and rows:
        # 无表头时使用第一行作为表头
        headers = [str(c or "") for c in rows[0]]
        data_rows = rows[1:]
    else:
        data_rows = rows
    expanded = expand_merged_rows(data_rows, headers)
    md = to_markdown(headers, expanded)
    js = to_json(headers, expanded)
    return {
        "headers": headers,
        "header_tree": build_header_tree(headers),
        "rows": expanded,
        "markdown": md,
        "json": js,
    }


def semanticize_table(table: Any) -> None:
    """原地给 TableBlock 填充语义字段。"""
    try:
        info = analyze_table(table.headers, table.rows)
        table.headers = info["headers"]
        table.rows = info["rows"]
        table.header_tree = info["header_tree"]
        table.markdown = info["markdown"]
        table.json_data = info["json"]
    except Exception as e:
        table.meta.setdefault("semantic_error", str(e))


def semanticize_pages(pages: list) -> int:
    count = 0
    for page in pages:
        for tbl in getattr(page, "tables", []) or []:
            semanticize_table(tbl)
            count += 1
    return count
