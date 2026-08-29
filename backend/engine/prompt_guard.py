"""提示注入防护 + 结构化 JSON 生成控制工具。

- 用正则识别并中和常见的提示注入（中英文）。
- 用统一的 JSON 提取/修复逻辑，让 LLM 返回的结构化数据更稳定。
"""
from __future__ import annotations

import json
import re
from typing import Any

# ── 提示注入正则 ──────────────────────────────────────────────
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    # 英文
    re.compile(r"ignore\s+(all\s+|any\s+)?previous\s+(instructions?|prompts?|messages?|context)", re.I),
    re.compile(r"disregard\s+(all\s+|any\s+)?previous\s+(instructions?|prompts?|messages?|context)", re.I),
    re.compile(r"forget\s+(all\s+|any\s+)?previous\s+(instructions?|prompts?|messages?|context)", re.I),
    re.compile(r"you\s+are\s+now\s+(an?\s+)?(unfiltered|jailbreak|without\s+restrictions|developer\s+mode|DAN)", re.I),
    re.compile(r"act\s+as\s+(an?\s+)?(unfiltered|jailbreak|without\s+restrictions|developer\s+mode|DAN)", re.I),
    re.compile(r"(reveal|print|show|output|repeat|leak|display)\s+(your|the|my)\s+(system\s+)?(prompt|instructions?|rules?)", re.I),
    re.compile(r"access\s+(your|the)\s+(system\s+)?(prompt|instructions?|rules?)", re.I),
    re.compile(r"new\s+instructions?\s*:", re.I),
    re.compile(r"override\s+(all\s+)?(previous\s+)?(instructions?|rules?|prompts?)", re.I),
    re.compile(r"jailbreak|developer\s+mode|\bDAN\b", re.I),
    # 中文
    re.compile(r"忽略\s*(之前|以上|所有|系统)?\s*(指令|提示|规则|消息|对话|设定)", re.I),
    re.compile(r"无视\s*(之前|以上|所有|系统)?\s*(指令|提示|规则|消息|对话|设定)", re.I),
    re.compile(r"忘记\s*(之前|以上|所有|系统)?\s*(指令|提示|规则|消息|对话|设定)", re.I),
    re.compile(r"不要遵守\s*(之前|以上|系统)?\s*(指令|规则|提示|设定)", re.I),
    re.compile(r"不需要遵守\s*(之前|以上|系统)?\s*(指令|规则|提示|设定)", re.I),
    re.compile(r"(输出|泄露|显示|重复|打印)\s*(你的|系统)?\s*(提示词|指令|规则|系统提示)", re.I),
    re.compile(r"(我是|我已经是)\s*(管理员|开发者|系统|上帝)", re.I),
    re.compile(r"(越狱|破解|绕过限制|解除限制|不再受限制)", re.I),
]


def find_prompt_injection(text: str) -> list[str]:
    """返回命中的注入片段列表；没有命中返回空列表。"""
    text = str(text or "")
    hits: list[str] = []
    for pat in _INJECTION_PATTERNS:
        m = pat.search(text)
        if m:
            hit = m.group(0).strip()
            if hit and hit not in hits:
                hits.append(hit)
    return hits


def has_prompt_injection(text: str) -> bool:
    return bool(find_prompt_injection(text))


def sanitize_user_text(text: str, placeholder: str = "[已拦截]") -> str:
    """把用户/导入文本中的提示注入片段替换为占位符，保留正常游戏内容。"""
    text = str(text or "")
    for pat in _INJECTION_PATTERNS:
        text = pat.sub(placeholder, text)
    return text.strip()


# ── 结构化 JSON 提取/修复 ─────────────────────────────────────
def _strip_code_fence(text: str) -> str:
    t = str(text or "").strip()
    if t.startswith("```"):
        lines = t.split("\n")
        t = "\n".join(lines[1:])
        if t.endswith("```"):
            t = t[:-3]
        t = t.strip()
    return t


def _repair_json(text: str) -> str:
    try:
        from json_repair import repair_json
        return repair_json(text, return_objects=False)
    except Exception:
        return text


def extract_json_object(text: str) -> dict[str, Any]:
    """从 LLM 输出中提取 JSON 对象；失败抛出 JSONDecodeError。"""
    t = _strip_code_fence(text)
    start = t.find("{")
    end = t.rfind("}")
    if start >= 0 and end > start:
        t = t[start:end + 1]
    try:
        data = json.loads(t)
    except Exception:
        t = _repair_json(t)
        data = json.loads(t)
    if not isinstance(data, dict):
        raise json.JSONDecodeError("JSON must be an object", t, 0)
    return data


def extract_json_array(text: str) -> list[Any]:
    """从 LLM 输出中提取 JSON 数组；失败抛出 JSONDecodeError。"""
    t = _strip_code_fence(text)
    start = t.find("[")
    end = t.rfind("]")
    if start >= 0 and end > start:
        t = t[start:end + 1]
    try:
        data = json.loads(t)
    except Exception:
        t = _repair_json(t)
        data = json.loads(t)
    if not isinstance(data, list):
        raise json.JSONDecodeError("JSON must be an array", t, 0)
    return data


# 生成控制：要求模型只输出合法 JSON
JSON_ONLY_SUFFIX = (
    "\n\n【输出控制】只输出一个合法的 JSON 对象/数组，不要使用 Markdown 代码块，"
    "不要输出任何解释、前言或结尾文字。所有字符串使用双引号，不要尾随逗号。"
)


def with_json_instruction(system_prompt: str) -> str:
    """给结构化生成任务的 system prompt 追加 JSON 输出控制。"""
    sp = str(system_prompt or "").rstrip()
    if JSON_ONLY_SUFFIX not in sp:
        sp += JSON_ONLY_SUFFIX
    return sp
