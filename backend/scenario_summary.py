"""剧本总结：把世界大纲压成约 400 字的摘要（失败时用抽取式回退）。

从 `backend/scenario_generate.py` 拆出；那边保留从文本生成整本剧本的管道，
并再导出这里的名字（`scenario_importer` 门面的 import 不变）。
"""
from __future__ import annotations

import asyncio

import re
from typing import Any

from openai import AsyncOpenAI

from backend.engine.llm_utils import strip_refusal as _strip_refusal
from backend.engine.prompt_guard import sanitize_user_text


SUMMARY_PROMPT = """你是一位TRPG模组编辑。请为以下冒险剧本写一份**约400字（允许350-450字）的剧本总结**。

总结要求：
1. 概括世界观、核心冲突、主线三幕、关键NPC、主要地点与独特规则
2. 语言精炼、信息密度高，让新玩家读完后能快速理解这是一个怎样的冒险
3. 使用中文，不要使用Markdown标题、列表符号，直接输出一段连贯文字
4. 不要输出"本剧本""总结如下"等多余引导语

## 冒险大纲
{outline}

## 原始剧本片段（可能截断）
{source}
"""



def _fallback_summary(outline: str, max_chars: int = 450) -> str:
    """从大纲中提取结构化摘要：每个章节取标题+首句；无标题时取每段首句，避免直接截断。"""
    if re.search(r"^#+\s", outline, re.M):
        lines = outline.split("\n")
        parts: list[str] = []
        current_heading = ""
        seen_heading_content = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                current_heading = stripped.lstrip("#").strip()
                if current_heading and (not parts or parts[-1] != current_heading):
                    parts.append(current_heading)
                seen_heading_content = False
                continue
            if current_heading and not seen_heading_content:
                sentence = re.split(r"(?<=[。！？!?；;])", stripped)[0][:100].strip()
                if sentence:
                    parts.append(sentence)
                    seen_heading_content = True
            if len("；".join(parts)) >= max_chars:
                break
        fallback = "；".join(parts)
    else:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", outline) if p.strip()]
        parts = []
        for para in paragraphs:
            sentence = re.split(r"(?<=[。！？!?；;])", para)[0][:100].strip()
            if sentence:
                parts.append(sentence)
            if len("；".join(parts)) >= max_chars:
                break
        fallback = "；".join(parts)
    fallback = fallback or outline.strip().replace("#", "").replace("*", "")
    fallback = re.sub(r"\s+", " ", fallback).strip()
    return fallback[:max_chars] or "（暂无剧本总结）"



async def generate_summary(
    client: AsyncOpenAI,
    model: str,
    outline: str,
    source_text: str,
    max_chars: int = 450,
    token_callback=None,
    error_callback=None,
) -> str:
    """调用 LLM 生成剧本总结；失败时使用结构化降级摘要，而不是简单截断。

    第 2 次尝试显式禁用思考并放大预算：推理模型下 reasoning 与正文共享 max_tokens，
    长大纲场景推理容易吃满预算导致 content 为空（日志表现为“总结生成空响应”）。
    """
    source_text = sanitize_user_text(source_text)
    last_err = None
    for attempt in range(1, 3):
        # 首次预算实测：大纲 1.6 万字时推理约 2900 字（≈2000 token），
        # 原先 2000 的预算会被推理吃满导致正文为空；提高预算后同步上调。
        current_max_tokens = 6000 if attempt == 1 else 10000
        kwargs: dict[str, Any] = dict(
            model=model,
            messages=[
                {"role": "system", "content": "你是一位严谨的TRPG模组编辑，擅长写出高信息密度的中文剧本总结。"},
                {"role": "user", "content": SUMMARY_PROMPT.format(
                    outline=outline[:12000],
                    source=source_text[:4000],
                )},
            ],
            max_tokens=current_max_tokens,
            temperature=0.4,
            stream=attempt == 1,
        )
        if attempt > 1:
            # 重试时禁用思考，保证正文一定能拿到（不被 reasoning 挤空）
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        try:
            # 统一流式：超时只等待首个响应头，不会在长文本生成中途掐断
            resp = await asyncio.wait_for(
                client.chat.completions.create(**kwargs),
                timeout=120,
            )
            summary = ""
            finish = None
            reasoning_len = 0
            if attempt == 1:
                stream = resp
                while True:
                    try:
                        chunk = await asyncio.wait_for(stream.__anext__(), timeout=60)
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError:
                        print(f"[ScenarioImporter] 总结流式空闲超时(60s无新数据)")
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
                        summary += d.content
                        if token_callback is not None:
                            token_callback(d.content)
                    rc = getattr(d, "reasoning_content", None)
                    if rc:
                        reasoning_len += len(rc)
            else:
                choice = resp.choices[0]
                summary = choice.message.content or ""
                finish = choice.finish_reason
                reasoning_len = len(getattr(choice.message, "reasoning_content", None) or "")
            summary = _strip_refusal(summary)
            if len(summary) > max_chars * 1.4:
                summary = summary[:max_chars]
            if summary:
                return summary
            print(f"[ScenarioImporter] 总结生成第{attempt}次空响应 "
                  f"(finish={finish}, reasoning≈{reasoning_len}字, max_tokens={current_max_tokens})")
            raise RuntimeError("空响应")
        except Exception as e:
            last_err = str(e)
            print(f"[ScenarioImporter] 总结生成第{attempt}次失败: {e}")
        await asyncio.sleep(1)
    print(f"[ScenarioImporter] 总结生成最终失败: {last_err}，使用结构化降级摘要")
    if error_callback is not None:
        error_callback(last_err or "未知错误")
    return _fallback_summary(outline, max_chars)



# ═══════════════════════════════════════════════════════════════
# 从导入文本生成完整新剧本
# ═══════════════════════════════════════════════════════════════
