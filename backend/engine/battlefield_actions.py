"""攻击预检与态势工具：掩体/距离拦截、提示注入与 set_tactical_state 处理器。

从 `backend/engine/battlefield.py` 拆出。
"""
from __future__ import annotations

from typing import Any, Iterable

from backend.engine.battlefield_rules import (
    BANDS, BAND_HINT, COVERS, can_be_targeted, melee_reachable, normalize_band,
    normalize_cover, normalize_name,
)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in ("1", "true", "yes", "y", "是", "真")


def preflight_attack(state: Any, tool_name: str, args: dict) -> str:
    """攻击类工具的前置校验（在消耗行动之前调用）。

    返回空串表示放行，否则返回给 DM/玩家的说明文本。
    这样"够不到/全掩体"不会白白吃掉本回合的主行动。
    """
    # 状态门面在 battlefield.py，而它又再导出本模块 → 用函数内 import 避免模块级环
    from backend.engine.battlefield import band_of, cover_of

    args = args or {}
    if tool_name == "combat_round":
        target = str(args.get("enemy_name") or "")
        if not target:
            return ""
        band = normalize_band(args.get("target_band")) or band_of(state, target)
        cover = normalize_cover(args.get("target_cover")) or cover_of(state, target)
        if not can_be_targeted(cover):
            return (f"⚠ {target} 正处于全掩体后，无法直接攻击。可以让它探头/移动后再攻，"
                    f"或用 set_tactical_state 更新它的掩体等级；也可以改打别的目标。")
        if not melee_reachable(band) and not _truthy(args.get("close_distance")):
            label, dist = BANDS.get(band, ("较远", "超出近战距离"))
            return (f"⚠ {target} 目前处于{label}（{dist}），近战够不到。"
                    f"请先声明 close_distance=true 冲上去（本回合移动），"
                    f"或改用远程/法术手段；也可以用 set_tactical_state 更新档位。")
        return ""
    if tool_name == "enemy_attack":
        if str(args.get("action_source") or "").lower() == "opportunity_attack":
            return ""      # 借机攻击是反应，不受距离限制
        player = normalize_name(state, "你") or "玩家"
        band = normalize_band(args.get("player_band")) or band_of(state, player)
        cover = normalize_cover(args.get("player_cover")) or cover_of(state, player)
        if not can_be_targeted(cover):
            return (f"⚠ {player} 正处于全掩体后，无法直接攻击。"
                    f"请改用范围手段、逼迫其离开掩体，或更新态势。")
        if not melee_reachable(band) and not _truthy(args.get("close_distance")):
            label, dist = BANDS.get(band, ("较远", "超出近战距离"))
            return (f"⚠ {player} 已在{label}（{dist}），近战够不到。"
                    f"请声明 close_distance=true 让其接近，或改用远程/投掷攻击。")
        return ""
    return ""


def replace_hint(state: Any, text: str) -> None:
    """把态势提示写进待注入队列（替换同前缀旧提示）。"""
    if not text:
        return
    hints = getattr(state, "pending_system_hints", None)
    if hints is None:
        return
    kept = [h for h in hints if not str(h).startswith(BAND_HINT)]
    kept.append(text)
    state.pending_system_hints = kept


async def _exec_set_tactical_state(args: dict, state: Any) -> str:
    """工具：登记战场态势（距离档位 / 掩体）。支持单个 combatant 或 placements 列表。"""
    from backend.engine.session import push_event
    from backend.engine.battlefield import set_placement, summary

    entries: list[dict] = []
    if isinstance(args.get("placements"), list):
        entries = [e for e in args["placements"] if isinstance(e, dict)]
    if args.get("combatant") or args.get("name"):
        entries.append({
            "combatant": args.get("combatant") or args.get("name"),
            "band": args.get("band"), "cover": args.get("cover"), "note": args.get("note"),
        })
    if not entries:
        return ("⚠ set_tactical_state 需要 combatant（或 placements 列表）；"
                f"band 可选 engaged/near/far/out，cover 可选 none/half/three_quarters/full。"
                f" 当前：{summary(state)}")

    lines: list[str] = []
    warnings: list[str] = []
    changed: list[dict] = []
    for entry in entries:
        name = str(entry.get("combatant") or entry.get("name") or "").strip()
        if not name:
            continue
        place, warning = set_placement(
            state, name, entry.get("band"), entry.get("cover"), str(entry.get("note") or ""))
        if place is None:
            continue
        band_label = BANDS.get(place.band, ("未记录", ""))[0]
        cover_label = COVERS.get(place.cover, ("未记录", 0))[0]
        lines.append(f"- {normalize_name(state, name)}：{band_label} / {cover_label}"
                     + (f"（{place.note}）" if place.note else ""))
        if warning:
            warnings.append(warning)
        changed.append({"name": normalize_name(state, name), "band": place.band,
                        "cover": place.cover, "note": place.note})

    text = "🗺️ 战场态势已更新：\n" + "\n".join(lines)
    if warnings:
        text += "\n" + "\n".join(warnings)
        replace_hint(state, BAND_HINT + " " + citations_for_hint(warnings))
    await push_event(state, "game_event", {
        "type": "battlefield",
        "description": text,
        "extra": {"placements": changed, "warnings": warnings},
    })
    return text


def citations_for_hint(warnings: Iterable[str]) -> str:
    return "；".join(str(w) for w in warnings)
