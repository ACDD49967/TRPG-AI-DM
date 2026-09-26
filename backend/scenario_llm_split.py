"""LLM 智能切分：提示词、分段调用、结果解析与失败回退。

从 backend.scenario_importer 拆出。
"""
from __future__ import annotations

import asyncio
import io
import json
import math
import os
import re
import subprocess
from typing import Any

from openai import AsyncOpenAI

from backend.config import ensure_valid_api_key, settings
from backend.engine.game_systems import detect_game_system
from backend.engine.llm_utils import strip_refusal as _strip_refusal
from backend.engine.prompt_guard import extract_json_array, extract_json_object, sanitize_user_text
from backend.engine.rag_utils import cosine as dense_cosine, embed_text
from backend.logging_utils import get_logger
from backend.scenario_split import (
    _join_chunk, _merge_vec, split_text_naive,
)



LLM_SPLIT_PROMPT = """你是 TRPG 模组编辑。请把以下剧本/知识文本智能切分为若干逻辑完整、语义连贯的片段。
要求：
1. 按场景、章节、主题、事件边界切分，不要生硬按字数截断。
2. 每段 600-1200 字；若原文极长可多分段。
3. 保留标题、专有名词、规则关键词；不要改写内容。
4. 只输出一个 JSON 对象，格式必须严格为：{{"chunks": ["片段1", "片段2", ...]}}
5. 不要输出 Markdown 代码块、不要解释、不要其他文字。

文本：
{text}
"""


# 单次送入 LLM 的文本长度。切分要求模型把原文重输出为 JSON，
# 过长的输入会导致输出远超 max_tokens（实测 24000 字 → 推理吃满 8000 预算、正文为空）。
# 提高输出预算后单段可放宽到 10000 字（约 6500 token 输出），仍留有余量。
LLM_SPLIT_CHUNK_CHARS = 10000

# 最多调用次数：超长剧本其余部分走本地递归切分，避免产生海量请求把等待时间拖成几十分钟。
LLM_SPLIT_MAX_CALLS = 6

# 单段切分的输出预算（与剧本创建同样受 settings.LLM_MAX_OUTPUT_TOKENS 约束）
LLM_SPLIT_MAX_TOKENS = 16000



def _split_for_llm(text: str, limit: int = LLM_SPLIT_CHUNK_CHARS) -> list[str]:
    """按段落边界把文本切成不超过 limit 字的片段，供逐段 LLM 切分。"""
    segments: list[str] = []
    buf = ""
    for part in re.split(r"(\n\s*\n)", text):
        if buf.strip() and len(buf) + len(part) > limit:
            segments.append(buf)
            buf = ""
        buf += part
        # 单个超长段落（无换行的整段文本）：硬切，避免单段撑爆预算
        while len(buf) > limit * 2:
            segments.append(buf[:limit])
            buf = buf[limit:]
    if buf.strip():
        segments.append(buf)
    return [s for s in segments if s.strip()]



def _parse_split_payload(content: str) -> list[str]:
    """从 LLM 输出中解析 {"chunks":[...]}；兼容旧版直接返回数组，失败返回空列表。"""
    data = None
    try:
        obj = extract_json_object(content)
        data = obj.get("chunks") or obj.get("segments") or obj.get("data") or []
    except Exception:
        try:
            data = extract_json_array(content)
        except Exception:
            data = None
    if not isinstance(data, list):
        return []
    chunks: list[str] = []
    for x in data:
        text = str(x.get("content") if isinstance(x, dict) else x).strip()
        if text:
            chunks.append(text)
    return chunks



async def _llm_split_segment(
    client: AsyncOpenAI,
    model: str,
    segment: str,
    index: int = 1,
    total: int = 1,
) -> list[str] | None:
    """对单个片段调用 LLM 语义切分；返回 None 表示失败（由上层回退本地切分）。

    切分是确定性的结构化任务：显式禁用思考，避免推理占满 max_tokens 导致正文为空。
    """
    prompt = LLM_SPLIT_PROMPT.format(text=segment)
    # thinking 参数并非所有 OpenAI 兼容网关都支持，失败后自动去掉该参数重试
    attempts = [
        {"json_mode": True, "disabled": True},
        {"json_mode": False, "disabled": True},
        {"json_mode": False, "disabled": False},
    ]
    for attempt, plan in enumerate(attempts, 1):
        try:
            kwargs: dict[str, Any] = dict(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=LLM_SPLIT_MAX_TOKENS, temperature=0.1, stream=True,
            )
            if plan["json_mode"]:
                kwargs["response_format"] = {"type": "json_object"}
            if plan["disabled"]:
                kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
            stream = await asyncio.wait_for(
                client.chat.completions.create(**kwargs), timeout=120,
            )
            content = ""
            finish = None
            reasoning_len = 0
            while True:
                try:
                    chunk = await asyncio.wait_for(stream.__anext__(), timeout=60)
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError:
                    print("[ScenarioImporter] LLM切分流式空闲超时(60s无新数据)")
                    raise RuntimeError("流式响应空闲超时")
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                if choice.finish_reason:
                    finish = choice.finish_reason
                d = choice.delta
                if d is None:
                    continue
                if d.content:
                    content += d.content
                rc = getattr(d, "reasoning_content", None)
                if rc:
                    reasoning_len += len(rc)
            content = content.strip()
            if content:
                chunks = _parse_split_payload(content)
                if chunks:
                    return chunks
                print(f"[ScenarioImporter] 第{index}/{total}段切分结果无法解析 (finish={finish})")
            else:
                print(f"[ScenarioImporter] 第{index}/{total}段切分为空响应 "
                      f"(finish={finish}, reasoning≈{reasoning_len}字, max_tokens={LLM_SPLIT_MAX_TOKENS})")
        except Exception as e:
            print(f"[ScenarioImporter] 第{index}/{total}段切分第{attempt}次失败: {e}")
        if attempt < len(attempts):
            await asyncio.sleep(1)
    return None



async def llm_split_text(
    text: str,
    api_key: str | None = None,
    model_name: str | None = None,
    base_url: str | None = None,
    thinking_strength: str = "medium",
    progress_callback=None,
) -> list[str]:
    """使用 LLM 智能切分文本；单段失败时该段回退本地切分，不整体失败。

    实现要点（空响应排查结论）：
    - 切分要求模型把原文重输出为 JSON，输入越长输出越长；配合推理模型的 reasoning
      很容易超过 max_tokens，表现为 finish_reason=length 且 content 为空。
      因此按 LLM_SPLIT_CHUNK_CHARS 分段逐块切分，并显式禁用思考。
    - 超出 LLM_SPLIT_MAX_CALLS 的尾部使用本地递归切分，避免超长剧本等待失控。
    """
    from backend.config import ensure_valid_api_key, settings
    api_key = ensure_valid_api_key(api_key or settings.LLM_API_KEY)
    base_url = base_url or settings.LLM_BASE_URL
    model = model_name or settings.LLM_MODEL_NAME
    if not model:
        raise ValueError("请提供模型名称")
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    text = sanitize_user_text(text)

    segments = _split_for_llm(text)
    head = segments[:LLM_SPLIT_MAX_CALLS]
    tail = segments[LLM_SPLIT_MAX_CALLS:]
    if progress_callback:
        progress_callback("LLM 智能切分", 5,
                          f"共 {len(segments)} 段，前 {len(head)} 段使用 LLM 语义切分...")

    results: list[str] = []
    failed = 0
    for i, seg in enumerate(head, 1):
        if progress_callback:
            progress_callback("LLM 智能切分", 5, f"正在用 LLM 切分第 {i}/{len(head)} 段...")
        chunks = await _llm_split_segment(client, model, seg, i, len(head))
        if chunks:
            results.extend(chunks)
        else:
            failed += 1
            results.extend(split_text_naive(seg, chunk_size=900))
    for seg in tail:
        results.extend(split_text_naive(seg, chunk_size=900))
    if progress_callback and (failed or tail):
        progress_callback("LLM 切分完成", 8,
                          f"{failed} 段 LLM 切分失败、{len(tail)} 段超出调用上限，已回退本地切分")

    results = [c.strip() for c in results if c.strip()]
    return results or split_text_naive(text, chunk_size=900)
