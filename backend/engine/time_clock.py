"""游戏内时钟：时段划分、分钟数与文本互转、从场景文本解析目标时间。

从 `backend/engine/time_rules.py` 拆出（那边保留推进/长休/场景同步的流程）。
"""
from __future__ import annotations

import re
from typing import Any


TIME_HINT = "[系统-时间]"
MAX_EXHAUSTION = 6

# 常见叙述时间 → 当天的分钟数（时钟缺失时的起点参考）
_PERIOD_START = {
    "清晨": 6 * 60, "早晨": 7 * 60, "上午": 9 * 60, "正午": 12 * 60, "中午": 12 * 60,
    "下午": 14 * 60, "傍晚": 17 * 60, "黄昏": 18 * 60, "日落": 18 * 60,
    "夜晚": 20 * 60, "入夜": 20 * 60, "深夜": 23 * 60, "午夜": 0,
    "凌晨": 3 * 60, "黎明": 5 * 60,
}
_PERIODS = [
    (0, "深夜"), (5 * 60, "黎明"), (6 * 60, "清晨"), (8 * 60, "上午"),
    (11 * 60, "正午"), (13 * 60, "下午"), (17 * 60, "黄昏"), (19 * 60, "夜晚"),
    (22 * 60, "深夜"),
]

# 力竭等级 → 5e 机械后果（给 DM 的提示 + 玩家可见说明）
EXHAUSTION_EFFECTS = {
    1: "属性检定具有劣势",
    2: "移动速度减半",
    3: "攻击检定与豁免具有劣势",
    4: "生命值上限减半",
    5: "移动速度降为 0",
    6: "死亡",
}

RATIONS_KEYWORDS = ("口粮", "干粮", "rations", "旅行干粮", "干肉")
WATER_KEYWORDS = ("水袋", "水囊", "清水", "饮水", "water")
LIGHT_KEYWORDS = ("火把", "灯油", "提灯", "油灯", "蜡烛", "torch", "lantern")


def period_of(minutes: int) -> str:
    """分钟数 → 时段词（提示用）。"""
    minute_of_day = int(minutes) % (24 * 60)
    label = _PERIODS[0][1]
    for start, name in _PERIODS:
        if minute_of_day >= start:
            label = name
    return label


def _parse_clock(state: Any) -> int:
    """从会话/场景里推断起始分钟数：优先已记录的时钟，其次解析 current_time 文案。"""
    recorded = getattr(state, "clock_minutes", None)
    if isinstance(recorded, int) and recorded >= 0:
        return recorded
    ws = getattr(state, "world_state", None)
    scene = getattr(ws, "scene", None)
    text = str(getattr(scene, "current_time", "") or "")
    day = max(1, int(getattr(scene, "day_count", 1) or 1))
    minute_of_day = 8 * 60                     # 默认早上 8 点开始
    match = re.search(r"(\d{1,2})\s*[:：]\s*(\d{2})", text)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            minute_of_day = hour * 60 + minute
    else:
        for word, start in _PERIOD_START.items():
            if word in text:
                minute_of_day = start
                break
    return (day - 1) * 24 * 60 + minute_of_day


def clock_text(minutes: int) -> str:
    day = int(minutes) // (24 * 60) + 1
    minute_of_day = int(minutes) % (24 * 60)
    return f"第{day}天 {minute_of_day // 60:02d}:{minute_of_day % 60:02d}（{period_of(minutes)}）"


def ensure_clock(state: Any) -> int:
    """把当前场景时间固化为权威时钟。

    必须在 DM 改写 `current_time` **之前**调用：否则叙述文字已经被覆盖，
    就再也算不出"从清晨到入夜"到底是几小时（实测踩过这个坑）。
    """
    current = _parse_clock(state)
    try:
        state.clock_minutes = current
    except Exception:
        pass
    return current


def parse_target_clock(text: str, current_minutes: int) -> int | None:
    """把叙述时间解析成"应该处于的分钟数"；解析不出返回 None。

    支持：'黄昏' '入夜' '深夜' 等时段词、'08:30' 显式时刻、'第2天' 显式日数。
    """
    raw = str(text or "").strip()
    if not raw:
        return None
    day = None
    match = re.search(r"第\s*(\d+)\s*天", raw)
    if match:
        day = max(1, int(match.group(1)))
    minute_of_day = None
    clock = re.search(r"(\d{1,2})\s*[:：]\s*(\d{2})", raw)
    if clock:
        hour, minute = int(clock.group(1)), int(clock.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            minute_of_day = hour * 60 + minute
    else:
        for word, start in _PERIOD_START.items():
            if word in raw:
                minute_of_day = start
                break
    if minute_of_day is None and day is None:
        return None
    current_day = current_minutes // (24 * 60) + 1
    if minute_of_day is None:
        minute_of_day = current_minutes % (24 * 60)
    if day is None:
        day = current_day
        if minute_of_day <= (current_minutes % (24 * 60)) - 1:
            # 叙述时间早于当前时刻 → 理解为第二天（例如 22:00 之后写"清晨"）
            day = current_day + 1
    return (day - 1) * 24 * 60 + minute_of_day
