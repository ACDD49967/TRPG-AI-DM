"""RAG 工具：本地稠密向量（哈希嵌入）与相似度计算。

- 零外部依赖、零 API 成本、确定性输出；
- 使用 jieba 分词 + 字符 trigram 哈希到固定维度，L2 归一化；
- 用于知识库向量检索与语义切分的句向量。
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

_DIM = 512


def _tokens(text: str) -> list[str]:
    text = str(text or "").lower()
    cleaned = re.sub(r"\s+", "", text)
    out: list[str] = []
    # 字符 trigram（对中文/混排稳健）
    for i in range(max(0, len(cleaned) - 2)):
        out.append(cleaned[i:i + 3])
    try:
        import jieba
        out.extend(w for w in jieba.cut(cleaned) if len(w.strip()) > 1)
    except Exception:
        pass
    return out


def _bucket(token: str) -> int:
    h = hashlib.md5(token.encode("utf-8", errors="ignore")).hexdigest()
    return int(h[:8], 16) % _DIM


def embed_text(text: str) -> list[float]:
    """本地哈希嵌入：固定 512 维，L2 归一化。"""
    vec = [0.0] * _DIM
    toks = _tokens(text)
    if not toks:
        return vec
    counts = Counter(toks)
    max_tf = max(counts.values()) or 1
    for tok, tf in counts.items():
        idx = _bucket(tok)
        # sublinear TF + 位置无关哈希
        vec[idx] += (1 + math.log(tf)) / max_tf
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed_texts(texts: list[str]) -> list[list[float]]:
    return [embed_text(t) for t in texts]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    for x, y in zip(a, b):
        dot += x * y
    return dot  # 均已 L2 归一化
