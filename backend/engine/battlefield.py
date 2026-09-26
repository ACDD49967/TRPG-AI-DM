"""战场态势门面：按会话状态读写每个单位的档位与掩体，并再导出规则模型。

按职责拆三段（`dm_turn` / `combat` / `tool_executor` 的 import 面不变）：
- `battlefield_rules`：档位/掩体表与 Placement、Battlefield
- `battlefield_actions`：preflight_attack、set_tactical_state 处理器、提示注入
- 本模块：field_for / band_of / cover_of / set_placement / summary / payload / clear 等门面
"""
from __future__ import annotations

from typing import Any

from backend.engine.battlefield_rules import (  # noqa: F401
    BANDS, BAND_HINT, COVERS, MELEE_BANDS, Battlefield, Placement, _BAND_ALIASES,
    _COVER_ALIASES, can_be_targeted, cover_ac_bonus, cover_dex_bonus, hp_ratio,
    melee_reachable, normalize_band, normalize_cover, normalize_name,
    provokes_opportunity,
)


def field_for(state: Any) -> Battlefield:
    field_obj = getattr(state, "battlefield", None)
    if not isinstance(field_obj, Battlefield):
        field_obj = Battlefield()
        try:
            state.battlefield = field_obj
        except Exception:
            pass
    return field_obj


def placement_of(state: Any, name: Any) -> Placement | None:
    return field_for(state).get(state, name)


def band_of(state: Any, name: Any, default: str = "") -> str:
    place = placement_of(state, name)
    return (place.band if place and place.band else default)


def cover_of(state: Any, name: Any, default: str = "") -> str:
    place = placement_of(state, name)
    return (place.cover if place and place.cover else default)


def ac_bonus_from_cover(state: Any, defender: Any, ignore_cover: bool = False) -> int:
    if ignore_cover:
        return 0
    return cover_ac_bonus(cover_of(state, defender))


def dex_bonus_from_cover(state: Any, defender: Any, ignore_cover: bool = False) -> int:
    if ignore_cover:
        return 0
    return cover_dex_bonus(cover_of(state, defender))


def set_placement(state: Any, name: Any, band: Any = "", cover: Any = "",
                  note: str = "") -> tuple[Placement | None, str]:
    """写入/更新一个单位的态势；返回 (新态势, 借机攻击提示文本)。"""
    field_obj = field_for(state)
    old = field_obj.get(state, name)
    old_band = old.band if old else ""
    new_band = normalize_band(band) or old_band
    new_cover = normalize_cover(cover) or (old.cover if old else "")
    place = field_obj.set(state, name, new_band, new_cover, note)
    warning = ""
    if place and provokes_opportunity(old_band, new_band):
        warning = (f"{normalize_name(state, name)} 从缠斗脱离（{old_band}→{new_band}）："
                   f"仍与它缠斗的敌人可以借机攻击"
                   f"（用 enemy_attack + action_source=\"opportunity_attack\" 结算）。")
    return place, warning


def summary(state: Any) -> str:
    return field_for(state).summary()


def payload(state: Any) -> dict:
    """接口/前端用：各单位档位与掩体（含中文摘要）。"""
    field_obj = field_for(state)
    return {
        "places": [{"name": name, **place.to_dict()}
                   for name, place in field_obj.places.items()],
        "summary": field_obj.summary(),
    }


def clear(state: Any) -> None:
    try:
        state.battlefield = Battlefield()
    except Exception:
        pass


from backend.engine.battlefield_actions import (  # noqa: E402,F401
    _exec_set_tactical_state, _truthy, citations_for_hint, preflight_attack, replace_hint,
)
