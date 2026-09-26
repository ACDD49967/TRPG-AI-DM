"""世界生成用到的生物数值：数量解析、NPC 数值推导、图鉴富化与归一化。

从 backend.engine.world_builder 拆出。
"""
from __future__ import annotations

import re
from typing import Any


_CN_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}



def _parse_creature_count(name: str) -> tuple[int, str]:
    """把“两个地精”“3只狼”拆成 (数量, 基础名)。"""
    s = str(name or "").strip()
    m = re.match(r"^(\d+)\s*[个只名位]?\s*(.+)$", s)
    if m:
        try:
            count = max(1, int(m.group(1)))
            return count, m.group(2).strip()
        except Exception:
            pass
    m = re.match(r"^([一二两三四五六七八九十])\s*[个只名位]?\s*(.+)$", s)
    if m:
        count = _CN_NUM.get(m.group(1), 1)
        return count, m.group(2).strip()
    return 1, s



def _derive_npc_stats(n: dict) -> tuple[int, int, int]:
    """根据重要性/角色关键词为非完整NpcEntry推导合理数值，避免全是 hp10/ac10。"""
    importance = str(n.get("importance", "minor") or "minor")
    role = str(n.get("role", "") or "")
    text = f"{role} {str(n.get('name', ''))}"
    level = int(n.get("level", 1) or 1)
    if level <= 1:
        level = 3 if importance == "major" else (2 if any(k in text for k in ("卫兵", "士兵", "强盗", "战士", "圣武士", "法师")) else 1)
    ac = int(n.get("ac", 0) or 0)
    if ac <= 0:
        ac = 14 if importance == "major" else 12
        if any(k in text for k in ("战士", "圣武士", "卫兵", "骑士", "重甲")):
            ac = max(ac, 15)
        elif any(k in text for k in ("法师", "学者", "商人", "平民")):
            ac = max(ac, 11)
    hp = int(n.get("hp", 0) or 0)
    if hp <= 0:
        hp = 30 if importance == "major" else 20
        hp = max(hp, level * 4 + 8)
    max_hp = int(n.get("max_hp", 0) or 0)
    if max_hp <= 0:
        max_hp = hp
    return max(1, level), ac, hp, max_hp



def _enrich_creature_from_bestiary(creature: dict, bestiary: list[dict]) -> dict:
    """生成生物前先查图鉴：若已有同名生物，优先采用图鉴中的属性/描述/标签。"""
    if not bestiary or not isinstance(creature, dict):
        return creature
    name = str(creature.get("name", "") or "").strip()
    if not name:
        return creature
    base = _parse_creature_count(name)[1] or name
    found = None
    for b in bestiary:
        bname = str(b.get("name", "") or "").strip()
        if bname == name or bname == base:
            found = b
            break
    if found is None:
        for b in bestiary:
            bname = str(b.get("name", "") or "").strip()
            if base and (base in bname or bname in base):
                found = b
                break
    if found is None:
        return creature
    merged = dict(creature)
    stats = dict(creature.get("stats") or {})
    for k, v in (found.get("stats") or {}).items():
        if not stats.get(k):
            stats[k] = v
    merged["stats"] = stats
    if not merged.get("description") and found.get("description"):
        merged["description"] = found["description"]
    if not merged.get("tags") and found.get("tags"):
        merged["tags"] = found["tags"]
    if not merged.get("image_path") and found.get("image_path"):
        merged["image_path"] = found["image_path"]
    merged["bestiary_source"] = found.get("name", base)
    return merged



def _normalize_creature(creature: dict, index: int) -> list[dict]:
    """规范化生成生物：拆分“两个地精”等复合名称，并补齐缺失属性。"""
    name = str(creature.get("name", "") or "").strip()
    count, base = _parse_creature_count(name)
    stats = dict(creature.get("stats") or {})
    level = 2
    try:
        level = max(1, int(stats.get("等级") or stats.get("level") or creature.get("level") or 2))
    except Exception:
        level = 2
    if not stats.get("HP") and not stats.get("hp"):
        stats["HP"] = str(max(12, level * 6))
    if not stats.get("AC") and not stats.get("ac"):
        stats["AC"] = str(min(22, 10 + level // 2))
    if not stats.get("速度") and not stats.get("speed"):
        stats["速度"] = "6"
    for k in ("力量", "敏捷", "体质", "智力", "感知", "魅力"):
        if not stats.get(k):
            stats[k] = "10"
    out = []
    real_count = min(count or 1, 12)
    for i in range(real_count):
        out.append({
            **(creature or {}),
            "name": base if real_count == 1 else f"{base}{i + 1}",
            "stats": stats,
            "quantity": real_count,
            "group_base": base,
            "group_index": i + 1,
        })
    return out
