"""知识库文本辅助：分词、查询分类与来源/正文清洗。

从 knowledge_base 拆出，供文档 CRUD 与检索 mixin 共用，避免循环导入。
"""

from __future__ import annotations

import hashlib
import re
from collections import OrderedDict


_TOKEN_CACHE: "OrderedDict[str, list[str]]" = OrderedDict()
_TOKEN_CACHE_MAX = 20000


def _tokenize_uncached(text: str) -> list[str]:
    """字符 bigram + jieba 分词混合，提升中文检索专业性与命中率。"""
    cleaned = re.sub(r"\s+", "", text.lower())
    if len(cleaned) <= 1:
        return [cleaned] if cleaned else []
    terms = [cleaned[i:i + 2] for i in range(len(cleaned) - 1)]
    try:
        import jieba
        words = [w for w in jieba.cut(cleaned) if len(w.strip()) > 1]
        terms.extend(words)
    except Exception:
        pass
    return terms


def _tokenize(text: str) -> list[str]:
    """带缓存的分词：同一分块在一次检索中会被 df/语料/tf-idf 三处复用。

    实测 10,579 个分块重复分词约 33 秒，是启动预热的主要成本。
    """
    key = hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()
    cached = _TOKEN_CACHE.get(key)
    if cached is not None:
        _TOKEN_CACHE.move_to_end(key)
        return cached
    terms = _tokenize_uncached(text)
    _TOKEN_CACHE[key] = terms
    if len(_TOKEN_CACHE) > _TOKEN_CACHE_MAX:
        _TOKEN_CACHE.popitem(last=False)
    return terms


def _safe_source(source: str) -> str:
    """去除知识库来源中的本地路径/文件名等敏感信息，统一为类别。"""
    source = source or ""
    if source.startswith("local:"):
        return "用户导入资料"
    if source.startswith("srd:"):
        return source
    if source.startswith("scenario:"):
        return "剧本"
    if source.startswith("extension:"):
        return "扩展包"
    if source.startswith("builtin"):
        return source
    if "\\" in source or "/" in source or source.lower().endswith((".pdf", ".docx", ".doc", ".txt", ".md", ".chm")):
        return "用户导入资料"
    return source or "未知来源"


def _safe_title(title: str) -> str:
    """去除标题中的本地文件名前缀，统一为可读名称。"""
    title = title or ""
    if title.startswith("本地资料："):
        return "导入资料"
    return title or "未命名知识"


def _clean_content(text: str) -> str:
    """清理知识库正文中的控制字符/不可打印字符/替换符乱码。"""
    if not text:
        return ""
    cleaned = "".join(ch for ch in text if ch.isprintable() or ch in "\n\r\t")
    # 大量 \ufffd 通常是二进制/编码损坏，直接清空
    if cleaned.count("\ufffd") / max(1, len(cleaned)) > 0.3:
        return ""
    return cleaned


def _is_garbled(text: str) -> bool:
    """判断文本是否已严重乱码（替换符+不可打印字符占比过高）。"""
    if not text.strip():
        return True
    repl = text.count("\ufffd")
    nonprint = sum(1 for ch in text if not ch.isprintable() and ch not in "\n\r\t")
    return (repl + nonprint) / max(1, len(text)) > 0.2


def _classify_query(query: str) -> str:
    """简单查询分类：规则/实体/通用，用于动态调整三路权重。"""
    q = query.lower()
    rule_kw = ["规则", "检定", "dc", "豁免", "伤害", "法术", "职业", "属性", "骰", "cr", "等级", "行动", "专注", "死亡", "回合"]
    entity_kw = ["谁", "在哪", "地点", "npc", "人物", "关系", "认识", "生物", "怪物", "boss", "城市", "地图", "线索"]
    rule_hits = sum(1 for k in rule_kw if k in q)
    entity_hits = sum(1 for k in entity_kw if k in q)
    if rule_hits > entity_hits:
        return "rule"
    if entity_hits > rule_hits:
        return "entity"
    return "general"


__all__ = [
    "_TOKEN_CACHE",
    "_TOKEN_CACHE_MAX",
    "_tokenize_uncached",
    "_tokenize",
    "_safe_source",
    "_safe_title",
    "_clean_content",
    "_is_garbled",
    "_classify_query",
]
