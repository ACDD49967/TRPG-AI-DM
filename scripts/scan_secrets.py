# -*- coding: utf-8 -*-
"""密钥/敏感信息扫描器（发布前安全闸门）。

用法：
    python scripts/scan_secrets.py [--path DIR] [--policy high|all] [--json] [--quiet]

- high 策略只匹配高置信密钥格式（OpenAI/DeepSeek Key、GitHub Token、私钥块）。
- 命中返回码 1；未命中返回 0。
- 默认跳过 .git/.venv/node_modules/__pycache__ 等目录；显式指定 --path dist 时会扫描 dist。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".dsh-plugins", ".idea"}

PATTERNS = [
    ("openai-like-key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"), True),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), True),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), True),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), True),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), True),
    ("generic-secret-assignment", re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"][^'\"]{16,}['\"]"), False),
]

TEXT_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".md", ".txt", ".yaml", ".yml",
             ".toml", ".ini", ".cfg", ".env", ".example", ".sh", ".bat", ".ps1", ".html"}


def _mask(value: str) -> str:
    if len(value) <= 10:
        return "*" * len(value)
    return value[:4] + "..." + value[-4:]


def scan_path(root: Path, policy: str = "high") -> list[dict]:
    findings: list[dict] = []
    files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
    for path in files:
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_EXTS and path.name not in (".env", ".env.example"):
            continue
        try:
            if path.stat().st_size > 5 * 1024 * 1024:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            for name, pattern, high_confidence in PATTERNS:
                if policy == "high" and not high_confidence:
                    continue
                for match in pattern.finditer(line):
                    raw = match.group(0)
                    findings.append({
                        "file": str(path),
                        "line": line_no,
                        "pattern": name,
                        "matched": _mask(raw),
                        "high": high_confidence,
                    })
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="扫描高置信密钥/敏感信息")
    parser.add_argument("--path", default=".", help="扫描根目录或单文件")
    parser.add_argument("--policy", choices=["high", "all"], default="high")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"[scan_secrets] 路径不存在: {root}", file=sys.stderr)
        return 2
    findings = scan_path(root, args.policy)
    if args.json:
        print(json.dumps(findings, ensure_ascii=False, indent=2))
    elif findings:
        print(f"[scan_secrets] 发现 {len(findings)} 处敏感信息（policy={args.policy}）：")
        for f in findings:
            print(f"  - {f['file']}:{f['line']} [{f['pattern']}] {f['matched']}")
    elif not args.quiet:
        print(f"[scan_secrets] 未发现敏感信息（policy={args.policy}）")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
