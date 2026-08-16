"""剧本导入模块的基础测试。"""

from backend.scenario_importer import (
    extract_text,
    split_text_naive,
    split_text_semantic,
)


def test_extract_text_txt():
    content = "第一章 风起\n\n小镇在晨雾中醒来。".encode("utf-8")
    text = extract_text("sample.txt", content)
    assert "小镇" in text


def test_split_text_naive_respects_chunk_size():
    text = "段落一。\n\n段落二。\n\n段落三。\n\n段落四。"
    chunks = split_text_naive(text, chunk_size=20, overlap=0)
    assert len(chunks) >= 2
    assert all(c.strip() for c in chunks)


def test_split_text_semantic_returns_nonempty():
    text = (
        "第一章 风起。小镇在晨雾中醒来。铁匠铺的锤声敲碎了寂静。"
        "第二章 暗流。领主在城堡里密谋。商人们在酒馆低声交谈。"
    )
    chunks = split_text_semantic(text, max_chunk_size=120, min_chunk_size=30)
    assert len(chunks) >= 1
    assert all(c.strip() for c in chunks)
