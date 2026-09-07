"""可选依赖安全加载。"""
from __future__ import annotations

import importlib.util
import os
from typing import Any


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def try_import(name: str) -> Any | None:
    try:
        return __import__(name, fromlist=["*"])
    except Exception:
        return None


def get_pymupdf():
    try:
        import pymupdf  # 新 API，不触发 fitz deprecation
        return pymupdf
    except Exception:
        try:
            import fitz  # 旧版 PyMuPDF 兼容
            return fitz
        except Exception:
            return None


def get_pdfplumber():
    try:
        import pdfplumber
        return pdfplumber
    except Exception:
        return None


def get_paddleocr():
    # 减少 Paddle/PaddleX 的无意义网络探测与编译日志
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    os.environ.setdefault("GLOG_minloglevel", "2")
    os.environ.setdefault("FLAGS_minloglevel", "2")
    try:
        from paddleocr import PaddleOCR
        return PaddleOCR
    except Exception:
        return None


def get_pypdf():
    try:
        import pypdf
        return pypdf
    except Exception:
        return None
