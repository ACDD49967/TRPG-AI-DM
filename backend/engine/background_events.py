"""后台剧情推进：玩家视线之外的世界动态（按回合间隔触发、低成本、可关闭）。

按职责拆三段，这里只留调度与再导出（`dm_agent` 的 import 面不变）：
- `background_prompt`：提示词、模型配置、线程提取与 JSON 解析
- `background_apply`：把一拍事件写进世界状态
- 本模块：should_run_background / advance_background_plot / _if_due
"""
from __future__ import annotations

import asyncio
from typing import Any

from backend.engine.llm_utils import strip_refusal

from backend.engine.background_prompt import (  # noqa: F401
    ALLOWED_FLAG_STATUS, BACKGROUND_INTERVAL_DEEP, BACKGROUND_INTERVAL_LITE,
    BACKGROUND_SYSTEM_PROMPT, MAX_BACKGROUND_EVENTS_PER_RUN, _client, _extract_json_array,
    _hidden_threads, _model, _play_mode, should_run_background,
)
from backend.engine.background_apply import (  # noqa: F401
    _apply_background_beat, _fallback_background_plot,
)


async def advance_background_plot(state: Any) -> list[dict]:
    """执行一轮幕后推进，返回新增的幕后事件列表。"""
    ws = getattr(state, "world_state", None)
    if ws is None:
        return []
    mem = getattr(state, "memory", None)
    threads = _hidden_threads(state)
    threads_text = "\n".join(
        f"- {t.get('key')} [{t.get('status', '未触发')}]: {str(t.get('description', ''))[:100]}"
        for t in threads[-8:]
    ) or "（暂无暗线）"
    major_text = ""
    if mem is not None:
        major_text = "\n".join(
            f"- [第{e.get('turn', 0)}轮] {str(e.get('title', ''))[:60]}: {str(e.get('description', ''))[:100]}"
            for e in (getattr(mem, "major_events", None) or [])[-6:]
        )
    npc_text = ""
    if ws.npcs:
        npc_text = "\n".join(
            f"- {str(n.name)[:40]} ({str(n.role)[:40]}, 态度:{n.attitude}, 位置:{str(n.location)[:40]}, 剧情关联:{str(n.relation_to_plot or '未知')[:80]})"
            for n in ws.npcs[:10]
        )
    location_text = ""
    if ws.locations:
        location_text = "\n".join(
            f"- {str(l.name)[:40]} ({l.status}, 类型:{str(l.type or '未知')[:40]})" for l in ws.locations[:8]
        )

    user_prompt = f"""当前回合：第 {ws.turn_count} 轮
当前场景：{ws.scene.current_location} | {ws.scene.current_time or f'第{ws.scene.day_count}天'} | {ws.scene.weather}

暗线/旗标：
{threads_text}

大事件：
{major_text or "（暂无）"}

重要人物：
{npc_text or "（暂无）"}

地点：
{location_text or "（暂无）"}

请生成 1-{MAX_BACKGROUND_EVENTS_PER_RUN} 条幕后进展。"""

    client = _client(state)
    model = _model(state)
    max_tokens = 200 if _play_mode(state) == "lite" else 300
    try:
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": BACKGROUND_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.8,
            ),
            timeout=25,
        )
        content = strip_refusal(resp.choices[0].message.content or "")
    except Exception:
        return _fallback_background_plot(state)

    beats = _extract_json_array(content)[:MAX_BACKGROUND_EVENTS_PER_RUN]
    applied = []
    for beat in beats:
        entry = _apply_background_beat(state, ws, beat)
        if entry:
            applied.append(entry)
    if not applied:
        return _fallback_background_plot(state)
    return applied


async def advance_background_plot_if_due(state: Any) -> list[dict]:
    """玩家回合结束后按需触发后台推进；异常时走兜底，绝不影响主流程。"""
    try:
        if not should_run_background(state):
            return []
        return await advance_background_plot(state)
    except Exception:
        try:
            return _fallback_background_plot(state)
        except Exception:
            return []
