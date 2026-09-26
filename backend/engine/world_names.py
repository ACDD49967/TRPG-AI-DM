"""NPC/地点/场景文本归一化：去掉注解、占位词与 NPC 自动建档噪音。"""
from __future__ import annotations

import re
from typing import Any

_SCENE_TEXT_LIMITS = {"current_location": 40, "current_time": 24, "weather": 24, "atmosphere": 80}

_SCENE_STOP_CHARS = "。！？!?\n；;"

_NPC_NAME_STOP_CHARS = "（(【[，,；;：:、—－-"

_SCENE_MAX_VISIBLE_NPCS = 8

_EMPTY_NPC_TOKENS = {"", "无", "无人", "没有", "null", "none", "玩家", "你们"}

def clean_scene_text(value: Any, limit: int) -> str:
    """把模型输出的散文裁剪成适合状态栏的单句短文本。"""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""
    for char in _SCENE_STOP_CHARS:
        idx = text.find(char)
        if idx > 0:
            text = text[:idx].strip()
    if len(text) > limit:
        text = text[:limit].rstrip()
    return text

def _cut_annotation(text: str, extra_chars: str = "") -> str:
    """截断首个注解符号，保留主体（「黄昏（短休进行中）」→「黄昏」）。"""
    for char in "（(【[" + extra_chars:
        idx = text.find(char)
        if idx > 0:
            text = text[:idx].strip()
    return text

def clean_npc_name(value: Any) -> str:
    """去掉「地精斥候（灌木丛后未现身）」这类注解，只保留 NPC 名。"""
    text = re.sub(r"\s+", " ", str(value or "")).strip().strip("“”\"'")
    for char in _NPC_NAME_STOP_CHARS:
        idx = text.find(char)
        if idx > 0:
            text = text[:idx].strip()
    return text.strip()

def clean_location_name(value: Any) -> str:
    """地点名同样只保留主体：「村外小径（地精斥候交战处）」→「村外小径」。

    地点在笔记/地图中按名称匹配，带注解会让同一地点分裂成多个条目。
    """
    text = clean_scene_text(value, _SCENE_TEXT_LIMITS["current_location"])
    if not text:
        return ""
    return _cut_annotation(text, "，,；;")
