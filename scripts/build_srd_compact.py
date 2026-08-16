"""将 5etools-cn 原始 JSON 转换为紧凑结构化 Markdown 后写入知识库，避免直接堆放原始 JSON。"""

import json
import urllib.request
from pathlib import Path

from backend.knowledge_base import get_knowledge_base

BASE = "https://raw.githubusercontent.com/nekoteai/5etools-cn/master/data"
CACHE = Path("eval_results/samples")


def fetch(rel: str) -> dict:
    path = CACHE / rel.replace("/", "_")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    url = f"{BASE}/{rel}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = json.loads(urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def bestiary_compact(data: dict) -> str:
    lines = ["# D&D 5e 怪物紧凑索引", ""]
    for m in data.get("monster", []):
        name = m.get("name", "?")
        size = m.get("size", "")
        typ = m.get("type", "")
        cr = m.get("cr", "?")
        if isinstance(cr, dict):
            cr = cr.get("cr", "?")
        hp = m.get("hp", {})
        if isinstance(hp, dict):
            hp = hp.get("average", hp.get("formula", "?"))
        ac = m.get("ac", [{}])
        if isinstance(ac, list) and ac:
            ac = ac[0].get("ac", "?") if isinstance(ac[0], dict) else ac[0]
        lines.append(f"- {name} | {size} {typ} | CR {cr} | HP {hp} | AC {ac}")
    return "\n".join(lines[:2000])


def spells_compact(data: dict) -> str:
    lines = ["# D&D 5e 法术紧凑索引", ""]
    for s in data.get("spell", []):
        name = s.get("name", "?")
        level = s.get("level", "?")
        school = s.get("school", {})
        if isinstance(school, dict):
            school = school.get("name", "?")
        time = s.get("time", [{}])
        if isinstance(time, list) and time:
            time = time[0].get("number", "?")
        classes = s.get("classes", {})
        if isinstance(classes, dict):
            classes = list(classes.keys())
        lines.append(f"- {name} | {level}环 {school} | 施法时间 {time} | 职业 {','.join(classes)}")
    return "\n".join(lines[:2000])


def items_compact(data: dict) -> str:
    lines = ["# D&D 5e 魔法物品紧凑索引", ""]
    for it in data.get("item", []):
        name = it.get("name", "?")
        rarity = it.get("rarity", "?")
        typ = it.get("type", "?")
        if isinstance(typ, dict):
            typ = typ.get("name", "?")
        lines.append(f"- {name} | {rarity} | {typ}")
    return "\n".join(lines[:2000])


def main():
    kb = get_knowledge_base()
    docs = [
        ("bestiary/bestiary-mm.json", "5etools-CN 怪物紧凑索引", bestiary_compact),
        ("spells/spells-phb.json", "5etools-CN 法术紧凑索引", spells_compact),
        ("items.json", "5etools-CN 魔法物品紧凑索引", items_compact),
    ]
    for rel, title, fn in docs:
        print(f"[build] {rel}")
        data = fetch(rel)
        text = fn(data)
        source = f"srd:5etools-cn:compact:{rel}"
        for d in kb.list_documents():
            if d.get("source") == source:
                kb.remove_document(d["id"])
        kb.add_document(
            title=title,
            content=text,
            source=source,
            system="dnd5e",
            tags=["SRD", "紧凑索引", "dnd5e"],
            chunk_size=1500,
        )
        print(f"  -> {len(text)} chars")
    print("完成。")


if __name__ == "__main__":
    main()
