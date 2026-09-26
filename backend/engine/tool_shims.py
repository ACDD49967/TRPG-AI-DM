"""工具模块共用的惰性 shim：转发到 dm_agent 的同名运行期工具。

为什么是"惰性 + 转发 dm_agent"而不是直接 `from dm_runtime import ...`：
- 惰性：dm_agent 会再导出各工具模块，模块级导入会形成循环；
- 转发 dm_agent：测试与历史代码用 `patch.object(dm_agent, "_client", ...)` 打桩，
  只有经 dm_agent 取用，这些 patch 才会对所有工具模块同时生效。

这段以前在 character_state / combat / dm_prompts / graph_tools / media_tools /
session_tools / world_tools 里各抄一份，其中 world_tools 的 5 个、media_tools 的 4 个、
session_tools 的 2 个都是**死代码**（定义了没人调用）。现在唯一一份在这里。
"""
from __future__ import annotations

from typing import Any


def _game_system(state: Any) -> str:
    from backend.engine import dm_agent
    return dm_agent._game_system(state)


def _as_bool(value: Any) -> bool:
    from backend.engine import dm_agent
    return dm_agent._as_bool(value)


def _safe_error_text(exc: Any) -> str:
    from backend.engine import dm_agent
    return dm_agent._safe_error_text(exc)


def _client(state: Any):
    from backend.engine import dm_agent
    return dm_agent._client(state)


def _model(state: Any) -> str:
    from backend.engine import dm_agent
    return dm_agent._model(state)
