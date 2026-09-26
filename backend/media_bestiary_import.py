"""生物图鉴的批量导入：知识库 5etools 怪物 JSON 与 D&D4e 怪物 PDF 文本。

从 `media_bestiary` 拆出（那边只留 CRUD 与剧本同步），并在 `media_bestiary` 再导出，
`media_manager` / `media_store` 的既有 import 面不变。

**循环导入**：两个导入器都要写库用的 `add_bestiary`，它在 `media_bestiary`；
这里在函数内延迟 import，避免模块级互相依赖。
"""
from __future__ import annotations

import json
import re

from backend.media_store import _load_meta, _user_media_dir

def _import_kb_monsters(username: str):
    """从知识库中的 5etools 怪物 JSON 导入标准怪物卡（幂等，仅一次）。"""
    from backend.media_bestiary import add_bestiary  # 延迟导入：避免与 media_bestiary 循环依赖
    user_dir = _user_media_dir(username)
    user_dir.mkdir(parents=True, exist_ok=True)
    marker = user_dir / "kb_bestiary_imported.json"
    if marker.exists():
        return
    try:
        from backend.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        existing_names = {i.get("name") for i in _load_meta(username, "bestiary") if i.get("system") == "dnd5e"}
        imported = 0
        for doc in kb.documents:
            source = doc.get("source", "")
            title = doc.get("title", "")
            if "bestiary" not in source and "怪物图鉴" not in title and "怪物库" not in title:
                continue
            try:
                data = json.loads(doc.get("content", ""))
            except Exception:
                continue
            for m in data.get("monster", []):
                name = m.get("name", "")
                if not name or name in existing_names:
                    continue
                existing_names.add(name)
                ac = m.get("ac")
                hp = m.get("hp") or {}
                speed = m.get("speed") or {}
                speed_str = "、".join(f"{k} {v}" for k, v in speed.items()) if isinstance(speed, dict) else str(speed)
                skills = m.get("skill") or {}
                skill_str = "、".join(f"{k} {v}" for k, v in skills.items()) if isinstance(skills, dict) else str(skills)
                traits = m.get("trait") or []
                actions = m.get("action") or []
                trait_str = "；".join(
                    f"{t.get('name','')}: {' '.join(str(e) for e in t.get('entries', []))}" for t in traits if isinstance(t, dict)
                )
                action_str = "；".join(
                    f"{a.get('name','')}: {' '.join(str(e) for e in a.get('entries', []))}" for a in actions if isinstance(a, dict)
                )
                stats = {
                    "AC": "/".join(str(x) for x in ac) if isinstance(ac, list) else str(ac or "—"),
                    "HP": str(hp.get("average", "")) if isinstance(hp, dict) else str(hp or "—"),
                    "速度": speed_str or "—",
                    "力量": str(m.get("str", "—")), "敏捷": str(m.get("dex", "—")),
                    "体质": str(m.get("con", "—")), "智力": str(m.get("int", "—")),
                    "感知": str(m.get("wis", "—")), "魅力": str(m.get("cha", "—")),
                    "技能": skill_str or "—",
                    "感官": f"被动察觉 {m.get('passive','—')}",
                    "语言": "、".join(str(x) for x in (m.get("languages", []) or [])) or "—",
                    "挑战等级": str(m.get("cr", "—")),
                    "豁免": "、".join(f"{k} +{v}" for k, v in (m.get("save") or {}).items()) if isinstance(m.get("save"), dict) else "—",
                    "特性": trait_str or "—",
                    "动作": action_str or "—",
                }
                details = {
                    "habitat": "、".join(str(x) for x in (m.get("environment", []) or [])) or "",
                    "source": "5etools-CN SRD",
                }
                add_bestiary(
                    username=username,
                    name=name,
                    system="dnd5e",
                    description=f"{m.get('size','')} {m.get('type',{}).get('type','') if isinstance(m.get('type'),dict) else m.get('type','')} · {' '.join(str(x) for x in (m.get('alignment',[]) or []))}".strip(" ·"),
                    stats=stats,
                    image_path="",
                    tags=["SRD", "生物", "知识库", "DND5e"],
                    details=details,
                    scenario_id="",
                )
                imported += 1
        marker.write_text(json.dumps({"imported": imported}, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[MediaManager] 知识库怪物导入失败: {e}")



def _import_dnd4_pdf_monsters(username: str):
    """从知识库中的 D&D4e 怪物 PDF 文本解析标准怪物卡（幂等，仅一次）。"""
    from backend.media_bestiary import add_bestiary  # 延迟导入：避免与 media_bestiary 循环依赖
    user_dir = _user_media_dir(username)
    user_dir.mkdir(parents=True, exist_ok=True)
    marker = user_dir / "kb_dnd4_imported.json"
    if marker.exists():
        return
    try:
        from backend.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        existing_names = {i.get("name") for i in _load_meta(username, "bestiary") if i.get("system") == "dnd4e"}
        imported = 0
        entry_pattern = re.compile(r"(?m)^([^\n（]+?)（([^）]*?)）\s*LV(\d+)\s*(\S+(?:\s+\S+)*?)\s*$")
        for doc in kb.documents:
            title = doc.get("title", "")
            source = doc.get("source", "")
            if not (("怪物图鉴" in title or "怪物库" in title) and source.endswith(".pdf")):
                continue
            text = doc.get("content", "")
            matches = list(entry_pattern.finditer(text))
            for i, m in enumerate(matches):
                name = m.group(1).strip()
                if name in existing_names:
                    continue
                existing_names.add(name)
                level = int(m.group(3))
                role = m.group(4).strip()
                block_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                block = text[m.start():block_end]
                hp = re.search(r"HP\s*(\d+)", block)
                ac = re.search(r"AC\s*(\d+)", block)
                frw = re.search(r"强韧\s*(\d+)\s*反射\s*(\d+)\s*意志\s*(\d+)", block)
                speed = re.search(r"速度\s*(\d+)", block)
                skills = re.search(r"技能：(.+)", block)
                attrs = re.search(
                    r"力量\s*(\d+).*?敏捷\s*(\d+).*?感知\s*(\d+).*?体质\s*(\d+).*?智力\s*(\d+).*?魅力\s*(\d+)",
                    block, re.S,
                )
                align_lang = re.search(r"阵营：(\S+)\s*语言：(.+)", block)
                xp = re.search(r"XP\s*(\d+)", block)
                size = re.search(r"(微型|小型|中型|大型|超大型|巨型)", block)
                # 把“标准动作/特性/移动动作/触发动作”等原始文本保留为动作说明
                actions_raw = re.sub(r"\s+", " ", block)
                actions_raw = actions_raw[:1200]
                stats = {
                    "等级": str(level),
                    "角色类型": role,
                    "XP": xp.group(1) if xp else "—",
                    "HP": hp.group(1) if hp else "—",
                    "AC": ac.group(1) if ac else "—",
                    "强韧": frw.group(1) if frw else "—",
                    "反射": frw.group(2) if frw else "—",
                    "意志": frw.group(3) if frw else "—",
                    "速度": speed.group(1) if speed else "—",
                    "力量": attrs.group(1) if attrs else "—",
                    "敏捷": attrs.group(2) if attrs else "—",
                    "体质": attrs.group(4) if attrs else "—",
                    "智力": attrs.group(5) if attrs else "—",
                    "感知": attrs.group(3) if attrs else "—",
                    "魅力": attrs.group(6) if attrs else "—",
                    "技能": skills.group(1).strip() if skills else "—",
                    "阵营": align_lang.group(1) if align_lang else "—",
                    "语言": align_lang.group(2).strip() if align_lang else "—",
                    "动作": actions_raw,
                }
                details = {"source": title.replace("本地资料：", "")}
                add_bestiary(
                    username=username,
                    name=name,
                    system="dnd4e",
                    description=f"{size.group(1) if size else ''} {role} · LV{level}".strip(),
                    stats=stats,
                    image_path="",
                    tags=["DND4e", "生物", "知识库", "PDF"],
                    details=details,
                    scenario_id="",
                )
                imported += 1
        marker.write_text(json.dumps({"imported": imported}, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[MediaManager] D&D4e怪物PDF导入失败: {e}")
