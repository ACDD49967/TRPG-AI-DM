# -*- coding: utf-8 -*-
"""一次性脱敏：把 dist/ 探针脚本里的硬编码 API Key 替换为环境变量读取。

用法：
    python scripts/sanitize_dist_secrets.py [--path dist] [--dry-run]

不会打印完整 Key；仅报告文件与命中数。默认只处理 .py 文件。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

KEY_PATTERNS = [
    re.compile(r"(['\"])sk-[A-Za-z0-9_\-]{20,}\1"),
    re.compile(r"(['\"])gh[pousr]_[A-Za-z0-9]{20,}\1"),
    re.compile(r"(['\"])github_pat_[A-Za-z0-9_]{20,}\1"),
]

REPLACEMENT = 'os.environ.get("LLM_API_KEY", "")'
IMPORT_LINE = "import os\n"


def _ensure_os_import(text: str) -> str:
    if re.search(r"^\s*import os\b", text, re.MULTILINE):
        return text
    lines = text.splitlines(keepends=True)
    if lines and lines[0].startswith("#!"):
        lines.insert(1, IMPORT_LINE)
    else:
        lines.insert(0, IMPORT_LINE)
    return "".join(lines)


def sanitize_file(path: Path, dry_run: bool = False) -> int:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return 0
    total = 0
    new_text = text
    for pattern in KEY_PATTERNS:
        new_text, count = pattern.subn(REPLACEMENT, new_text)
        total += count
    if total and not dry_run:
        new_text = _ensure_os_import(new_text)
        path.write_text(new_text, encoding="utf-8")
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description="脱敏 dist 中的硬编码 API Key")
    parser.add_argument("--path", default="dist")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(args.path)
    if not root.exists():
        print(f"[sanitize_dist] 路径不存在: {root}", file=sys.stderr)
        return 2
    files = [root] if root.is_file() else [p for p in root.rglob("*.py") if p.is_file()]
    changed = 0
    for path in files:
        count = sanitize_file(path, dry_run=args.dry_run)
        if count:
            changed += 1
            print(f"  {'[dry-run] ' if args.dry_run else ''}{path}: {count} 处")
    print(f"[sanitize_dist] 共处理 {changed} 个文件"
          + ("（未写入）" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
