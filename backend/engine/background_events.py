"""低成本后台剧情推进器。

目标：
- 世界在玩家视线之外继续推进：暗线、重要人物、大事件的后续影响。
- 不占用玩家回合的叙事，不额外生成大段文本。
- 通过“低频触发 + 小 max_tokens + 精简 JSON”控制 token 消耗。
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from openai import AsyncOpenAI

from backend.config import ensure_valid_api_key, settings
from backend.engine.llm_utils import strip_refusal
from backend.engine.world_state import WorldState

# 每多少轮触发一次幕后推进（deep 更频繁，lite 更省 token）
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


def _apply_background_beat(state: Any, ws: WorldState, beat: dict) -> dict | None:
    """把一条幕后进展写入记忆与世界状态。返回规范化后的事件 dict。"""
    thread_key = str(beat.get("thread_key") or beat.get("key") or "").strip()
    event = str(beat.get("event") or "").strip()
    if not thread_key and not event:
        return None
    status = str(beat.get("status") or "进行中").strip()
    if status not in ALLOWED_FLAG_STATUS:
        status = "进行中"
    impact = str(beat.get("impact") or "").strip()
    public_hint = str(beat.get("public_hint") or "").strip()[:120]
    affected_npcs = [str(x).strip() for x in (beat.get("affected_npcs") or []) if str(x).strip()]
    affected_locations = [str(x).strip() for x in (beat.get("affected_locations") or []) if str(x).strip()]

    mem = getattr(state, "memory", None)
    if mem is not None:
        if thread_key:
            mem.update_hidden_thread(
                key=thread_key,
                status=status,
                progress=event,
                turn=ws.turn_count,
            )
            # 若刚创建，补全描述与关联
            existing = next((h for h in mem.hidden_threads if h.get("key") == thread_key), None)
            if existing and not existing.get("description"):
                existing["description"] = event
            if existing:
                for name in affected_npcs:
                    if name not in (existing.get("related_npcs") or []):
                        existing.setdefault("related_npcs", []).append(name)
                for loc in affected_locations:
                    if loc not in (existing.get("related_locations") or []):
                        existing.setdefault("related_locations", []).append(loc)
        if impact:
            for npc_name in affected_npcs:
                mem.add_character_impact(name=npc_name, impact=impact, event=event, turn=ws.turn_count)
            if not affected_npcs:
                mem.add_major_event(
                    title=thread_key or event[:20],
                    description=event,
                    impact=impact,
                    turn=ws.turn_count,
                    npcs=affected_npcs,
                    locations=affected_locations,
                )

    # 同步到世界状态旗标（暗线默认对玩家隐藏）
    if thread_key:
        ws.set_flag(
            key=thread_key,
            status=status,
            description=event,
            consequence=impact,
            visible=False,
        )

    event_entry = {
        "turn": ws.turn_count,
        "thread_key": thread_key,
        "event": event,
        "impact": impact,
        "affected_npcs": affected_npcs,
        "affected_locations": affected_locations,
        "public_hint": public_hint,
        "visible": bool(public_hint),
    }
    ws.add_background_event(event_entry)
    return event_entry


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


def _fallback_background_plot(state: Any) -> list[dict]:
    """无 LLM/解析失败时的兜底：推进第一条未完成暗线，不产生新内容。"""
    ws = getattr(state, "world_state", None)
    if ws is None:
        return []
    mem = getattr(state, "memory", None)
    threads = _hidden_threads(state)
    if not threads:
        return []
    target = None
    for t in threads:
        if t.get("status") in ("未触发", "进行中"):
            target = t
            break
    if target is None:
        return []
    key = target.get("key", "")
    status = "进行中" if target.get("status") == "未触发" else "进行中"
    event = f"{key}在暗中继续发展（第{ws.turn_count}轮）"
    beat = {
        "thread_key": key,
        "event": event,
        "impact": "",
        "affected_npcs": target.get("related_npcs", []) or [],
        "affected_locations": target.get("related_locations", []) or [],
        "status": status,
        "public_hint": "",
    }
    entry = _apply_background_beat(state, ws, beat)
    if mem is not None and entry:
        # 兜底只更新进度，不额外添加大事件
        mem.update_hidden_thread(key=key, status=status, progress=event, turn=ws.turn_count)
    return [entry] if entry else []


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
