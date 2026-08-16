"""从克苏鲁公社/苹果园/TRPGrepo 拉取中文剧本样本，测试切分与自动生成差距。

用法：
  LLM_API_KEY=sk-xxx PYTHONPATH=. .venv/Scripts/python.exe scripts/test_real_chinese_sources.py
"""

import asyncio
import json
import os
import urllib.request
from pathlib import Path

from backend.engine.game_systems import detect_game_system
from backend.scenario_importer import extract_text, generate_scenario_from_text, split_text
from scripts.eval_four_scenarios import strip_html

API_KEY = os.environ.get("LLM_API_KEY", "")
MODEL = os.environ.get("LLM_MODEL_NAME", "deepseek-chat")
BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")
OUT_DIR = Path("eval_results")
OUT_DIR.mkdir(exist_ok=True)


def fetch(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def source_metadata(url: str):
    html = fetch(url, timeout=30)
    text = strip_html(html)
    return text


async def generate_case(label: str, source_url: str, text: str):
    print(f"\n===== 生成: {label} =====")
    chunks = split_text(text, mode="naive", chunk_size=900)
    system = detect_game_system(text, label)
    result = await generate_scenario_from_text(
        source_text=text,
        chunks=chunks,
        title=f"[{label}] 自动改编",
        description=text[:200],
        tone="克苏鲁恐怖",
        system=system,
        character_name="测试调查员",
        race="人类",
        char_class="记者",
        api_key=API_KEY,
        model_name=MODEL,
        base_url=BASE_URL,
        splitter="naive",
        target_score=75,
        max_revisions=1,
    )
    result["_label"] = label
    result["_source_url"] = source_url
    result["_source_chars"] = len(text)
    result["_chunk_count"] = len(chunks)
    return result


async def main():
    if not API_KEY:
        raise SystemExit("缺少 LLM_API_KEY")
    report = {}

    # 克苏鲁公社：鬼屋（仅元数据，无正文）
    cth_haunt_url = "https://www.cthulhuclub.com/coc-mod/the-haunting/"
    cth_haunt_text = source_metadata(cth_haunt_url)
    report["cthulhuclub_haunting_meta"] = {
        "url": cth_haunt_url,
        "chars": len(cth_haunt_text),
        "detected_system": detect_game_system(cth_haunt_text, "鬼屋"),
        "naive_chunks": len(split_text(cth_haunt_text, mode="naive", chunk_size=900)),
    }
    cth_haunt_gen = await generate_case("克苏鲁公社-鬼屋元数据", cth_haunt_url, cth_haunt_text)
    report["cthulhuclub_haunting_gen"] = cth_haunt_gen

    # 克苏鲁公社：她的声音（仅元数据，无正文）
    cth_voice_url = "https://www.cthulhuclub.com/coc-mod/her-voice/"
    cth_voice_text = source_metadata(cth_voice_url)
    report["cthulhuclub_voice_meta"] = {
        "url": cth_voice_url,
        "chars": len(cth_voice_text),
        "detected_system": detect_game_system(cth_voice_text, "她的声音"),
        "naive_chunks": len(split_text(cth_voice_text, mode="naive", chunk_size=900)),
    }
    cth_voice_gen = await generate_case("克苏鲁公社-她的声音元数据", cth_voice_url, cth_voice_text)
    report["cthulhuclub_voice_gen"] = cth_voice_gen

    # 苹果园：printpage 实际返回登录页（无法直接抓取正文）
    apple_url = "https://goddessfantasy.net/bbs/index.php?action=printpage;topic=120500.0"
    apple_text = source_metadata(apple_url)
    report["apple_garden_printpage"] = {
        "url": apple_url,
        "chars": len(apple_text),
        "is_login_page": "账号" in apple_text and "密码" in apple_text,
        "preview": apple_text[:120],
    }

    # TRPGrepo：西藏之谜 PDF（完整中文 COC 模组）
    tibet_path = OUT_DIR / "samples" / "tibet.pdf"
    tibet_text = extract_text("tibet.pdf", tibet_path.read_bytes())
    report["trpgrepo_tibet_meta"] = {
        "file": "tibet.pdf",
        "chars": len(tibet_text),
        "detected_system": detect_game_system(tibet_text, "西藏之谜"),
        "naive_chunks": len(split_text(tibet_text, mode="naive", chunk_size=900)),
    }
    tibet_gen = await generate_case("TRPGrepo-西藏之谜PDF", "local:tibet.pdf", tibet_text)
    report["trpgrepo_tibet_gen"] = tibet_gen

    out = OUT_DIR / "real_chinese_source_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[完成] 报告已写入 {out}")


if __name__ == "__main__":
    asyncio.run(main())
