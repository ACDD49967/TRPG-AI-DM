"""内容库卡片渲染与查询：图鉴/地点卡片的格式化与 get_*_card 处理器。

从 `media_tools` 拆出（那边只留门面与再导出）。
"""
from __future__ import annotations

from backend.engine.combat import _find_bestiary_card
from backend.engine.session import GameSessionState

def _format_bestiary_card(item: dict) -> str:
    stats = item.get("stats") or {}
    details = item.get("details") or {}
    lines = [
        f"### {item.get('name','未知生物')}",
        f"类型: {item.get('system','')} | 标签: {'、'.join(item.get('tags') or []) or '无'}",
        f"描述: {str(item.get('description',''))[:300]}",
    ]
    stat_lines = []
    for key in ("AC", "HP", "速度", "力量", "敏捷", "体质", "智力", "感知", "魅力", "技能", "感官", "语言", "挑战等级", "豁免", "特性", "动作"):
        if stats.get(key):
            stat_lines.append(f"{key}: {stats[key]}")
    if stat_lines:
        lines.append("数值: " + " | ".join(stat_lines))
    detail_lines = []
    for key, label in (("habits", "习性"), ("habitat", "栖息地"), ("lore", "传说"), ("weakness", "弱点")):
        if details.get(key):
            detail_lines.append(f"{label}: {details[key]}")
    if detail_lines:
        lines.append("详情: " + "；".join(detail_lines))
    return "\n".join(lines)


async def _exec_get_bestiary_card(args: dict, state: GameSessionState) -> str:
    name = str(args.get("name", "")).strip()
    if not name:
        return "⚠ 需要 name"
    item = _find_bestiary_card(state, name)
    if item is None:
        return f"图鉴中未找到生物: {name}"
    return _format_bestiary_card(item)


def _format_location_card(item: dict) -> str:
    details = item.get("details") or {}
    lines = [
        f"### {item.get('name','未知地点')}",
        f"描述: {str(item.get('description',''))[:300]}",
    ]
    detail_lines = []
    for key, label in (("type", "类型"), ("status", "状态"), ("culture", "文化/势力"),
                       ("notable_figures", "知名人物"), ("dangers", "危险"), ("secret", "秘密")):
        if details.get(key):
            detail_lines.append(f"{label}: {details[key]}")
    if details.get("districts"):
        detail_lines.append(f"区域: {'、'.join(details['districts'])}")
    if item.get("locations"):
        detail_lines.append(f"子地点: {'、'.join(str(l.get('name','')) for l in item['locations'])}")
    if detail_lines:
        lines.append("详情: " + "；".join(detail_lines))
    return "\n".join(lines)


async def _exec_get_location_card(args: dict, state: GameSessionState) -> str:
    name = str(args.get("name", "")).strip()
    if not name:
        return "⚠ 需要 name"
    from backend.media_manager import list_maps
    scenario_id = state.character_info.get("scenario_id", "") or ""
    items = list_maps(state.username or "default", scenario_id or None)
    # 先找当前剧本自己的地点，再回退通用参考。
    for item in items:
        if str(item.get("scenario_id") or "") == scenario_id and (item.get("name") == name or item.get("id") == name):
            return _format_location_card(item)
    for item in items:
        if not str(item.get("scenario_id") or "") and (item.get("name") == name or item.get("id") == name):
            return _format_location_card(item)
    return f"地点图鉴中未找到: {name}"
