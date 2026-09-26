"""时间规则门面：推进时间、长休结算与场景时间同步。

按职责拆三段，这里只做再导出，`rest_tools` / `world_scene_tools` / `tool_executor` 的
`time_rules.xxx` 调用与测试补丁（`patch("backend.engine.time_rules.advance")`）都不变：
- `time_clock`：时段与时钟文本
- `time_supplies`：口粮/饮水/照明消耗与力竭
- 本模块：advance / finish_long_rest / sync_scene_time / advance_time 工具
"""
from __future__ import annotations

from typing import Any

from backend.engine.time_clock import (  # noqa: F401
    EXHAUSTION_EFFECTS, MAX_EXHAUSTION, TIME_HINT, _PERIODS, _PERIOD_START, _parse_clock,
    clock_text, ensure_clock, parse_target_clock, period_of,
)
from backend.engine.time_supplies import (  # noqa: F401
    LIGHT_KEYWORDS, RATIONS_KEYWORDS, WATER_KEYWORDS, _consume_daily_supplies,
    _consume_item, _has_item, _item_qty_left, _items, _set_exhaustion, exhaustion_level,
    exhaustion_note,
)


async def advance(state: Any, minutes: int, reason: str = "",
                  light_source: str = "", label: str = "") -> dict:
    """推进游戏内时间并结算后果（补给、照明、力竭）。返回结果字典。"""
    from backend.engine.session import push_event

    minutes = max(0, int(minutes or 0))
    start = _parse_clock(state)
    before_day = start // (24 * 60) + 1
    end = start + minutes
    after_day = end // (24 * 60) + 1
    days_crossed = max(0, after_day - before_day)

    try:
        state.clock_minutes = end
    except Exception:
        pass
    ws = getattr(state, "world_state", None)
    scene = getattr(ws, "scene", None)
    if scene is not None:
        scene.day_count = after_day
        # label 非空时保留 DM 的叙述文字（"入夜（抵达后约半刻）"），只让权威时钟前进
        scene.current_time = (label or clock_text(end))[:24]
        if hasattr(ws, "save"):
            try:
                ws.save()
            except Exception:
                pass

    notes: list[str] = []
    hours = minutes / 60
    if light_source:
        torches = max(1, int(-(-hours // 1))) if hours else 0      # 向上取整：1 支/小时
        used = _consume_item(state, LIGHT_KEYWORDS, torches)
        if used:
            notes.append(f"消耗 {torches} 份照明（{used}）")
        else:
            notes.append(f"⚠ 没有可用的照明（需要 {torches} 份），黑暗中行动请按劣势处理")
    if days_crossed:
        notes.extend(await _consume_daily_supplies(state, days_crossed))

    label = f"（{reason}）" if reason else ""
    summary = (f"🕐 时间推进 {minutes} 分钟{label} → {clock_text(end)}"
               + (f"，跨越 {days_crossed} 天" if days_crossed else ""))
    if notes:
        summary += "\n" + "\n".join(notes)
    level = exhaustion_level(state)
    if level:
        summary += f"\n当前{exhaustion_note(level)}"

    await push_event(state, "game_event", {
        "type": "time",
        "description": summary,
        "extra": {"minutes": minutes, "day": after_day, "clock": clock_text(end),
                  "reason": reason, "notes": notes, "exhaustion": level},
    })
    return {"minutes": minutes, "day": after_day, "clock": clock_text(end),
            "days_crossed": days_crossed, "notes": notes, "exhaustion": level,
            "summary": summary}


async def _exec_advance_time(args: dict, state: Any) -> str:
    """工具：推进游戏内时间（旅行/搜索/等待/休息）。"""
    try:
        minutes = int(args.get("minutes") or 0)
    except (TypeError, ValueError):
        minutes = 0
    try:
        minutes += int(args.get("hours") or 0) * 60
    except (TypeError, ValueError):
        pass
    try:
        minutes += int(args.get("days") or 0) * 24 * 60
    except (TypeError, ValueError):
        pass
    if minutes <= 0:
        return ("⚠ advance_time 需要 minutes / hours / days 之一（例如赶路 4 小时：hours=4）。"
                f" 当前时间：{clock_text(_parse_clock(state))}")
    result = await advance(state, minutes, str(args.get("reason") or ""),
                           str(args.get("light_source") or ""))
    # 旅行节奏与强行军（可选）：传了 pace 就当作在赶路，按 5e 记当天里程并掷豁免
    pace = str(args.get("pace") or "").strip()
    if pace:
        from backend.engine.travel_rules import apply_travel
        notes = await apply_travel(state, minutes / 60, pace)
        if notes:
            result["summary"] += "\n" + "\n".join(notes)
    return result["summary"]


async def finish_long_rest(state: Any) -> str:
    """长休后的时间与恢复：推进 8 小时，吃过的口粮让力竭 −1。"""
    result = await advance(state, 8 * 60, "长休")
    note = ""
    level = exhaustion_level(state)
    if level > 0 and _has_item(state, RATIONS_KEYWORDS):
        new_level = await _set_exhaustion(state, level - 1, "长休恢复")
        note = f"力竭 {level} → {new_level}"
    elif level > 0:
        note = "没有口粮，长休无法降低力竭"
    return result["summary"] + (f"\n{note}" if note else "")


async def sync_scene_time(state: Any, text: str, reason: str = "场景时间更新") -> str:
    """把 DM 写进 current_time 的叙述文字与权威时钟对齐。

    实测问题：DM 常常用 `update_scene(current_time="入夜")` 推进时间，
    于是日数不动、口粮不扣、力竭不涨——"过了三天"只活在叙事里。
    这里解析叙述时间，必要时推进时钟（跨天会照常结算补给与力竭），
    但**保留 DM 的叙述文字**显示给玩家，只有权威时钟前进。
    """
    current = ensure_clock(state)
    target = parse_target_clock(text, current)
    if target is None:
        return ""
    delta = target - current
    if delta < 15:                     # 几分钟的措辞差异不折腾
        if delta <= 0:
            return ""
    result = await advance(state, delta, reason, label=str(text or ""))
    return result["summary"]
