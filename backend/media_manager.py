"""地图、生物图鉴、角色图片等媒体资源管理（租户隔离）。"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.default_content import CLASSIC_BESTIARY, COMMON_CITIES
from backend.srd_spell_classes import SRD_SPELL_CLASSES

MEDIA_ROOT = Path("media")


def _user_media_dir(username: str) -> Path:
    safe = "".join(c for c in (username or "default") if c.isalnum() or c in "._-") or "default"
    return MEDIA_ROOT / safe


def _images_dir(username: str) -> Path:
    d = _user_media_dir(username) / "images"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _meta_path(username: str, kind: str) -> Path:
    return _user_media_dir(username) / f"{kind}.json"


def _load_meta(username: str, kind: str) -> list[dict]:
    p = _meta_path(username, kind)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_meta(username: str, kind: str, items: list[dict]):
    p = _meta_path(username, kind)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_seeded(username: str):
    """为指定用户写入一次内置经典生物与城市背景（幂等）。"""
    user_dir = _user_media_dir(username)
    user_dir.mkdir(parents=True, exist_ok=True)
    marker = user_dir / "seeded.json"
    if marker.exists():
        return
    for beast in CLASSIC_BESTIARY:
        add_bestiary(
            username=username,
            name=beast["name"],
            system=beast["system"],
            description=beast["description"],
            stats=beast.get("stats", {}),
            image_path="",
            tags=beast.get("tags", []),
            details=beast.get("details", {}),
        )
    for city in COMMON_CITIES:
        add_map(
            username=username,
            name=city["name"],
            description=city["description"],
            image_path="",
            locations=city.get("locations", []),
            system=city.get("system", "custom"),
            details=city.get("details", {}),
        )
    marker.write_text("1", encoding="utf-8")


def save_image(username: str, data: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower() or ".png"
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        ext = ".png"
    img_id = uuid.uuid4().hex[:16]
    path = _images_dir(username) / f"{img_id}{ext}"
    path.write_bytes(data)
    return f"/media/{_user_media_dir(username).name}/images/{img_id}{ext}"


def add_map(username: str, name: str, description: str, image_path: str,
            locations: list[dict] | None = None, system: str = "custom",
            details: dict | None = None, scenario_id: str = "") -> dict:
    items = _load_meta(username, "maps")
    item = {
        "id": uuid.uuid4().hex[:16],
        "name": name or "未命名地图",
        "description": description or "",
        "image_path": image_path,
        "locations": locations or [],
        "system": system,
        "details": details or {},
        "scenario_id": scenario_id or "",
        "created_at": datetime.now().isoformat(),
    }
    items.append(item)
    _save_meta(username, "maps", items)
    return item


def update_map(username: str, name_or_id: str, changes: dict) -> dict | None:
    """按 ID 或名称更新地图；返回更新后的条目。"""
    items = _load_meta(username, "maps")
    for item in items:
        if item.get("id") != name_or_id and item.get("name") != name_or_id:
            continue
        for k, v in (changes or {}).items():
            item[k] = v
        _save_meta(username, "maps", items)
        return item
    return None


def list_maps(username: str, scenario_id: str | None = None) -> list[dict]:
    ensure_seeded(username)
    items = _load_meta(username, "maps")
    # 将知识库中标记为地点/城市的文档合并进地图（保留完整内容，仅展示，不写入用户媒体）
    try:
        from backend.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        for d in kb.documents:
            tags = [str(t) for t in d.get("tags", [])]
            if any(("地点" in t) or ("城市" in t) or ("location" in t.lower()) for t in tags):
                items.append({
                    "id": f"kb-{d['id']}",
                    "name": d.get("title", "未命名地点"),
                    "description": d.get("content", ""),
                    "image_path": "",
                    "locations": [],
                    "system": d.get("system", "custom"),
                    "details": {"source": "知识库"},
                    "scenario_id": "",
                    "created_at": d.get("created_at", ""),
                })
    except Exception:
        pass
    if scenario_id is not None:
        return [i for i in items if not i.get("scenario_id") or i.get("scenario_id") == scenario_id]
    return items


def sync_scenario_maps(username: str, scenario_id: str, locations: list[dict], system: str = "custom"):
    """把世界状态中的常驻地点同步到该剧本的地点图鉴（幂等）。"""
    if not scenario_id:
        return
    existing = {i.get("name") for i in list_maps(username, scenario_id)}
    for loc in locations:
        name = str(loc.get("name", "")).strip() if isinstance(loc, dict) else str(loc).strip()
        if not name or name in existing:
            continue
        add_map(
            username=username,
            name=name,
            description=str(loc.get("description", "")) if isinstance(loc, dict) else "",
            image_path="",
            locations=[],
            system=system,
            scenario_id=scenario_id,
        )
        existing.add(name)


def sync_scenario_bestiary(username: str, scenario_id: str, creatures: list[dict], system: str = "custom"):
    """把世界状态中提取的生物同步到该剧本的生物图鉴（幂等）。"""
    if not scenario_id:
        return
    existing = {i.get("name") for i in list_bestiary(username, scenario_id)}
    for c in creatures:
        name = str(c.get("name", "")).strip() if isinstance(c, dict) else str(c).strip()
        if not name or name in existing:
            continue
        add_bestiary(
            username=username,
            name=name,
            system=system,
            description=str(c.get("description", "")) if isinstance(c, dict) else "",
            stats=c.get("stats") if isinstance(c, dict) else {},
            tags=c.get("tags") if isinstance(c, dict) else [],
            details={"source": "剧本生成"},
            scenario_id=scenario_id,
        )
        existing.add(name)


def delete_map(username: str, map_id: str) -> bool:
    items = _load_meta(username, "maps")
    new = [i for i in items if i["id"] != map_id]
    if len(new) == len(items):
        return False
    _save_meta(username, "maps", new)
    return True


def add_bestiary(username: str, name: str, system: str, description: str,
                 stats: dict | None = None, image_path: str = "", tags: list[str] | None = None,
                 details: dict | None = None, scenario_id: str = "") -> dict:
    items = _load_meta(username, "bestiary")
    item = {
        "id": uuid.uuid4().hex[:16],
        "name": name or "未命名生物",
        "system": system,
        "description": description or "",
        "stats": stats or {},
        "image_path": image_path,
        "tags": tags or [],
        "details": details or {},
        "scenario_id": scenario_id or "",
        "created_at": datetime.now().isoformat(),
    }
    items.append(item)
    _save_meta(username, "bestiary", items)
    return item


def update_bestiary(username: str, name: str, changes: dict) -> dict | None:
    """按 ID 或名称更新生物条目；仅更新传入字段，返回更新后的条目。"""
    items = _load_meta(username, "bestiary")
    for item in items:
        if item.get("id") != name and item.get("name") != name:
            continue
        for k, v in (changes or {}).items():
            if k == "stats" and isinstance(v, dict):
                item["stats"] = {**item.get("stats", {}), **v}
            else:
                item[k] = v
        _save_meta(username, "bestiary", items)
        return item
    return None


def _import_kb_monsters(username: str):
    """从知识库中的 5etools 怪物 JSON 导入标准怪物卡（幂等，仅一次）。"""
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


def list_bestiary(username: str, scenario_id: str | None = None) -> list[dict]:
    ensure_seeded(username)
    _import_kb_monsters(username)
    _import_dnd4_pdf_monsters(username)
    items = _load_meta(username, "bestiary")
    # 将知识库中标记为生物/怪物的文档合并进图鉴（保留完整内容，仅展示，不写入用户媒体）
    try:
        from backend.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        for d in kb.documents:
            tags = [str(t) for t in d.get("tags", [])]
            source = d.get("source", "")
            title = d.get("title", "")
            if "srd:" in source or "compact" in source or "bestiary" in source or "怪物" in title:
                continue
            if any(("生物" in t) or ("怪物" in t) or ("creature" in t.lower()) for t in tags):
                items.append({
                    "id": f"kb-{d['id']}",
                    "name": d.get("title", "未命名生物"),
                    "system": d.get("system", "custom"),
                    "description": d.get("content", ""),
                    "stats": {},
                    "image_path": "",
                    "tags": tags,
                    "details": {"source": "知识库"},
                    "scenario_id": "",
                    "created_at": d.get("created_at", ""),
                })
    except Exception:
        pass
    if scenario_id is not None:
        return [i for i in items if not i.get("scenario_id") or i.get("scenario_id") == scenario_id]
    return items


def delete_bestiary(username: str, beast_id: str) -> bool:
    items = _load_meta(username, "bestiary")
    new = [i for i in items if i["id"] != beast_id]
    if len(new) == len(items):
        return False
    _save_meta(username, "bestiary", new)
    return True


# ── 法术/仪式 ──

_SCHOOL_CN = {
    "A": "防护", "C": "咒法", "D": "预言", "E": "塑能",
    "EN": "附魔", "I": "幻术", "N": "死灵", "T": "变化", "V": "预言",
}
_CLASS_CN = {
    "Wizard": "法师", "Sorcerer": "术士", "Warlock": "邪术师",
    "Cleric": "牧师", "Druid": "德鲁伊", "Bard": "吟游诗人",
    "Paladin": "圣武士", "Ranger": "游侠", "Artificer": "奇械师",
    "wizard": "法师", "sorcerer": "术士", "warlock": "邪术师",
    "cleric": "牧师", "druid": "德鲁伊", "bard": "吟游诗人",
    "paladin": "圣武士", "ranger": "游侠", "artificer": "奇械师",
}

# 内置经典法术：固定格式，name/level/school/ritual/casting_time/range/components/duration/classes/description
CLASSIC_SPELLS = [
    {"name": "火焰箭", "level": "0", "school": "塑能", "ritual": False,
     "casting_time": "1 动作", "range": "120 尺", "components": "V、S", "duration": "立即",
     "classes": ["术士", "法师"],
     "description": "你对施法距离内的一个生物或物件掷出一团火焰。进行一次远程法术攻击，命中则目标受到 1d10 点火焰伤害。未被着装或携带的可燃物件会被点燃。升环：5 级时伤害增至 2d10，11 级 3d10，17 级 4d10。"},
    {"name": "冷冻射线", "level": "0", "school": "塑能", "ritual": False,
     "casting_time": "1 动作", "range": "60 尺", "components": "V、S", "duration": "立即",
     "classes": ["术士", "法师"],
     "description": "一道蓝白色寒光射向目标。远程法术攻击命中后造成 1d8 点寒冷伤害，目标速度减少 10 尺直到你的下一回合开始。"},
    {"name": "魔法伎俩", "level": "0", "school": "变化", "ritual": False,
     "casting_time": "1 动作", "range": "10 尺", "components": "V、S", "duration": "至多 1 小时",
     "classes": ["吟游诗人", "术士", "邪术师", "法师"],
     "description": "制造简单魔法效果：点燃/熄灭蜡烛、清洁衣物、制造声响、改变味道等。同时维持的效果不超过三个。"},
    {"name": "法师之手", "level": "0", "school": "咒法", "ritual": False,
     "casting_time": "1 动作", "range": "30 尺", "components": "V、S", "duration": "1 分钟",
     "classes": ["吟游诗人", "术士", "邪术师", "法师"],
     "description": "一只半透明漂浮手出现在范围内，可执行 10 磅以内物体的简单操作：开门、取物、倾倒药剂等。不能攻击、启动魔法物品或携带超过 10 磅。"},
    {"name": "次级幻影", "level": "0", "school": "幻术", "ritual": False,
     "casting_time": "1 动作", "range": "30 尺", "components": "S、M（一点羊毛）", "duration": "1 分钟",
     "classes": ["吟游诗人", "术士", "邪术师", "法师"],
     "description": "在范围内制造一个声音或一个物体的影像，持续到法术结束。影像不能移动，不能发出声音以外的效果。"},
    {"name": "魔能爆", "level": "0", "school": "塑能", "ritual": False,
     "casting_time": "1 动作", "range": "120 尺", "components": "V、S", "duration": "立即",
     "classes": ["邪术师"],
     "description": "对目标进行远程法术攻击，命中造成 1d10 力场伤害。5 级时攻击次数增至两次，11 级三次，17 级四次。"},
    {"name": "圣火术", "level": "0", "school": "塑能", "ritual": False,
     "casting_time": "1 动作", "range": "60 尺", "components": "V、S", "duration": "立即",
     "classes": ["牧师"],
     "description": "灼热圣光倾泻而下。目标必须通过敏捷豁免，否则受到 1d8 点光耀伤害。目标不能因掩蔽获得豁免优势。"},
    {"name": "荆棘之鞭", "level": "0", "school": "变化", "ritual": False,
     "casting_time": "1 动作", "range": "30 尺", "components": "V、S、M（一根荆棘藤）", "duration": "立即",
     "classes": ["德鲁伊"],
     "description": "藤蔓长鞭抽向目标。近战法术攻击命中造成 1d6 穿刺伤害，并可将目标向你拉近 10 尺。"},
    {"name": "恶言相加", "level": "0", "school": "附魔", "ritual": False,
     "casting_time": "1 动作", "range": "60 尺", "components": "V", "duration": "立即",
     "classes": ["吟游诗人"],
     "description": "你对目标说出恶毒咒语。目标必须通过感知豁免，否则受到 1d4 心灵伤害，且下一次攻击检定有劣势。"},
    {"name": "奇术", "level": "0", "school": "变化", "ritual": False,
     "casting_time": "1 动作", "range": "30 尺", "components": "V", "duration": "至多 1 分钟",
     "classes": ["牧师", "提夫林"],
     "description": "制造一个低语般的神迹：声音放大、火焰变色、地面颤动或双眼发光，用于威慑与宣告。"},
    {"name": "神导术", "level": "0", "school": "预言", "ritual": False,
     "casting_time": "1 动作", "range": "触及", "components": "V、S", "duration": "专注，至多 1 分钟",
     "classes": ["牧师", "德鲁伊"],
     "description": "触及的自愿生物在随后的一次属性检定中获得 1d4 加值。"},
    {"name": "德鲁伊伎俩", "level": "0", "school": "变化", "ritual": False,
     "casting_time": "1 动作", "range": "30 尺", "components": "V、S", "duration": "立即",
     "classes": ["德鲁伊"],
     "description": "与自然沟通的小把戏：预测天气、让花朵绽放、点燃/熄灭篝火、制造兽鸣。"},
    {"name": "电爪", "level": "0", "school": "塑能", "ritual": False,
     "casting_time": "1 动作", "range": "触及", "components": "V、S", "duration": "立即",
     "classes": ["术士", "法师"],
     "description": "手中跃出闪电。近战法术攻击命中造成 1d8 闪电伤害，目标在你的下一回合开始前不能进行借机攻击。"},
    {"name": "魔法飞弹", "level": "1", "school": "塑能", "ritual": False,
     "casting_time": "1 动作", "range": "120 尺", "components": "V、S", "duration": "立即",
     "classes": ["术士", "法师"],
     "description": "三枚魔法飞镖自动命中施法距离内的目标，每枚造成 1d4+1 力场伤害。飞镖可分配不同目标。升环：每高一环多一枚飞镖。"},
    {"name": "法师护甲", "level": "1", "school": "防护", "ritual": False,
     "casting_time": "1 动作", "range": "触及", "components": "V、S、M（一小块鞣制皮革）", "duration": "8 小时",
     "classes": ["术士", "法师"],
     "description": "目标未着甲时，其基础 AC 变为 13+敏捷调整。目标着甲或法术结束时终止。"},
    {"name": "护盾术", "level": "1", "school": "防护", "ritual": False,
     "casting_time": "1 反应（被击中时）", "range": "自身", "components": "V、S", "duration": "1 轮",
     "classes": ["术士", "法师"],
     "description": "隐形力场护盾出现，直到你的下一回合开始 AC+5，且免疫魔法飞弹。"},
    {"name": "燃烧之手", "level": "1", "school": "塑能", "ritual": False,
     "casting_time": "1 动作", "range": "自身（15 尺锥形）", "components": "V、S", "duration": "立即",
     "classes": ["术士", "法师"],
     "description": "火焰从指尖喷出，15 尺锥形范围内生物必须通过敏捷豁免，失败受到 3d6 火焰伤害，成功减半。升环：每高一环 +1d6。"},
    {"name": "治愈真言", "level": "1", "school": "塑能", "ritual": False,
     "casting_time": "1 附赠动作", "range": "60 尺", "components": "V", "duration": "立即",
     "classes": ["牧师", "吟游诗人"],
     "description": "施法距离内可见的一个生物恢复 1d4+施法属性调整点生命值。对构装体和不死生物无效。升环：每高一环 +1d4。"},
    {"name": "治疗伤害", "level": "1", "school": "塑能", "ritual": False,
     "casting_time": "1 动作", "range": "触及", "components": "V、S", "duration": "立即",
     "classes": ["牧师", "德鲁伊", "圣武士", "游侠"],
     "description": "触及的生物恢复 1d8+施法属性调整点生命值。对构装体和不死生物无效。升环：每高一环 +1d8。"},
    {"name": "祝福术", "level": "1", "school": "附魔", "ritual": False,
     "casting_time": "1 动作", "range": "30 尺", "components": "V、S、M（一点圣水）", "duration": "专注，至多 1 分钟",
     "classes": ["牧师", "圣武士"],
     "description": "至多三个生物在攻击检定和豁免检定时获得 1d4 加值。"},
    {"name": "侦测魔法", "level": "1", "school": "预言", "ritual": True,
     "casting_time": "1 动作", "range": "自身", "components": "V、S", "duration": "专注，至多 10 分钟",
     "classes": ["吟游诗人", "牧师", "德鲁伊", "圣武士", "游侠", "术士", "邪术师", "法师"],
     "description": "你能感知 30 尺内的魔法与魔法物品，并用动作辨识其学派。"},
    {"name": "隐形术", "level": "2", "school": "幻术", "ritual": False,
     "casting_time": "1 动作", "range": "触及", "components": "V、S、M（一根包裹在阿拉伯胶中的睫毛）", "duration": "专注，至多 1 小时",
     "classes": ["吟游诗人", "术士", "邪术师", "法师"],
     "description": "触及的生物连同随身物品变为隐形，直到其攻击或施法。"},
    {"name": "灼热射线", "level": "2", "school": "塑能", "ritual": False,
     "casting_time": "1 动作", "range": "120 尺", "components": "V、S", "duration": "立即",
     "classes": ["术士", "法师"],
     "description": "射出三道火焰射线，每道进行一次远程法术攻击，命中造成 2d6 火焰伤害。升环：每高一环多一道射线。"},
    {"name": "迷踪步", "level": "2", "school": "咒法", "ritual": False,
     "casting_time": "1 附赠动作", "range": "自身", "components": "V", "duration": "立即",
     "classes": ["术士", "邪术师", "法师"],
     "description": "你被银色雾气包裹，瞬间传送到 30 尺内可见的未占据空间。"},
    {"name": "火球术", "level": "3", "school": "塑能", "ritual": False,
     "casting_time": "1 动作", "range": "150 尺", "components": "V、S、M（一小球蝙蝠粪及硫磺）", "duration": "立即",
     "classes": ["术士", "法师"],
     "description": "明亮的闪光从你的指间飞驰向施法距离内你指定的一点，并随着一声低吼迸成一片烈焰。目标点周围半径 20 尺球状区域内的每个生物必须进行一次敏捷豁免。豁免失败者将受到 8d6 点火焰伤害，豁免成功则伤害减半。迸发的火焰将绕过拐角扩散，并点燃区域内所有未被着装或携带的可燃物件。升环：使用 4 环或更高法术位施放时，每比 3 环高一环，伤害增加 1d6。"},
    {"name": "闪电束", "level": "3", "school": "塑能", "ritual": False,
     "casting_time": "1 动作", "range": "自身（100 尺线状）", "components": "V、S、M（一点毛皮和一根琥珀/水晶棒）", "duration": "立即",
     "classes": ["术士", "法师"],
     "description": "一道 100 尺长、5 尺宽的闪电从你指向的方向射出，线上生物敏捷豁免失败受到 8d6 闪电伤害，成功减半。升环：每高一环 +1d6。"},
    {"name": "反制法术", "level": "3", "school": "防护", "ritual": False,
     "casting_time": "1 反应", "range": "60 尺", "components": "S", "duration": "立即",
     "classes": ["术士", "邪术师", "法师"],
     "description": "打断一个正在施放的法术。若目标法术环位不高于你使用的法术位，该法术失效。高于则进行施法属性检定，DC=10+目标法术环位。"},
    {"name": "飞行术", "level": "3", "school": "变化", "ritual": False,
     "casting_time": "1 动作", "range": "触及", "components": "V、S、M（任意鸟类的翼羽）", "duration": "专注，至多 10 分钟",
     "classes": ["术士", "邪术师", "法师"],
     "description": "触及的自愿生物获得 60 尺飞行速度。升环：每高一环可多影响一个生物。"},
    {"name": "冰风暴", "level": "4", "school": "塑能", "ritual": False,
     "casting_time": "1 动作", "range": "300 尺", "components": "V、S、M（一点灰尘和几滴水）", "duration": "立即",
     "classes": ["德鲁伊", "术士", "法师"],
     "description": "以目标点为中心 20 尺半径、40 尺高的圆柱区域内降下冰雹，生物受到 2d8 钝击+4d6 寒冷伤害（敏捷豁免成功减半），区域变为困难地形直到你的下一回合结束。"},
    {"name": "寒冰锥", "level": "5", "school": "塑能", "ritual": False,
     "casting_time": "1 动作", "range": "自身（60 尺锥形）", "components": "V、S、M（一小块水晶或玻璃锥体）", "duration": "立即",
     "classes": ["术士", "法师"],
     "description": "60 尺锥形寒流爆发，范围内生物体质豁免失败受到 8d8 寒冷伤害，成功减半。豁免失败的生物若 HP 因此归零会被冻成冰雕。升环：每高一环 +1d8。"},
]

_CLASSIC_SPELL_NAMES = {s["name"] for s in CLASSIC_SPELLS}


def _deleted_builtin_path(username: str) -> Path:
    return _user_media_dir(username) / "deleted_builtin_spells.json"


def _load_deleted_builtin_spells(username: str) -> set[str]:
    p = _deleted_builtin_path(username)
    try:
        return set(json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return set()


def _mark_deleted_builtin_spell(username: str, name: str):
    if name not in _CLASSIC_SPELL_NAMES:
        return
    deleted = _load_deleted_builtin_spells(username)
    deleted.add(name)
    _deleted_builtin_path(username).write_text(
        json.dumps(sorted(deleted), ensure_ascii=False), encoding="utf-8"
    )


_DND5_ENTRY_RE = re.compile(r"\{@(?:damage|dice|hit|chance)\s+([^}]+)\}")
_DND5_SPELL_RE = re.compile(r"\{@spell\s+([^}]+)\}")


def _entries_to_text(entries: Any) -> str:
    """把 5etools entries 转为纯文本，去掉 @ 标签但保留数值。"""
    if isinstance(entries, str):
        return entries
    parts: list[str] = []

    def walk(node: Any):
        if isinstance(node, str):
            parts.append(node)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            if node.get("type") == "entries":
                walk(node.get("entries"))
            elif node.get("type") == "list":
                for item in node.get("items", []):
                    parts.append("· ")
                    walk(item)
                    parts.append("；")
            elif node.get("type") == "table":
                parts.append("（见表）")
            else:
                for v in node.values():
                    walk(v)

    walk(entries)
    text = " ".join("".join(parts).split())
    text = _DND5_ENTRY_RE.sub(lambda m: m.group(1), text)
    text = _DND5_SPELL_RE.sub(lambda m: m.group(1), text)
    text = re.sub(r"\{@[a-z]+\s+([^}]+)\}", lambda m: m.group(1), text)
    return text[:2000]


def _fmt_time(data: Any) -> str:
    try:
        if isinstance(data, list) and data:
            t = data[0]
            n = t.get("number", 1)
            unit = str(t.get("unit", "action"))
            unit_cn = {"action": "动作", "bonus": "附赠动作", "reaction": "反应",
                       "minute": "分钟", "hour": "小时", "instantaneous": "立即"}.get(unit, unit)
            return f"{n} {unit_cn}"
    except Exception:
        pass
    return "1 动作"


def _fmt_range(data: Any) -> str:
    try:
        if isinstance(data, dict):
            rtype = str(data.get("type", ""))
            if rtype == "self":
                return "自身"
            if rtype == "touch":
                return "触及"
            if rtype == "point":
                dist = data.get("distance", {})
                amount = dist.get("amount", "")
                unit = str(dist.get("type", "feet"))
                return f"{amount} {'尺' if unit == 'feet' else unit}"
    except Exception:
        pass
    return "自身"


def _fmt_components(data: Any) -> str:
    try:
        if not isinstance(data, dict):
            return ""
        parts = []
        if data.get("v"):
            parts.append("V")
        if data.get("s"):
            parts.append("S")
        mat = data.get("m")
        if mat:
            text = _entries_to_text(mat.get("text", "")) if isinstance(mat, dict) else str(mat)
            parts.append(f"M（{text}）")
        return "、".join(parts)
    except Exception:
        return ""


def _fmt_duration(data: Any) -> str:
    try:
        if isinstance(data, list) and data:
            t = data[0]
            conc = "专注，至多 " if t.get("concentration") else ""
            rtype = str(t.get("type", ""))
            if rtype == "instant":
                return "立即"
            dur = t.get("duration", {})
            n = dur.get("amount", "")
            unit = str(dur.get("type", "minute"))
            unit_cn = {"minute": "分钟", "hour": "小时", "round": "轮", "day": "日"}.get(unit, unit)
            return f"{conc}{n} {unit_cn}".strip()
    except Exception:
        pass
    return "立即"


def _seed_classic_spells(username: str):
    """把内置经典法术写入用户法术图鉴（幂等，按名称补齐；用户删除过的经典法术不再补回）。"""
    existing = _load_meta(username, "spells")
    names = {i.get("name") for i in existing}
    deleted = _load_deleted_builtin_spells(username)
    for sp in CLASSIC_SPELLS:
        if sp["name"] in names or sp["name"] in deleted:
            continue
        add_spell(
            username=username,
            name=sp["name"],
            system="dnd5e",
            description=sp["description"],
            level=sp["level"],
            school=sp["school"],
            ritual=sp["ritual"],
            casting_time=sp["casting_time"],
            range_=sp["range"],
            components=sp["components"],
            duration=sp["duration"],
            classes=sp["classes"],
            scenario_id="",
            tags=["经典", "DND5e", "法术"],
        )


def _import_kb_spells(username: str):
    """从知识库自动抓取 SRD 法术 JSON，并转成统一格式写入用户法术图鉴（幂等，仅一次）。"""
    user_dir = _user_media_dir(username)
    user_dir.mkdir(parents=True, exist_ok=True)
    marker = user_dir / "kb_spells_imported.json"
    if marker.exists():
        return
    try:
        from backend.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        items = _load_meta(username, "spells")
        existing = {i.get("name") for i in items}
        imported = 0
        for doc in kb.documents:
            source = str(doc.get("source", ""))
            title = str(doc.get("title", ""))
            if "spells" not in source and "法术" not in title:
                continue
            try:
                data = json.loads(doc.get("content", ""))
            except Exception:
                continue
            for s in data.get("spell", []):
                name = str(s.get("name", ""))
                if not name or name in existing:
                    continue
                existing.add(name)
                classes_raw = (s.get("classes") or {}).get("fromClassList", []) if isinstance(s.get("classes"), dict) else []
                classes = [_CLASS_CN.get(str(c), str(c)) for c in classes_raw]
                if not classes:
                    classes = _srd_spell_classes(name)
                items.append({
                    "id": uuid.uuid4().hex[:16],
                    "name": name,
                    "system": "dnd5e",
                    "description": _entries_to_text(s.get("entries", [])),
                    "level": str(s.get("level", 0)),
                    "school": _SCHOOL_CN.get(str(s.get("school", "")), "未知"),
                    "ritual": bool(s.get("meta", {}).get("ritual", False)) if isinstance(s.get("meta"), dict) else False,
                    "casting_time": _fmt_time(s.get("time", [])),
                    "range": _fmt_range(s.get("range", {})),
                    "components": _fmt_components(s.get("components", {})),
                    "duration": _fmt_duration(s.get("duration", [])),
                    "classes": classes,
                    "scenario_id": "",
                    "tags": ["SRD", "知识库", "法术"],
                    "created_at": datetime.now().isoformat(),
                })
                imported += 1
        if imported:
            _save_meta(username, "spells", items)
        marker.write_text(json.dumps({"imported": imported}, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[MediaManager] 知识库法术导入失败: {e}")



def _norm_spell_classes(value: Any) -> list[str]:
    """把 classes 规范为字符串数组（兼容逗号/顿号字符串）。"""
    if isinstance(value, str):
        return [x.strip() for x in re.split(r"[,，、]", value) if x.strip()]
    if isinstance(value, list):
        return [str(x) for x in value if x]
    return []


def _srd_spell_classes(name: str) -> list[str]:
    """按名称查 SRD 职业映射，兼容大小写差异。"""
    if name in SRD_SPELL_CLASSES:
        return list(SRD_SPELL_CLASSES[name])
    lower = name.lower()
    for k, v in SRD_SPELL_CLASSES.items():
        if k.lower() == lower:
            return list(v)
    return []


def add_spell(username: str, name: str, system: str, description: str,
              level: str = "0", school: str = "", ritual: bool = False,
              casting_time: str = "", range_: str = "", components: str = "",
              duration: str = "", classes: list[str] | None = None,
              scenario_id: str = "", tags: list[str] | None = None) -> dict:
    items = _load_meta(username, "spells")
    item = {
        "id": uuid.uuid4().hex[:16],
        "name": name or "未命名法术",
        "system": system,
        "description": description or "",
        "level": str(level),
        "school": school or "",
        "ritual": bool(ritual),
        "casting_time": casting_time or "",
        "range": range_ or "",
        "components": components or "",
        "duration": duration or "",
        "classes": _norm_spell_classes(classes),
        "scenario_id": scenario_id or "",
        "tags": tags or [],
        "created_at": datetime.now().isoformat(),
    }
    items.append(item)
    _save_meta(username, "spells", items)
    return item


def update_spell(username: str, name_or_id: str, changes: dict) -> dict | None:
    """按 ID 或名称更新法术/仪式条目。"""
    items = _load_meta(username, "spells")
    for item in items:
        if item.get("id") != name_or_id and item.get("name") != name_or_id:
            continue
        for k, v in (changes or {}).items():
            item[k] = v
        _save_meta(username, "spells", items)
        return item
    return None


def _fill_srd_spell_classes(username: str):
    """为旧导入的 SRD 法术补齐职业映射（离线映射表）。"""
    items = _load_meta(username, "spells")
    changed = False
    for item in items:
        if "SRD" in (item.get("tags") or []) and not item.get("classes"):
            mapped = _srd_spell_classes(item.get("name"))
            if mapped:
                item["classes"] = mapped
                changed = True
    if changed:
        _save_meta(username, "spells", items)


def list_spells(username: str, scenario_id: str | None = None) -> list[dict]:
    ensure_seeded(username)
    _seed_classic_spells(username)
    _import_kb_spells(username)
    _fill_srd_spell_classes(username)
    items = _load_meta(username, "spells")
    # 兼容旧数据/外部写入：classes 统一为数组
    changed = False
    for item in items:
        norm = _norm_spell_classes(item.get("classes"))
        if norm != item.get("classes"):
            item["classes"] = norm
            changed = True
    if changed:
        _save_meta(username, "spells", items)
    if scenario_id is not None:
        return [i for i in items if not i.get("scenario_id") or i.get("scenario_id") == scenario_id]
    return items


def delete_spell(username: str, spell_id: str) -> bool:
    items = _load_meta(username, "spells")
    removed = next((i for i in items if i["id"] == spell_id), None)
    new = [i for i in items if i["id"] != spell_id]
    if len(new) == len(items):
        return False
    if removed:
        _mark_deleted_builtin_spell(username, str(removed.get("name", "")))
    _save_meta(username, "spells", new)
    return True


def sync_scenario_spells(username: str, scenario_id: str, spells: list[dict], system: str = "custom"):
    """把世界状态中提取的法术/仪式同步到该剧本的法术图鉴（幂等）。"""
    if not scenario_id:
        return
    existing = {i.get("name") for i in list_spells(username, scenario_id)}
    for s in spells:
        name = str(s.get("name", "")).strip() if isinstance(s, dict) else str(s).strip()
        if not name or name in existing:
            continue
        add_spell(
            username=username,
            name=name,
            system=system,
            description=str(s.get("description", "")) if isinstance(s, dict) else "",
            level=str(s.get("level", "0")) if isinstance(s, dict) else "0",
            school=str(s.get("school", "")) if isinstance(s, dict) else "",
            ritual=bool(s.get("ritual", False)) if isinstance(s, dict) else False,
            casting_time=str(s.get("casting_time", "")) if isinstance(s, dict) else "",
            range_=str(s.get("range", "")) if isinstance(s, dict) else "",
            components=str(s.get("components", "")) if isinstance(s, dict) else "",
            duration=str(s.get("duration", "")) if isinstance(s, dict) else "",
            classes=list(s.get("classes", [])) if isinstance(s, dict) else [],
            scenario_id=scenario_id,
        )
        existing.add(name)
