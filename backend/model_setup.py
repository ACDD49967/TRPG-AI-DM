# -*- coding: utf-8 -*-
"""一键安装向量模型依赖并下载模型——玩家不需要手动执行任何命令。

- 依赖安装：自动调用当前 Python 环境的 pip。
- 模型下载：优先 huggingface_hub；若 SSL 证书异常，自动降级为 requests 直连下载。
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from typing import Awaitable, Callable


def _run_pip(packages: list[str], cancel_check=None) -> None:
    """执行 pip install；cancel_check 返回 True 时终止子进程。"""
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-input", *packages]
    proc = subprocess.Popen(cmd)
    while proc.poll() is None:
        if cancel_check and cancel_check():
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
            from backend.task_center import TaskCancelled
            raise TaskCancelled("模型依赖安装已取消")
        time.sleep(0.5)
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)


async def ensure_bge_dependencies(cancel_check=None) -> None:
    """安装 BGE-M3 向量模型所需依赖（FlagEmbedding + huggingface_hub + modelscope）。"""
    await asyncio.to_thread(_run_pip, ["FlagEmbedding", "huggingface_hub", "modelscope"], cancel_check)


async def ensure_small_dependencies(cancel_check=None) -> None:
    """安装小中文向量模型所需依赖（sentence-transformers + FlagEmbedding + huggingface_hub）。"""
    await asyncio.to_thread(_run_pip, ["sentence-transformers", "FlagEmbedding", "huggingface_hub", "modelscope"], cancel_check)


async def ensure_reranker_dependencies(cancel_check=None) -> None:
    """安装 BGE-reranker 所需依赖（与向量模型相同）。"""
    await asyncio.to_thread(_run_pip, ["FlagEmbedding", "huggingface_hub", "modelscope"], cancel_check)


async def _download_hf_repo_requests(
    repo_id: str,
    local_dir: str,
    progress_cb: Callable[[float | None, str], Awaitable[None]],
    cancel_check=None,
) -> None:
    """使用 requests 绕过本地证书校验下载 Hugging Face 仓库。"""
    import requests

    os.makedirs(local_dir, exist_ok=True)
    session = requests.Session()
    # 默认开启 TLS 校验；只有用户显式设置 DND_INSECURE_TLS=1 时才允许降级。
    if os.environ.get("DND_INSECURE_TLS", "0") == "1":
        print("[model_setup] 警告：DND_INSECURE_TLS=1，已关闭 TLS 校验")
        session.verify = False
    else:
        ca_bundle = os.environ.get("DND_CA_BUNDLE", "").strip()
        session.verify = ca_bundle or True

    mirror = os.environ.get("HF_MIRROR") or os.environ.get("HF_ENDPOINT") or "https://huggingface.co"
    list_url = f"{mirror}/api/models/{repo_id}/tree/main?recursive=true"
    r = await asyncio.to_thread(session.get, list_url, timeout=60)
    r.raise_for_status()
    items = r.json()
    skip_exts = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg",
                 ".md", ".txt", ".gitattributes", ".ds_store", ".ds_store")
    skip_names = (".onnx", ".onnx_data", "constant_7_attr__value", ".ds_store")
    files = []
    for i in items:
        if i.get("type") != "file" or not i.get("size"):
            continue
        path = str(i.get("path", ""))
        low = path.lower()
        if low.endswith(skip_exts):
            continue
        if "/imgs/" in low or "/images/" in low:
            continue
        if any(low.endswith(x) or x in low for x in skip_names):
            continue
        files.append(i)
    total = sum(int(i.get("size", 0) or 0) for i in files)
    downloaded = 0
    for f in files:
        if cancel_check and cancel_check():
            from backend.task_center import TaskCancelled
            raise TaskCancelled("模型下载已取消")
        path = str(f.get("path", ""))
        if not path:
            continue
        target = os.path.join(local_dir, path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        url = f"{mirror}/{repo_id}/resolve/main/{path}"
        resp = await asyncio.to_thread(
            session.get, url, stream=True, timeout=(15, 120),
            allow_redirects=True,
        )
        resp.raise_for_status()
        try:
            with open(target, "wb") as out:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        if cancel_check and cancel_check():
                            raise RuntimeError("__cancel__")
                        out.write(chunk)
        except RuntimeError as e:
            if str(e) == "__cancel__":
                try:
                    os.remove(target)
                except Exception:
                    pass
                from backend.task_center import TaskCancelled
                raise TaskCancelled("模型下载已取消（已清理半成品文件）") from e
            raise
        downloaded += int(f.get("size", 0) or 0)
        pct = round(downloaded / total * 100, 1) if total > 0 else None
        await progress_cb(pct, path)


async def download_hf_repo(
    repo_id: str,
    local_dir: str,
    progress_cb: Callable[[float | None, str], Awaitable[None]],
    cancel_check=None,
) -> None:
    """从 Hugging Face 下载仓库到 local_dir，并按文件大小回报实时进度。"""
    try:
        from huggingface_hub import HfApi

        os.makedirs(local_dir, exist_ok=True)
        api = HfApi()
        entries = await asyncio.to_thread(api.list_repo_tree, repo_id, recursive=True)
        files = [e for e in entries if hasattr(e, "size") and getattr(e, "size", 0)]
        total = sum(int(getattr(f, "size", 0) or 0) for f in files)
        downloaded = 0
        for f in files:
            if cancel_check and cancel_check():
                from backend.task_center import TaskCancelled
                raise TaskCancelled("模型下载已取消")
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
    except Exception as e:
        from backend.task_center import TaskCancelled
        if isinstance(e, TaskCancelled):
            raise
        print(f"[model_setup] huggingface_hub 下载失败，降级 requests: {e}")
        await _download_hf_repo_requests(repo_id, local_dir, progress_cb, cancel_check=cancel_check)
