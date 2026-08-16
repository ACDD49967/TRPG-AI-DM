"""四次剧本质量评估脚本：DND5e / DND4e / COC 网络剧本 + LLM 自动生成。

用法：
  LLM_API_KEY=sk-xxx .venv/Scripts/python.exe scripts/eval_four_scenarios.py
"""

import asyncio
import html
import json
import os
import re
import urllib.request
from pathlib import Path

from backend.engine.game_systems import roll_coc_characteristics
from backend.main import generate_character
from backend.scenario_importer import (
    extract_text,
    generate_scenario_from_text,
    split_text,
)
from backend.schemas import GenerateAttributesRequest

API_KEY = os.environ.get("LLM_API_KEY", "")
MODEL = os.environ.get("LLM_MODEL_NAME", "deepseek-chat")
BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")
OUT_DIR = Path("eval_results")


def fetch(url: str, timeout: int = 30) -> bytes:
    print(f"[fetch] {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def strip_html(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


async def make_scenario(source_text: str, system: str, label: str, source_url: str, description: str = ""):
    print(f"\n===== 生成剧本: {label} ({system}) =====")
    chunks = split_text(source_text, mode="naive", chunk_size=900)
    result = await generate_scenario_from_text(
        source_text=source_text,
        chunks=chunks,
        title=f"[{label}] 自动改编",
        description=description or source_text[:200],
        tone="史诗奇幻" if system in ("dnd5e", "dnd4e") else "克苏鲁恐怖",
        system=system,
        character_name="测试角色",
        race="人类",
        char_class="战士" if system != "coc" else "记者",
        api_key=API_KEY,
        model_name=MODEL,
        base_url=BASE_URL,
        splitter="naive",
        target_score=75,
        max_revisions=1,
    )
    result["_label"] = label
    result["_source_url"] = source_url
    return result


async def make_background(result: dict, system: str, label: str):
    print(f"[background] {label}")
    if system == "coc":
        attrs = roll_coc_characteristics()
        race = "调查员"
        char_class = "记者"
    else:
        attrs = {"str": 14, "dex": 12, "con": 14, "int": 10, "wis": 12, "cha": 8}
        race = "人类"
        char_class = "战士"
    req = GenerateAttributesRequest(
        character_name="测试角色",
        gender="未指定",
        race=race,
        char_class=char_class,
        attributes=attrs,
        game_system=system,
        scenario_summary=result.get("summary", ""),
    )
    bg = await generate_character(req)
    return {
        "label": label,
        "system": system,
        "attributes": attrs,
        "backstory": bg.get("backstory", ""),
        "fallback": bg.get("fallback", False),
    }


async def main():
    if not API_KEY:
        raise SystemExit("缺少 LLM_API_KEY")
    os.makedirs(OUT_DIR, exist_ok=True)
    results = {}

    # 1) DND5e 网络剧本：The Delian Tomb (GitHub README)
    dnd5_url = "https://raw.githubusercontent.com/World-Smiths/the-delian-tomb/main/README.md"
    dnd5_text = fetch(dnd5_url).decode("utf-8", errors="replace")
    results["dnd5e_web"] = await make_scenario(dnd5_text, "dnd5e", "DND5e-网络", dnd5_url)

    # 2) DND4e 网络剧本：The Slaying Stone 讨论/剧情信息
    dnd4_url = "https://www.enworld.org/threads/dfs-the-slaying-stone-4e.315973/page-2"
    dnd4_html = fetch(dnd4_url, timeout=30)
    dnd4_text = strip_html(dnd4_html)
    results["dnd4e_web"] = await make_scenario(dnd4_text, "dnd4e", "DND4e-网络", dnd4_url)

    # 3) COC 网络剧本：The Haunting (HTML)
    coc_url = "https://cultistarmoury.org/the-haunting/"
    coc_html = fetch(coc_url, timeout=30)
    coc_text = strip_html(coc_html)
    results["coc_web"] = await make_scenario(coc_text, "coc", "COC-网络", coc_url)

    # 4) LLM 自动生成剧本（无网络来源）
    auto_desc = "一个被遗忘的边境小镇，最近所有孩子都开始做同一个噩梦；镇长秘密召唤冒险者调查。"
    results["llm_auto"] = await make_scenario(
        auto_desc, "dnd5e", "LLM自动生成", "local-llm", description=auto_desc
    )

    # 背景故事质量测试
    backgrounds = []
    for key, res in results.items():
        system = res.get("system", "dnd5e")
        bg = await make_background(res, system, key)
        backgrounds.append(bg)
    results["_backgrounds"] = backgrounds

    report_path = OUT_DIR / "eval_report.json"
    report_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[完成] 报告已写入 {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
