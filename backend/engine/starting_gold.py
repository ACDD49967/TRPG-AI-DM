"""DM 根据剧本大纲、角色背景与财宝规则生成起始金币。"""
from __future__ import annotations

import asyncio
import json
import re

from openai import AsyncOpenAI

from backend.config import ensure_valid_api_key, settings
from backend.engine.game_systems import get_starting_gold

STARTING_GOLD_PROMPT = """你是TRPG主持人。请严格阅读以下D&D 5e起始财富规则，然后根据剧本大纲与角色背景，为这位新角色生成**合理且符合角色身份**的起始金币。

## 财宝/起始财富规则（D&D 5e 官方）
- 起始装备通常由职业背景决定，也可用起始财富替代：
  - 战士/圣武士/游侠/游荡者/吟游诗人/邪术师：5d4×10 GP（约50-200）
  - 野蛮人：2d4×10 GP（约20-80）
  - 武僧/德鲁伊：5d4 GP（约5-20）
  - 牧师/法师/术士：2d4×10 GP（约20-80）
- 背景可能提供额外财富（如贵族、骑士、商人）。
- 金币必须符合角色身份与剧本经济水平：平民 0-20，冒险者 20-200，富裕贵族/商人 200-1000+，不得随意给到上万。

## 剧本大纲
{outline}

## 角色背景
{backstory}

## 角色职业
{char_class}

## 输出要求
只输出 JSON 对象，不要 Markdown 代码块，不要解释：
{{"gold": 整数, "reason": "一句话理由"}}
"""


def _extract_gold(text: str) -> int | None:
    if not text:
        return None
    m = re.search(r'"gold"\s*:\s*(\d+)', text)
    if m:
        return int(m.group(1))
    return None


async def generate_starting_gold(
    api_key: str | None,
    model_name: str | None,
    base_url: str | None,
    game_system: str,
    char_class: str,
    outline: str = "",
    backstory: str = "",
) -> int:
    """调用 LLM 按财宝规则生成起始金币；失败时回退到职业默认值。"""
    fallback = get_starting_gold(game_system, char_class)
    if game_system != "dnd5e":
        # 4e/COC/custom 暂不强制 LLM，直接使用规则默认
        return fallback
    try:
        api_key = ensure_valid_api_key(api_key or settings.LLM_API_KEY)
        model = model_name or settings.LLM_MODEL_NAME
        if not model:
            return fallback
        client = AsyncOpenAI(api_key=api_key, base_url=base_url or settings.LLM_BASE_URL)
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一位熟悉D&D财宝规则的严谨TRPG主持人。"},
                    {"role": "user", "content": STARTING_GOLD_PROMPT.format(
                        outline=(outline or "暂无")[:3000],
                        backstory=(backstory or "暂无")[:1500],
                        char_class=char_class or "战士",
                    )},
                ],
                max_tokens=300,
                temperature=0.5,
            ),
            timeout=45,
        )
        gold = _extract_gold(resp.choices[0].message.content or "")
        if gold is not None and 0 <= gold <= 100000:
            return gold
    except Exception as e:
        print(f"[StartingGold] LLM生成失败，使用职业默认值: {e}")
    return fallback
