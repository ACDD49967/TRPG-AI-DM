"""后台剧情推进的提示词、模型配置与输出解析。

从 `backend/engine/background_events.py` 拆出；落账在 background_apply，调度在主模块。
"""
from __future__ import annotations

import json
import re
from typing import Any

from openai import AsyncOpenAI

from backend.config import ensure_valid_api_key, settings


BACKGROUND_INTERVAL_DEEP = 3
BACKGROUND_INTERVAL_LITE = 5
# 单次最多生成几条幕后事件
MAX_BACKGROUND_EVENTS_PER_RUN = 2

ALLOWED_FLAG_STATUS = ("未触发", "进行中", "已完成", "已失败")

BACKGROUND_SYSTEM_PROMPT = """你是 TRPG 低成本后台剧情推进器。你只负责世界在玩家视线之外发生的事。

规则：
1. 只基于输入中已有的暗线/旗标/重要人物推进，不要凭空创造与当前剧情无关的新主线。
2. 每次只输出一个 JSON 数组，数组元素 1-2 个。
3. 每个元素字段：
   "thread_key": 已有暗线的 key，或新暗线的 key
   "event": 一句话幕后进展
   "impact": 对世界或人物的影响（一句话，可为空字符串）
   "affected_npcs": 涉及 NPC 名数组
   "affected_locations": 涉及地点名数组
   "status": "未触发" / "进行中" / "已完成" / "已失败"
   "public_hint": 玩家可能听到的传闻或迹象；没有就填空字符串
4. 不要输出 Markdown、解释或多余文字。
"""


def _play_mode(state: Any) -> str:
    mode = (state.character_info or {}).get("play_mode", "deep")
    return mode if mode in ("lite", "deep") else "deep"


def _client(state: Any) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=ensure_valid_api_key(getattr(state, "api_key", None)),
        base_url=getattr(state, "base_url", None) or settings.LLM_BASE_URL,
    )


def _model(state: Any) -> str:
    return getattr(state, "model_name", None) or settings.LLM_MODEL_NAME


def _hidden_threads(state: Any) -> list[dict]:
    """汇总当前已知暗线：内存暗线 + 世界状态中隐藏旗标。"""
    mem = getattr(state, "memory", None)
    threads: dict[str, dict] = {}
    if mem is not None:
        for ht in getattr(mem, "hidden_threads", []) or []:
            key = str(ht.get("key", "")).strip()
            if key:
                threads[key] = dict(ht)
    ws = getattr(state, "world_state", None)
    if ws is not None:
        for f in getattr(ws, "plot_flags", []) or []:
            if not getattr(f, "visible", True):
                flag_data = {
                    "key": f.key,
                    "description": f.description,
                    "status": f.status,
                    "consequence": f.consequence,
                }
                if f.key in threads:
                    threads[f.key].update(flag_data)
                else:
                    threads[f.key] = flag_data
    return list(threads.values())


def should_run_background(state: Any) -> bool:
    """是否应该在本轮结束后触发后台推进。"""
    ws = getattr(state, "world_state", None)
    if ws is None:
        return False
    if getattr(state, "in_combat", False):
        return False
    interval = BACKGROUND_INTERVAL_LITE if _play_mode(state) == "lite" else BACKGROUND_INTERVAL_DEEP
    if interval <= 0 or ws.turn_count % interval != 0:
        return False
    # 没有可推进的暗线/大事件/重要人物时跳过，避免凭空消耗 token
    mem = getattr(state, "memory", None)
    active_mem_threads = False
    if mem is not None:
        active_mem_threads = any(
            h.get("status") in ("未触发", "进行中")
            for h in (getattr(mem, "hidden_threads", None) or [])
        ) or bool(getattr(mem, "major_events", None))
    active_flags = any(
        f.status in ("未触发", "进行中") for f in ws.plot_flags
    )
    has_threads = bool(
        active_mem_threads
        or active_flags
        or any(getattr(n, "importance", "minor") == "major" for n in ws.npcs)
    )
    return has_threads


def _extract_json_array(text: str) -> list[dict]:
    """从 LLM 输出中稳健提取 JSON 数组。"""
    text = (text or "").strip()
    if not text:
        return []
    # 去掉可能包裹的 ```json ... ```
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    # 直接找最外层 [...] 或 {...}
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        text = match.group(0)
    else:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            text = match.group(0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 尝试逐行解析容错：很多模型会输出 JSONL
        results = []
        for line in text.splitlines():
            line = line.strip().rstrip(",")
            if not line:
                continue
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    results.append(item)
            except json.JSONDecodeError:
                continue
        return results
    if isinstance(data, dict):
        # 兼容 {events: [...]} 包装
        for key in ("events", "background_events", "beats"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    return []
