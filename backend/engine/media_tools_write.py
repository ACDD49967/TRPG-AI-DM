"""内容库写入类工具：图鉴/城市条目的修改与"登记到当前剧本"。

从 `media_tools` 拆出（那边只留门面与再导出）。
"""
from __future__ import annotations

from backend.engine.session import GameSessionState, push_event
from backend.engine.tool_shims import _game_system

async def _exec_update_bestiary(args: dict, state: GameSessionState) -> str:
    name = args.get("name", "")
    changes = args.get("changes", {}) or {}
    reason = args.get("reason", "")
    state.bestiary_overrides[name] = {**state.bestiary_overrides.get(name, {}), **changes}
    return f"生物图鉴已临时更新: {name} ({reason})"


async def _exec_update_city(args: dict, state: GameSessionState) -> str:
    name = args.get("name", "")
    changes = args.get("changes", {}) or {}
    reason = args.get("reason", "")
    state.city_overrides[name] = {**state.city_overrides.get(name, {}), **changes}
    return f"城市/地点背景已临时更新: {name} ({reason})"


async def _exec_add_scenario_bestiary(args: dict, state: GameSessionState) -> str:
    from backend.media_manager import (
        add_bestiary, find_bestiary_exact, find_global_bestiary, update_bestiary,
    )
    username = state.username or "default"
    scenario_id = state.character_info.get("scenario_id", "") or ""
    name = str(args.get("name", "未命名生物"))
    # 只查找同作用域条目；同名通用图鉴不会被本工具改写。
    existing = find_bestiary_exact(username, scenario_id or None, name)
    if existing:
        item = update_bestiary(username, existing["id"], {
            "system": _game_system(state),
            "description": args.get("description", "") or "",
            "stats": args.get("stats") or {},
            "tags": args.get("tags") or [],
            "details": args.get("details") or {},
            "scenario_id": scenario_id,
        })
        action = "更新"
    else:
        # 从通用图鉴复制基础数值/图片，保证剧本副本也有图可显示。
        ref = find_global_bestiary(username, name) or {}
        ref_stats = dict(ref.get("stats") or {})
        ref_stats.update(args.get("stats") or {})
        item = add_bestiary(
            username=username,
            name=name,
            system=_game_system(state),
            description=args.get("description", "") or str(ref.get("description", "") or ""),
            stats=ref_stats,
            image_path=str(ref.get("image_path", "") or ""),
            tags=args.get("tags") or list(ref.get("tags", []) or []),
            details={**(ref.get("details") or {}), **(args.get("details") or {}), "source": "当前剧本"},
            scenario_id=scenario_id,
        )
        action = "新增"
    await push_event(state, "bestiary_updated", {})
    return f"✅ 已{action}当前剧本图鉴: {item['name']}"


async def _exec_add_scenario_map(args: dict, state: GameSessionState) -> str:
    from backend.media_manager import add_map, find_global_map, find_map_exact, update_map
    username = state.username or "default"
    scenario_id = state.character_info.get("scenario_id", "") or ""
    name = str(args.get("name", "未命名地图"))
    # 只查找同作用域条目；同名通用地图不会被本工具改写。
    existing = find_map_exact(username, scenario_id or None, name)
    if existing:
        item = update_map(username, existing["id"], {
            "description": args.get("description", "") or "",
            "locations": args.get("locations") or [],
            "system": _game_system(state),
            "details": args.get("details") or {},
            "scenario_id": scenario_id,
        })
        action = "更新"
    else:
        ref = find_global_map(username, name) or {}
        item = add_map(
            username=username,
            name=name,
            description=args.get("description", "") or str(ref.get("description", "") or ""),
            image_path=str(ref.get("image_path", "") or ""),
            locations=args.get("locations") or list(ref.get("locations", []) or []),
            system=_game_system(state),
            details={**(ref.get("details") or {}), **(args.get("details") or {}), "source": "当前剧本"},
            scenario_id=scenario_id,
        )
        action = "新增"
    await push_event(state, "maps_updated", {})
    return f"✅ 已{action}当前剧本地图: {item['name']}"
