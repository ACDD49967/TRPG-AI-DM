# -*- coding: utf-8 -*-
"""检查基础运行依赖是否齐全。

setup.bat / setup.sh / run.bat 通过本脚本判断是否需要执行 pip install，
避免“只装了几个核心包就误判为已安装”的情况（例如漏装 python-multipart）。
"""
from __future__ import annotations

import importlib.util
import sys

# (import 模块名, pip 包名)
REQUIRED = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("openai", "openai"),
    ("sqlalchemy", "sqlalchemy"),
    ("aiosqlite", "aiosqlite"),
    ("pydantic", "pydantic"),
    ("dotenv", "python-dotenv"),
    ("httpx", "httpx"),
    ("multipart", "python-multipart"),
    ("sse_starlette", "sse-starlette"),
    ("json_repair", "json-repair"),
    ("jieba", "jieba"),
    ("rank_bm25", "rank-bm25"),
    ("numpy", "numpy"),
    ("langgraph", "langgraph"),
    ("yaml", "pyyaml"),
    ("pypdf", "pypdf"),
    ("docx", "python-docx"),
    ("pdfplumber", "pdfplumber"),
]

# PyMuPDF 在不同版本中提供 pymupdf 或 fitz 两个导入名，任一存在即可
PDF_MODULES = [("pymupdf", "pymupdf"), ("fitz", "PyMuPDF")]


def _has(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except Exception:
        return False


def main() -> int:
    missing = [pkg for mod, pkg in REQUIRED if not _has(mod)]
    if not any(_has(mod) for mod, _ in PDF_MODULES):
        missing.append("pymupdf")
    if missing:
        print("缺少基础依赖: " + ", ".join(missing))
        print("安装命令: python -m pip install -r backend/requirements.txt")
        return 1
    print("基础依赖已就绪")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
