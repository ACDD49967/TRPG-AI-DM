"""游戏会话管理器——管理活跃会话、事件队列和 SSE 推送。

按职责拆成三个模块，这里只做再导出，既有 `from backend.engine.session import ...` 全部照旧：
- `session_state`：GameSessionState（字段与运行时锁）
- `session_manager`：SessionManager / session_manager 单例 / get_session_for_user
- `sse_bus`：push_event / sse_event_generator / 打字机推送
"""
from backend.engine.session_state import GameSessionState  # noqa: F401
from backend.engine.session_manager import (  # noqa: F401
    SessionManager, get_session_for_user, session_manager,
)
from backend.engine.sse_bus import (  # noqa: F401
    _format_sse, push_event, push_narrative_flush, push_narrative_token,
    sse_event_generator,
)
