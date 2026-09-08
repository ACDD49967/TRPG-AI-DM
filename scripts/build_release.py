# -*- coding: utf-8 -*-
"""构建 Release 源码包。

用法：
    python scripts/build_release.py

输出：
    dist/TRPG-AI-DM-v<version>.zip

打包策略：
- 只打包运行必需源码与启动脚本；
- 不打包 .venv / node_modules / docs / models / media / knowledge_base / saves / characters / .git / .claude 等；
- 前端依赖仍由 setup 脚本通过 npm install 下载，Python 依赖由 setup 通过 pip install 下载；
- 如需离线依赖，后续可在 release 中附加 wheels 目录并让 setup 优先从本地 wheels 安装。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

INCLUDE_DIRS = [
    "backend",
    "frontend",
    "scripts",
]

INCLUDE_FILES = [
    "README.md",
    "LICENSE",
    ".env.example",
    ".gitignore",
    "setup.bat",
    "setup.sh",
    "run.bat",
    "run.sh",
    "pyproject.toml",
]

EXCLUDE_NAMES = {
    "__pycache__", ".venv", "venv", "env", "node_modules",
    "docs", "models", "media", "knowledge_base", "saves",
    "characters", "world_states", "scenarios", "data", "memory_vault", "dist",
    ".git", ".claude", ".idea", ".vscode", ".dsh-plugins",
    ".install-cache", ".git-ssl", "frontend/dist",
}


def _version() -> str:
    try:
        pkg = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
        return str(pkg.get("version", "dev"))
    except Exception:
        return "dev"


def _build_frontend() -> None:
    npm = "npm.cmd" if os.name == "nt" else "npm"
    if shutil.which(npm) is None:
        print("[release] npm 未安装，跳过前端构建")
        return
    print("[release] 构建前端 ...")
    frontend = ROOT / "frontend"
    if not (frontend / "node_modules").exists():
        subprocess.run([npm, "install"], cwd=frontend, check=False)
    subprocess.run([npm, "run", "build"], cwd=frontend, check=True)


def _ignore(dirpath: str, names: list[str]) -> set[str]:
    rel = Path(dirpath).relative_to(ROOT)
    ignored: set[str] = set()
    for name in names:
        p = rel / name
        if name in EXCLUDE_NAMES:
            ignored.add(name)
        elif name.startswith("."):
            ignored.add(name)
        elif p.name == "__pycache__":
            ignored.add(name)
    return ignored


def _stage() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="dnd-release-"))
    for d in INCLUDE_DIRS:
        src = ROOT / d
        if src.exists():
            shutil.copytree(src, tmp / d, ignore=_ignore)
    for f in INCLUDE_FILES:
        src = ROOT / f
        if src.exists():
            shutil.copy2(src, tmp / f)
    return tmp


def build() -> Path:
    _build_frontend()
    DIST.mkdir(parents=True, exist_ok=True)
    ver = _version()
    out = DIST / f"TRPG-AI-DM-v{ver}.zip"
    print(f"[release] 版本 {ver} -> {out}")
    stage = _stage()
    try:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(stage))
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    print(f"[release] 完成：{out} ({out.stat().st_size / 1024 / 1024:.2f} MB)")
    return out


if __name__ == "__main__":
    sys.exit(0 if build() else 1)
