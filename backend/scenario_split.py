"""剧本切分：朴素切分、语义切分（字符 n-gram 相似度）与递归切分。

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
from backend.scenario_text_io import normalize_text



def split_text_naive(text: str, chunk_size: int = 900, overlap: int = 100) -> list[str]:
    """按段落和字数切分：保留标题完整性，避免 overlap 截断标题。"""
    text = normalize_text(text)
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        # Markdown 标题永远作为新块起点，防止 overlap 截断标题
        if para.startswith("#") and current:
            chunks.append(current)
            current = para
            continue
        # 超长段落先按 chunk_size 硬切，带 overlap
        while len(para) > chunk_size:
            if current:
                chunks.append(current)
                current = current[-overlap:] if overlap else ""
            chunks.append(para[:chunk_size])
            para = para[chunk_size - overlap:] if overlap else para[chunk_size:]
        # 合并到当前块
        if not current:
            current = para
        elif len(current) + len(para) + 1 <= chunk_size:
            current = f"{current}\n\n{para}".strip()
        else:
            chunks.append(current)
            current = current[-overlap:] if overlap else ""
            current = f"{current}\n\n{para}".strip() if current else para
    if current.strip():
        chunks.append(current.strip())
    return [c for c in chunks if c.strip()]



# ── 语义切分（纯 Python 实现，无需外部 embedding 服务） ──

def _char_ngrams(text: str, n: int = 2) -> list[str]:
    """提取字符 n-gram；中文按字，英文按词边界弱化。"""
    cleaned = re.sub(r"\s+", "", text.lower())
    if len(cleaned) <= n:
        return [cleaned] if cleaned else []
    return [cleaned[i:i + n] for i in range(len(cleaned) - n + 1)]



def _vec(text: str) -> dict[str, int]:
    vec: dict[str, int] = {}
    for gram in _char_ngrams(text):
        vec[gram] = vec.get(gram, 0) + 1
    # jieba 中文分词补充语义单元
    try:
        import jieba
        for word in jieba.cut(text):
            w = word.strip()
            if len(w) > 1:
                vec[w] = vec.get(w, 0) + 1
    except Exception:
        pass
    return vec



def _cosine(a: dict[str, int], b: dict[str, int]) -> float:
    if not a or not b:
        return 0.0
    dot = 0
    for k, v in a.items():
        if k in b:
            dot += v * b[k]
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)



def _merge_vec(base: dict[str, int], other: dict[str, int]) -> dict[str, int]:
    merged = dict(base)
    for k, v in other.items():
        merged[k] = merged.get(k, 0) + v
    return merged



def _join_chunk(sentences: list[str]) -> str:
    """按语言习惯拼接句子：中文无空格，英文/混合文本用空格分隔。"""
    if any(re.search(r"[\u4e00-\u9fff]", s) for s in sentences):
        return "".join(sentences)
    return " ".join(sentences)



def split_text_semantic(
    text: str,
    max_chunk_size: int = 1200,
    min_chunk_size: int = 400,
    similarity_threshold: float = 0.30,
) -> list[str]:
    """基于相邻句子的字符 n-gram 相似度进行语义切分。

    句子在主题发生明显变化（相似度低于阈值）时断开，且保证块长在
    [min_chunk_size, max_chunk_size] 附近；不会产生无意义的小碎片。
    """
    text = normalize_text(text)
    if not text:
        return []

    # 先按段落粗分，段内再按句子切，保留标点
    raw_sentences: list[str] = []
    TITLE_BREAK = "\u0000TITLE_BREAK\u0000"
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        # Markdown 标题强制作为切分边界
        if para.startswith("#"):
            raw_sentences.append(TITLE_BREAK)
        sentences = re.split(r"(?<=[。！？；;])|(?<=[.!?])\s+|\n", para)
        for s in sentences:
            s = s.strip()
            if s:
                raw_sentences.append(s)

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    current_emb: list[float] | None = None
    current_count = 0

    def flush():
        nonlocal current, current_len, current_emb, current_count
        if current:
            chunks.append(_join_chunk(current))
        current = []
        current_len = 0
        current_emb = None
        current_count = 0

    for sent in raw_sentences:
        if sent == TITLE_BREAK:
            flush()
            continue
        emb = embed_text(sent)
        if current and current_len >= min_chunk_size and current_emb:
            mean = [v / current_count for v in current_emb]
            sim = dense_cosine(mean, emb)
            if sim < similarity_threshold or current_len + len(sent) > max_chunk_size:
                flush()
        current.append(sent)
        current_len += len(sent)
        if current_emb is None:
            current_emb = list(emb)
            current_count = 1
        else:
            for i, v in enumerate(emb):
                if i < len(current_emb):
                    current_emb[i] += v
            current_count += 1

    flush()
    # 极长块保护：语义切分结果中若仍有超过 max_chunk_size 的块，用硬切补齐
    final: list[str] = []
    for chunk in chunks:
        while len(chunk) > max_chunk_size * 1.5:
            final.append(chunk[:max_chunk_size])
            chunk = chunk[max_chunk_size - 100:]
        if chunk:
            final.append(chunk)
    return [c.strip() for c in final if c.strip()]



def split_text_recursive(text: str, chunk_size: int = 900, overlap: int = 150) -> list[str]:
    """快速递归切分：按段落/标题/字数切分，带 overlap，不依赖 LLM。"""
    return split_text_naive(text, chunk_size=chunk_size, overlap=overlap)



def split_text(text: str, mode: str = "naive", chunk_size: int = 900) -> list[str]:
    """对外切分入口。mode: naive | recursive | semantic | llm（llm 需走异步 llm_split_text）"""
    if mode == "semantic":
        return split_text_semantic(text, max_chunk_size=max(600, chunk_size))
    if mode == "recursive":
        return split_text_recursive(text, chunk_size=chunk_size)
    return split_text_naive(text, chunk_size=chunk_size)
