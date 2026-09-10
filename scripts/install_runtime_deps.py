# -*- coding: utf-8 -*-
"""Setup 阶段依赖安装/模型下载辅助脚本。

用法：
    python scripts/install_runtime_deps.py --core
    python scripts/install_runtime_deps.py --bge          # 安装 FlagEmbedding 并下载 BGE-M3/reranker
    python scripts/install_runtime_deps.py --layout       # 安装 paddlex[ocr] 以启用 PaddleLayout
    python scripts/install_runtime_deps.py --pgvector     # 安装 pgvector/asyncpg
    python scripts/install_runtime_deps.py --all

说明：
- 90% 依赖应在首次 setup 时下载，不进入 git；
- 大模型默认不自动下载，--bge/--layout 需要显式开启；
- 所有下载均使用国内镜像优先，失败时回退默认源。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str], mirror: bool = False) -> bool:
    print(f"[install] {' '.join(cmd)}")
    try:
        if mirror:
            cmd = cmd + [
                "-i", "https://mirrors.aliyun.com/pypi/simple/",
                "--trusted-host", "mirrors.aliyun.com",
            ]
        return subprocess.call(cmd) == 0
    except Exception as e:
        print(f"[install] 执行失败: {e}")
        return False


def install_core() -> bool:
    py = sys.executable
    req = ROOT / "backend" / "requirements.txt"
    if not req.exists():
        print("[install] 缺少 backend/requirements.txt")
        return False
    if run([py, "-m", "pip", "install", "-r", str(req), "--disable-pip-version-check"]):
        return True
    print("[install] 默认源失败，尝试阿里云镜像 ...")
    return run([
        py, "-m", "pip", "install", "-r", str(req),
        "--disable-pip-version-check",
    ], mirror=True)


def install_bge() -> bool:
    py = sys.executable
    # P1-25: download_bge_models.py 使用 ModelScope，必须一并安装 modelscope。
    if not run([py, "-m", "pip", "install", "-q", "FlagEmbedding", "huggingface_hub", "modelscope"]):
        return False
    script = ROOT / "scripts" / "download_bge_models.py"
    if script.exists():
        print("[install] 下载 BGE-M3 / BGE-reranker（ModelScope）...")
        return subprocess.call([py, str(script)]) == 0
    print("[install] 未找到 download_bge_models.py")
    return True


def install_layout() -> bool:
    py = sys.executable
    return run([py, "-m", "pip", "install", "-q", "paddlex[ocr]>=3.7.2"])


def install_pgvector() -> bool:
    py = sys.executable
    ok1 = run([py, "-m", "pip", "install", "-q", "pgvector>=0.3.0"])
    ok2 = run([py, "-m", "pip", "install", "-q", "asyncpg>=0.29.0"])
    return ok1 and ok2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", action="store_true")
    parser.add_argument("--bge", action="store_true")
    parser.add_argument("--layout", action="store_true")
    parser.add_argument("--pgvector", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    plan = []
    if args.all or args.core:
        plan.append(install_core)
    if args.all or args.bge:
        plan.append(install_bge)
    if args.all or args.layout:
        plan.append(install_layout)
    if args.all or args.pgvector:
        plan.append(install_pgvector)

    if not plan:
        parser.print_help()
        return 1

    ok = True
    for fn in plan:
        ok = fn() and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
