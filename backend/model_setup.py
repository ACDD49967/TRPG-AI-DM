"""一键安装向量模型依赖并下载模型——玩家不需要手动执行任何命令。

- 依赖安装：自动调用当前 Python 环境的 pip。
- 模型下载：通过 huggingface_hub 拉取完整 BGE-M3 / BGE-reranker 到本地目录。
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from typing import Awaitable, Callable


def _run_pip(packages: list[str]) -> None:
    """在后台线程中执行 pip install（阻塞但可取消/可观察）。"""
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-input", *packages]
    subprocess.check_call(cmd)


async def ensure_bge_dependencies() -> None:
    """安装 BGE-M3 向量模型所需依赖（FlagEmbedding + huggingface_hub）。"""
    await asyncio.to_thread(_run_pip, ["FlagEmbedding", "huggingface_hub"])


async def ensure_reranker_dependencies() -> None:
    """安装 BGE-reranker 所需依赖（与向量模型相同）。"""
    await asyncio.to_thread(_run_pip, ["FlagEmbedding", "huggingface_hub"])


async def download_hf_repo(
    repo_id: str,
    local_dir: str,
    progress_cb: Callable[[float | None, str], Awaitable[None]],
) -> None:
    """从 Hugging Face 下载仓库到 local_dir，并按文件大小回报实时进度。"""
    from huggingface_hub import HfApi

    os.makedirs(local_dir, exist_ok=True)
    api = HfApi()
    entries = await asyncio.to_thread(api.list_repo_tree, repo_id, recursive=True)
    files = [e for e in entries if hasattr(e, "size") and getattr(e, "size", 0)]
    total = sum(int(getattr(f, "size", 0) or 0) for f in files)
    downloaded = 0
    for f in files:
        path = getattr(f, "path")
        await asyncio.to_thread(
            api.hf_hub_download,
            repo_id=repo_id,
            filename=path,
            local_dir=local_dir,
        )
        downloaded += int(getattr(f, "size", 0) or 0)
        pct = round(downloaded / total * 100, 1) if total > 0 else None
        await progress_cb(pct, path)
