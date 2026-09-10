# -*- coding: utf-8 -*-
"""迁移旧存档：删除 session.api_key 明文，避免历史存档继续泄露 Key。

用法：
    python scripts/migrate_saves_remove_api_key.py [--path saves] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def migrate_file(path: Path, dry_run: bool = False) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    session = data.get("session")
    if not isinstance(session, dict) or "api_key" not in session:
        return False
    if dry_run:
        return True
    session.pop("api_key", None)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default="saves")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(args.path)
    if not root.exists():
        print(f"[migrate_saves] 路径不存在: {root}", file=sys.stderr)
        return 2
    files = [root] if root.is_file() else list(root.rglob("*.json"))
    changed = 0
    for path in files:
        if migrate_file(path, dry_run=args.dry_run):
            changed += 1
            print(f"  {'[dry-run] ' if args.dry_run else ''}{path}")
    print(f"[migrate_saves] 处理 {changed} 个含 api_key 的存档"
          + ("（未写入）" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
