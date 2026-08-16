"""剧本导入模块的基础测试。"""

from backend.engine.game_systems import detect_game_system, get_dnd4_derived, get_dnd5_derived
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


def test_detect_game_system():
    assert detect_game_system("调查员在古宅中发现理智值下降") == "coc"
    assert detect_game_system("D&D 4e 威能与回复力") == "dnd4e"
    assert detect_game_system("5e 法术位与死亡豁免") == "dnd5e"
    assert detect_game_system("完全自定义的蒸汽朋克规则") == "custom"


def test_dnd4_derived_formula():
    d = get_dnd4_derived("战士", {"con": 14})
    # 战士 1 级 HP = 15 + 体质值 = 29；回复力 = 9 + 体质调整(+2) = 11
    assert d["max_hp"] == 29
    assert d["healing_surges"] == 11
    assert d["surge_value"] == 7  # 29 // 4


def test_dnd5_derived_formula():
    d = get_dnd5_derived("战士", {"con": 14}, level=1)
    # 战士 1 级 HP = d10 最大值 10 + 体质调整(+2) = 12
    assert d["max_hp"] == 12
    assert d["hit_die"] == "1d10"
