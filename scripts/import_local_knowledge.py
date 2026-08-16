"""导入 data/need_read 中的本地规则书/资料，并抓取 DND 灰机 Wiki 首页，写入知识库。"""

import re
import subprocess
import urllib.request
from pathlib import Path

from backend.knowledge_base import get_knowledge_base
from backend.scenario_importer import extract_text, split_text

DATA_DIR = Path("data/need_read")
WIKI_URL = "https://dnd.huijiwiki.com/wiki/%E9%A6%96%E9%A1%B5"


def detect_system(path: str) -> str:
    p = path.lower()
    if "4e" in p or "dnd4" in p or "怪物图鉴" in p or "玩家手册" in p or "城主之书" in p or "精界" in p or "元素英雄" in p or "暗影英雄" in p:
        return "dnd4e"
    if "克苏鲁" in p or "coc" in p or "call of cthulhu" in p:
        return "coc"
    if "五代" in p or "5e" in p or "dnd5" in p or "d&d5" in p:
        return "dnd5e"
    return "custom"


def strip_html(data: bytes) -> str:
    import html as html_mod
    text = data.decode("utf-8", errors="replace")
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html_mod.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def extract_chm(chm_path: Path, out_dir: Path) -> str:
    """使用 Windows hh.exe 解压 CHM 后提取 HTML 文本。"""
    if out_dir.exists():
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["hh.exe", "-decompile", str(out_dir), str(chm_path)], check=True, timeout=60)
    except Exception as e:
        print(f"  [CHM] 解压失败: {e}")
        return ""
    texts = []
    for html_file in out_dir.rglob("*.htm*"):
        try:
            texts.append(strip_html(html_file.read_bytes()))
        except Exception:
            continue
    return "\n\n".join(t for t in texts if t.strip())


def main():
    kb = get_knowledge_base()
    count = 0

    for path in sorted(DATA_DIR.rglob("*")):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext not in (".pdf", ".chm", ".txt", ".md", ".doc", ".docx"):
            continue
        rel = path.relative_to(DATA_DIR).as_posix()
        print(f"[import] {rel}")
        try:
            if ext == ".chm":
                text = extract_chm(path, Path("data/need_read/_chm_tmp") / path.stem)
            else:
                text = extract_text(path.name, path.read_bytes())
        except Exception as e:
            print(f"  [skip] {e}")
            continue
        if not text.strip():
            print("  [skip] 空文本")
            continue
        system = detect_system(rel)
        source = f"local:{rel}"
        for d in kb.list_documents():
            if d.get("source") == source:
                kb.remove_document(d["id"])
        kb.add_document(
            title=f"本地资料：{path.name}",
            content=text,
            source=source,
            system=system,
            tags=["本地资料", system, ext.lstrip(".")],
            chunk_size=1200,
        )
        count += 1
        print(f"  -> {len(text)} chars, system={system}")

    # 抓取灰机 Wiki 首页
    print("[wiki] 抓取首页...")
    try:
        req = urllib.request.Request(WIKI_URL, headers={"User-Agent": "Mozilla/5.0"})
        wiki_text = strip_html(urllib.request.urlopen(req, timeout=30).read())
        source = "wiki:首页"
        for d in kb.list_documents():
            if d.get("source") == source:
                kb.remove_document(d["id"])
        kb.add_document(
            title="DND 灰机 Wiki 首页资料",
            content=wiki_text,
            source=source,
            system="custom",
            tags=["Wiki", "DND", "参考"],
            chunk_size=1200,
        )
        print(f"  -> {len(wiki_text)} chars")
        count += 1
    except Exception as e:
        print(f"[wiki] 抓取失败: {e}")

    print(f"\n完成，共导入 {count} 份资料。")


if __name__ == "__main__":
    main()
