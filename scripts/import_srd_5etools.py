"""从 5etools-cn 公开 GitHub 镜像导入 D&D 5e SRD 数据到知识库，增强游戏规则/生物/法术内容。"""

import json
import urllib.request

from backend.knowledge_base import get_knowledge_base

BASE = "https://raw.githubusercontent.com/nekoteai/5etools-cn/master/data"
FILES = [
    ("bestiary/bestiary-mm.json", "5etools-CN 怪物图鉴（MM）", "dnd5e"),
    ("spells/spells-phb.json", "5etools-CN 法术（PHB）", "dnd5e"),
    ("items.json", "5etools-CN 魔法物品（Items）", "dnd5e"),
]


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def main():
    kb = get_knowledge_base()
    for rel, title, system in FILES:
        url = f"{BASE}/{rel}"
        print(f"[fetch] {url}")
        try:
            raw = fetch(url)
            text = raw.decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  [skip] {e}")
            continue
        source = f"srd:5etools-cn:{rel}"
        for d in kb.list_documents():
            if d.get("source") == source:
                kb.remove_document(d["id"])
        kb.add_document(
            title=title,
            content=text,
            source=source,
            system=system,
            tags=["SRD", "5etools", system, "规则/生物/法术"],
            chunk_size=1200,
        )
        print(f"  -> {len(text)} chars")
    print("完成。")


if __name__ == "__main__":
    main()
