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

_RESOURCE_ID_RE = re.compile(r"^[0-9A-Za-z_-]{1,128}$")


class InvalidResourceId(ValueError):
    """资源标识不合法；API 层将其转换为明确的 400 响应。"""


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


def validate_resource_id(resource_id: str | None, field: str = "资源 ID") -> str:
    """验证会拼接到文件名中的 ID，确保它只能表示单层文件名。"""
    value = resource_id if isinstance(resource_id, str) else ""
    if not _RESOURCE_ID_RE.fullmatch(value) or value.lower() in _RESERVED:
        raise InvalidResourceId(f"{field}格式非法：仅允许 1-128 位字母、数字、下划线和连字符")
    return value
