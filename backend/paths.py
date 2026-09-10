# -*- coding: utf-8 -*-
"""统一路径安全工具：用户名 -> 安全目录名。

所有把 username 拼进文件路径的模块都应使用 safe_username()，避免 `..`、
路径分隔符、Windows 保留名等造成目录穿越或写入异常。
"""
from __future__ import annotations

import re

_DEFAULT = "default"
_MAX_LEN = 64
_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def safe_username(username: str | None) -> str:
    """把任意用户名转成安全的单层目录名（允许中文、字母、数字、下划线、连字符）。"""
    raw = (username or "").strip()
    name = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]", "_", raw)
    name = name.strip("._")
    if not name or name in (".", "..") or set(name) <= {"_"}:
        return _DEFAULT
    if name.lower() in _RESERVED:
        name = f"{name}_user"
    return name[:_MAX_LEN] or _DEFAULT
