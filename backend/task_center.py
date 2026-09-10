# -*- coding: utf-8 -*-
"""轻量级长时间任务中心：创建任务、更新快照、SSE 输出进度。

设计：
- 任务只保存最新快照，不保留历史事件流；
- SSE 生成器轮询快照变化，避免为每个子任务维护队列；
- 更新由同步回调触发，使用线程锁保证安全；
- 支持取消标志，但实际取消由具体任务实现检查 `cancel_requested`。
"""
from __future__ import annotations

import asyncio
import json
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def _json_safe(value: Any, depth: int = 0) -> Any:
    """递归转换任意对象为 JSON 可序列化结构，并对超大字段做截断。"""
    if depth > 8:
        return str(value)[:2000]
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, str) and len(value) > 12000:
            return value[:12000] + "…[truncated]"
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v, depth + 1) for k, v in list(value.items())[:200]}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v, depth + 1) for v in list(value)[:200]]
    if hasattr(value, "__dict__"):
        return _json_safe(vars(value), depth + 1)
    return str(value)[:2000]


class TaskCancelled(Exception):
    """任务被前端取消时，由进度回调抛出，供具体任务实现中断。"""


@dataclass
class Task:
    id: str
    type: str
    status: str = "pending"  # pending | running | completed | failed | cancelled
    phase: str = ""
    current: int = 0
    total: int = 0
    progress: float = 0.0
    message: str = ""
    result: Any = None
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    cancel_requested: bool = False

    def to_dict(self) -> dict:
        return _json_safe(asdict(self))


class TaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()

    def create(self, task_type: str, total: int = 0, phase: str = "pending", message: str = "") -> Task:
        task = Task(id=uuid.uuid4().hex[:16], type=task_type, total=total,
                    phase=phase, message=message)
        with self._lock:
            self._tasks[task.id] = task
        self.prune()
        return task

    def prune(self, max_age_seconds: float = 3600.0, max_tasks: int = 200) -> int:
        """清理过期/超量任务，避免内存无限增长。"""
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(seconds=max_age_seconds)
        removed = 0
        with self._lock:
            for task_id, task in list(self._tasks.items()):
                if task.status not in TERMINAL_STATUSES:
                    continue
                try:
                    updated = datetime.fromisoformat(task.updated_at)
                except Exception:
                    continue
                if updated < cutoff:
                    del self._tasks[task_id]
                    removed += 1
            if len(self._tasks) > max_tasks:
                ordered = sorted(self._tasks.values(), key=lambda t: t.updated_at)
                for task in ordered[:len(self._tasks) - max_tasks]:
                    self._tasks.pop(task.id, None)
                    removed += 1
        return removed

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def list(self, limit: int = 50) -> list[Task]:
        with self._lock:
            items = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
        return items[:limit]

    def update(
        self,
        task_id: str,
        *,
        status: str | None = None,
        phase: str | None = None,
        current: int | None = None,
        total: int | None = None,
        progress: float | None = None,
        message: str | None = None,
        result: Any = None,
        error: str | None = None,
        cancel_requested: bool | None = None,
    ) -> Task | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            if status is not None:
                task.status = status
            if phase is not None:
                task.phase = phase
            if current is not None:
                task.current = current
            if total is not None:
                task.total = total
            if progress is not None:
                task.progress = progress
            if message is not None:
                task.message = message
            if result is not None:
                task.result = result
            if error is not None:
                task.error = error
            if cancel_requested is not None:
                task.cancel_requested = cancel_requested
            if total and current is not None:
                task.progress = round(min(100.0, max(0.0, current / total * 100.0)), 2)
            task.updated_at = datetime.now().isoformat()
            return task

    def delete(self, task_id: str) -> bool:
        with self._lock:
            if task_id not in self._tasks:
                return False
            del self._tasks[task_id]
            return True

    def request_cancel(self, task_id: str) -> bool:
        return self.update(task_id, cancel_requested=True) is not None


task_manager = TaskManager()


def task_progress_callback(task_id: str, phase: str = ""):
    """构造一个同步 progress_callback，供文档管线/model 下载使用。

    每次进度回调都会检查取消标志；已取消时抛出 TaskCancelled，
    让在线程中执行的同步管线立即中断。
    """
    def cb(current: int, total: int, detail: str | None = None) -> None:
        task = task_manager.get(task_id)
        if task is not None and task.cancel_requested:
            raise TaskCancelled(f"任务 {task_id} 已取消")
        task_manager.update(
            task_id,
            status="running",
            phase=phase,
            current=current,
            total=total,
            message=detail or f"{phase} {current}/{total}",
        )
    return cb


def is_cancel_requested(task_id: str) -> bool:
    task = task_manager.get(task_id)
    return bool(task and task.cancel_requested)


def make_task_event_text(task: Task) -> str:
    """将任务快照格式化为 SSE data 事件。"""
    payload = json.dumps(task.to_dict(), ensure_ascii=False, default=str)
    return f"data: {payload}\n\n"


async def task_sse_generator(task_id: str):
    """SSE 生成器：轮询任务快照，输出 progress/complete/error 事件。"""
    last: str | None = None
    while True:
        task = task_manager.get(task_id)
        if task is None:
            yield "data: " + json.dumps({"type": "error", "msg": "任务不存在"}, ensure_ascii=False) + "\n\n"
            break

        snapshot = json.dumps(task.to_dict(), ensure_ascii=False, default=str)
        if snapshot != last:
            yield make_task_event_text(task)
            last = snapshot

        if task.status in TERMINAL_STATUSES:
            break
        await asyncio.sleep(0.3)


async def wait_task(task_id: str, timeout: float | None = None) -> Task | None:
    """等待任务进入终态，供测试/内部使用。"""
    import asyncio
    waited = 0.0
    while True:
        task = task_manager.get(task_id)
        if task is None or task.status in TERMINAL_STATUSES:
            return task
        await asyncio.sleep(0.3)
        waited += 0.3
        if timeout is not None and waited >= timeout:
            return task
