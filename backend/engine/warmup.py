"""后台预热：把模型加载与检索索引构建移出启动关键路径。

应用启动只调度预热任务并立即就绪；预热在线程中继续执行，
状态可通过 /api/system/warmup 查询。
"""
from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field


@dataclass
class WarmupSnapshot:
    state: str = "pending"          # pending | running | ready | failed
    started_at: float = 0.0         # 调度时间（unix 秒）
    duration_ms: float = 0.0
    stages_ms: dict[str, float] = field(default_factory=dict)
    error: str = ""

    @property
    def ready(self) -> bool:
        return self.state == "ready"


_snapshot = WarmupSnapshot()
_lock = threading.Lock()
_task: asyncio.Task | None = None


def _record_stage(name: str, ms: float) -> None:
    with _lock:
        _snapshot.stages_ms[name] = ms


def _run_warmup() -> None:
    """在线程中执行；异常不抛出，只记录为 failed。"""
    started = time.perf_counter()
    try:
        from backend.engine.rag_utils import warmup_rag

        warmup_rag(on_stage=_record_stage)
        state = "ready"
        error = ""
    except Exception as exc:  # pragma: no cover - 兜底
        state = "failed"
        error = f"{type(exc).__name__}: {str(exc)[:240]}"
    with _lock:
        _snapshot.state = state
        _snapshot.error = error
        _snapshot.duration_ms = round((time.perf_counter() - started) * 1000, 2)
    print(f"[Warmup] 预热{('完成' if state == 'ready' else '失败')} "
          f"{_snapshot.duration_ms:.0f}ms stages={_snapshot.stages_ms}")


async def start_background_warmup() -> "asyncio.Task | None":
    """调度后台预热并立即返回；重复调用复用同一任务。"""
    global _task
    if _task is not None and not _task.done():
        return _task
    with _lock:
        if _snapshot.state == "ready":
            return None
        _snapshot.state = "running"
        _snapshot.started_at = time.time()
        _snapshot.stages_ms = {}
        _snapshot.error = ""
    # 首次调用可能不在事件循环中（例如测试/脚本），退化为同步执行
    try:
        _task = asyncio.create_task(asyncio.to_thread(_run_warmup))
    except RuntimeError:  # pragma: no cover
        _run_warmup()
        _task = None
    return _task


async def wait_for_warmup(timeout: float | None = None) -> dict:
    task = _task
    if task is not None:
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
        except Exception:
            pass
    return status()


def status() -> dict:
    with _lock:
        return {
            "state": _snapshot.state,
            "ready": _snapshot.ready,
            "started_at": _snapshot.started_at,
            "duration_ms": _snapshot.duration_ms,
            "stages_ms": dict(_snapshot.stages_ms),
            "error": _snapshot.error,
        }


def reset_for_tests() -> None:
    """仅供测试：把状态恢复为未预热。"""
    global _task, _snapshot
    _task = None
    _snapshot = WarmupSnapshot()
