"""长期记忆检索打分：分词、词法命中、时间衰减与向量余弦。

从 backend/long_term_memory 拆出；这些函数只依赖文本与向量，不碰存储。
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from typing import Any

def _json_list(value: Any) -> str:
    if isinstance(value, str):
        items = [x.strip() for x in re.split(r"[,，、;；]", value) if x.strip()]
    elif isinstance(value, (list, tuple, set)):
        items = [str(x).strip() for x in value if str(x).strip()]
    else:
        items = []
    return json.dumps(list(dict.fromkeys(items)), ensure_ascii=False)


def _loads(value: str | None, default: Any) -> Any:
    try:
        data = json.loads(value or "")
        return data if isinstance(data, type(default)) else default
    except Exception:
        return default


def _tokenize(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", "", str(text or "").lower())
    if not cleaned:
        return []
    terms = [cleaned[i:i + 2] for i in range(len(cleaned) - 1)]
    try:
        import jieba
        terms.extend(w for w in jieba.cut(cleaned) if len(w.strip()) > 1)
    except Exception:
        pass
    return terms


def _lexical_score(query_tokens: list[str], content: str) -> float:
    if not query_tokens:
        return 0.0
    c = Counter(_tokenize(content))
    if not c:
        return 0.0
    hit = sum(min(q, c.get(t, 0)) for t, q in Counter(query_tokens).items())
    return hit / (sum(c.values()) ** 0.5 + 1e-6)


def _recency_score(updated_at: str) -> float:
    try:
        dt = datetime.fromisoformat(updated_at)
        days = max(0.0, (datetime.now() - dt).total_seconds() / 86400.0)
    except Exception:
        return 0.5
    return 1.0 / (1.0 + days / 30.0)


def _embed(text: str) -> list[float]:
    try:
        from backend.engine.rag_utils import embed_text
        return embed_text(text)
    except Exception:
        return []


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    try:
        from backend.engine.rag_utils import cosine
        return max(0.0, float(cosine(a, b)))
    except Exception:
        return 0.0


def _memory_id(username: str, memory_type: str, content: str) -> str:
    raw = f"{username}|{memory_type}|{content.strip()}"
    return hashlib.md5(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]
