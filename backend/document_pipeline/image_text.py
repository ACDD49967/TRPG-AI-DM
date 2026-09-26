"""图片上下文解析：图注/正文里抽取实体名与数值，判断图片类别。

从 `backend/document_pipeline/image_processor.py` 拆出（那边只留抽取与登记）。
"""
from __future__ import annotations

import re


_MIN_WIDTH = 180
_MIN_HEIGHT = 180
_MAX_IMAGES_PER_PAGE = 12
_BESTIARY_KEYWORDS = re.compile(
    r"怪物库|生物图鉴|图鉴|怪物|生物|怪兽|Monster|Creature|Bestiary", re.I
)
_IMAGE_EXT = {1: "png", 2: "jpeg", 3: "jpeg", 4: "gif", 5: "png", 6: "bmp"}


def _context_from_page(page_text: str, limit: int = 500) -> str:
    """保留换行地提取页面上下文，便于识别实体名称与属性。"""
    lines = []
    for line in (page_text or "").split("\n"):
        s = re.sub(r"\s+", " ", line).strip()
        if s:
            lines.append(s)
    return "\n".join(lines)[:limit]


def _is_header_line(line: str) -> bool:
    if re.search(r"怪物库|生物图鉴|图鉴|目录|Contents|目\s*录|第\s*\d+\s*页/共|页面", line, re.I):
        return True
    if re.match(r"^\s*[0-9]+\s*$", line):
        return True
    return False


def _clean_entity_name(raw: str) -> str:
    s = re.sub(r"\s+", " ", raw or "").strip()
    # 去掉常见上下文尾缀
    s = re.split(r"(?:图片|图片来源|出自|来自|图鉴|怪物库|，|,|；|;)", s)[0]
    s = s.strip(" :：·.-—")
    if len(s) > 40:
        s = s[:40]
    return s


def _extract_entity_name(context: str, caption: str, page_no: int, kind: str = "bestiary") -> str:
    """从页面上下文/图注中提取更准确的实体名。"""
    lines = [re.sub(r"\s+", " ", x).strip() for x in (context or "").split("\n") if x.strip()]
    candidates = []
    if caption:
        candidates.append(caption)
    candidates.extend(lines)

    for cand in candidates:
        s = re.sub(r"\s+", " ", cand or "").strip()
        if not s or _is_header_line(s):
            continue
        # “名字 LVxx 角色” 形式
        m = re.match(r"^(.+?)\s+LV\s*\d+", s, re.I)
        if m:
            name = _clean_entity_name(m.group(1))
            if name:
                return name
        # “名字（英文/别名/类型）” 形式
        m = re.match(r"^(.+?)[（(]", s)
        if m:
            name = _clean_entity_name(m.group(1))
            if name:
                return name
        # 去掉常见前缀后第一段
        name = _clean_entity_name(s)
        if name and not _is_header_line(name):
            return name
    return f"{'怪物' if kind == 'bestiary' else '地图'}图谱第{page_no}页"


def _extract_stats_from_context(context: str) -> dict[str, str]:
    """从页面文本中尽力提取生物属性，供图谱/图鉴使用。"""
    text = re.sub(r"\s+", " ", context or "")
    lines = [re.sub(r"\s+", " ", x).strip() for x in (context or "").split("\n") if x.strip()]
    stats: dict[str, str] = {}
    hp = re.search(r"HP\s*[:：]?\s*(\d+)", text, re.I)
    if hp:
        stats["HP"] = hp.group(1)
    ac = re.search(r"AC\s*[:：]?\s*(\d+)", text, re.I)
    if ac:
        stats["AC"] = ac.group(1)
    speed = re.search(r"速度\s*[:：]?\s*(\d+)", text)
    if speed:
        stats["速度"] = speed.group(1)
    level = re.search(r"LV\s*(\d+)", text, re.I)
    if level:
        stats["等级"] = level.group(1)
    # 角色类型只取同一行中 LV 之后的短片段，避免把后续属性吸进 name/role
    for line in lines:
        m = re.search(r"LV\s*\d+\s*([^\n]*)", line, re.I)
        if m:
            role = m.group(1).strip()
            role = re.split(r"\s+(?:HP|AC|速度|力量|敏捷|感知|体质|智力|魅力|XP|等级)\s*[:：]?", role, flags=re.I)[0]
            role = role.strip(" :：·.-—")
            if role:
                stats["角色类型"] = role[:40]
            break
    # 六维属性（D&D 4e 怪物卡常见排列）
    attrs = re.search(
        r"力量\s*(\d+).*?敏捷\s*(\d+).*?感知\s*(\d+).*?体质\s*(\d+).*?智力\s*(\d+).*?魅力\s*(\d+)",
        text, re.S,
    )
    if attrs:
        stats["力量"] = attrs.group(1)
        stats["敏捷"] = attrs.group(2)
        stats["感知"] = attrs.group(3)
        stats["体质"] = attrs.group(4)
        stats["智力"] = attrs.group(5)
        stats["魅力"] = attrs.group(6)
    return stats


def detect_image_type(context: str) -> str:
    if _BESTIARY_KEYWORDS.search(context):
        return "bestiary"
    if re.search(r"地图|Map|区域图|地形图", context, re.I):
        return "map"
    if re.search(r"物品|道具|Item", context, re.I):
        return "item"
    return "other"
