"""特长差值同步：把 `feat_effects` 算出的"应得加值"落到角色卡上。

从 `feat_effects` 拆出（那边只留"读图鉴算加值"的纯函数）。这里关心的是**可重入**：
属性加值与最大生命都用"期望值 − 已应用值"的差值结算，记录在
`character_info["feat_attr_bonuses"]` / `["feat_hp_bonus"]` 里，所以

- 同一轮反复调用不会叠加；
- 升级后（健壮每级 +2）自动补上差额；
- `feats_remove` 修正记录时会把加值收回去。
"""
from __future__ import annotations

from backend.engine.feat_effects import catalog_entry, hp_bonus_total
from backend.engine.session import GameSessionState


def _sync_attributes(state: GameSessionState, info: dict, applied: dict) -> None:
    """按图鉴里声明的 attr_bonus 差值同步属性（上限 20）。"""
    desired: dict[str, int] = {}
    for feat in info.get("feats") or []:
        effect = catalog_entry(feat).get("effect") or {}
        try:
            bonus = int(effect.get("attr_bonus") or 0)
        except (TypeError, ValueError):
            continue
        if bonus <= 0:
            continue
        choice = ""
        if isinstance(feat, dict):
            choice = str(feat.get("attr_choice") or "")
        options = effect.get("attr_choice") or []
        if not choice and options:
            choice = str(options[0])
        if choice:
            desired[choice] = desired.get(choice, 0) + bonus

    previous = info.get("feat_attr_bonuses")
    previous = previous if isinstance(previous, dict) else {}
    attrs = info.setdefault("attributes", {})
    changed = False
    for key in set(desired) | {str(k) for k in previous}:
        delta = desired.get(key, 0) - int(previous.get(key, 0) or 0)
        if not delta:
            continue
        try:
            base = int(attrs.get(key, 10) or 10)
        except (TypeError, ValueError):
            base = 10
        attrs[key] = max(1, min(20, base + delta))
        changed = True
    if changed:
        applied["attributes"] = attrs
        info["feat_attr_bonuses"] = desired


def _sync_hp(state: GameSessionState, info: dict, applied: dict) -> None:
    """按 hp_bonus 的差值同步最大生命（升级后会长大，删特长会回落）。"""
    desired = hp_bonus_total(state)
    previous = int(info.get("feat_hp_bonus", 0) or 0)
    delta = desired - previous
    if not delta:
        return
    base_max = int(info.get("max_hp", 0) or 0)
    new_max = max(1, base_max + delta)
    info["max_hp"] = new_max
    hp = int(info.get("hp", 0) or 0)
    info["hp"] = max(0, min(new_max, hp + delta))
    info["feat_hp_bonus"] = desired
    applied["max_hp"] = new_max
    applied["hp"] = info["hp"]


def _record_choices(state: GameSessionState, changes: dict) -> None:
    """把 DM 在 feats_add 里选的 attr_choice 记到角色卡上，供差值同步使用。"""
    payload = changes.get("feats_add")
    entries = payload if isinstance(payload, list) else [payload]
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        choice = str(entry.get("attr_choice") or "")
        if not choice:
            continue
        name = str(entry.get("name") or entry.get("id") or "")
        for feat in state.character_info.get("feats") or []:
            if not isinstance(feat, dict):
                continue
            if name and name not in (str(feat.get("name") or ""), str(feat.get("id") or "")):
                continue
            feat["attr_choice"] = choice


async def sync(state: GameSessionState, changes: dict, applied: dict) -> None:
    """把特长带来的属性/最大生命差值落到角色卡；幂等，可每轮调用。"""
    info = getattr(state, "character_info", None)
    if not isinstance(info, dict):
        return
    _record_choices(state, changes or {})
    _sync_attributes(state, info, applied)
    _sync_hp(state, info, applied)


__all__ = ["sync"]
