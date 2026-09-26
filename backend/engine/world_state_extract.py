"""结构化提取结果的校验与统计：剧情旗标回填、状态校验、程序化评分、标题去重。

从 backend.engine.world_builder 拆出。
"""
from __future__ import annotations

import json
import re
from typing import Any

from openai import AsyncOpenAI

from backend.engine.prompt_guard import extract_json_object
from backend.engine.world_llm import _llm
from backend.engine.world_prompts import PLOT_FLAGS_ONLY_PROMPT

def _needs_plot_flag_backfill(data: dict) -> bool:
    """提取结果是否疑似被输出上限截断。

    JSON 被截断时排在末尾的 plot_flags 会整段丢失，但“空数组”能通过字段校验，
    不会触发修正循环，因此用「有 NPC/地点却一条旗标都没有」作为疑似截断信号。
    """
    if not isinstance(data, dict):
        return False
    return bool(not data.get("plot_flags") and (data.get("npcs") or data.get("locations")))



async def _extract_plot_flags(client: AsyncOpenAI, model: str, outline: str,
                              thinking_strength: str = "medium",
                              token_callback=None, error_callback=None) -> list[dict]:
    """只提取剧情旗标的精简回退调用。

    结构化提取要求输出一个巨大的 JSON（NPC 含属性/技能/装备等完整字段），
    输出被上限截断时排在末尾的 plot_flags 会整段丢失；这里用短 prompt + 小输出补一次。
    """
    result = await _llm(client, model,
        "你是TRPG剧情结构抽取员。只返回JSON。",
        PLOT_FLAGS_ONLY_PROMPT.format(outline=outline[:20000]),
        max_tokens=6000, temp=0.2, timeout=180, thinking_strength=thinking_strength,
        token_callback=token_callback, error_callback=error_callback,
        disable_thinking=True)
    if not result:
        return []
    try:
        data = _extract_json(result)
    except Exception:
        return []
    flags = data.get("plot_flags") if isinstance(data, dict) else None
    return flags if isinstance(flags, list) else []



def _validate_extracted_state(data: dict) -> list[str]:
    """严格校验专业AGENT提取出的结构化字段，返回错误列表。"""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["提取结果不是JSON对象"]
    for key in ("npcs", "locations", "plot_flags"):
        val = data.get(key)
        if val is None:
            continue
        if not isinstance(val, list):
            errors.append(f"{key} 必须是数组")
            continue
        for i, item in enumerate(val):
            if not isinstance(item, dict):
                errors.append(f"{key}[{i}] 必须是对象")
                continue
            if key == "npcs":
                if not str(item.get("name", "")).strip():
                    errors.append(f"npcs[{i}] 缺少 name")
                if item.get("level") is not None and not isinstance(item.get("level"), int):
                    errors.append(f"npcs[{i}].level 必须是整数")
                if item.get("ac") is not None and not isinstance(item.get("ac"), int):
                    errors.append(f"npcs[{i}].ac 必须是整数")
                if item.get("hp") is not None and not isinstance(item.get("hp"), int):
                    errors.append(f"npcs[{i}].hp 必须是整数")
                attrs = item.get("attributes")
                if attrs is not None and not isinstance(attrs, dict):
                    errors.append(f"npcs[{i}].attributes 必须是对象")
            elif key == "locations":
                if not str(item.get("name", "")).strip():
                    errors.append(f"locations[{i}] 缺少 name")
            elif key == "plot_flags":
                if not str(item.get("key", "")).strip():
                    errors.append(f"plot_flags[{i}] 缺少 key")
                status = item.get("status")
                if status not in (None, "未触发", "进行中", "已完成", "已失败"):
                    errors.append(f"plot_flags[{i}].status 非法: {status}")
    return errors



def _programmatic_score(outline: str, ws) -> int:
    """基于剧本结构完整性的程序化评分，避免 LLM 稳定输出同一分数。"""
    score = 0
    if len(outline) >= 1000:
        score += 10
    if len(outline) >= 3000:
        score += 10
    if len(outline) >= 5000:
        score += 5
    if re.search(r"第[一二三]幕|第一幕|第二幕|第三幕", outline):
        score += 20
    if re.search(r"^#|^##", outline, re.M):
        score += 5
    npc_count = len(ws.npcs)
    loc_count = len(ws.locations)
    flag_count = len(ws.plot_flags)
    score += min(npc_count, 5) * 3
    score += min(loc_count, 5) * 2
    score += min(flag_count, 5) * 2
    if ws.world_rules:
        score += 5
    if npc_count >= 3:
        score += 5
    if loc_count >= 3:
        score += 5
    if flag_count >= 5:
        score += 5
    return min(100, score)



def _dedupe_headings(text: str) -> str:
    """合并后处理：去除连续/重复出现的相同 Markdown 标题。"""
    seen: set[str] = set()
    out: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#") and stripped in seen:
            continue
        if stripped.startswith("#"):
            seen.add(stripped)
        out.append(line)
    return "\n".join(out)



def _extract_json(text: str) -> dict:
    """从可能含有markdown包裹的文本中提取JSON（统一走 prompt_guard 修复逻辑）。"""
    return extract_json_object(text)
