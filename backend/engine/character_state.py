"""角色状态变更与派生值（从 dm_agent 拆出）。

职责：属性/资源/法术位/背包/职业资源的增量与赋值、状态效果（conditions）、专注、
濒死与死亡锁定、装备影响 AC 的重算、升级派生值。全部是确定性规则，不需要 AI 参与。

与 dm_agent 的关系：少数通用工具（_game_system、_exec_death_save）通过惰性 shim 调用，
避免循环导入；dm_agent 反向再导出本模块的名字，保持既有调用方不变。
"""
from __future__ import annotations

import json
import re
from typing import Any

from backend.engine.rules import DeathSaves
from backend.engine.session import GameSessionState, push_event
from backend.engine.tool_shims import _game_system

# 玩家侧伤害特性字段（player_damage 管线读取）
_DAMAGE_TRAIT_FIELDS = ("damage_resistances", "damage_immunities",
                        "damage_vulnerabilities", "damage_traits")


async def _exec_death_save(args: dict, state: Any) -> str:
    from backend.engine import dm_agent
    return await dm_agent._exec_death_save(args, state)


async def _exec_update_state(args: dict, state: GameSessionState) -> str:
    changes = args.get("changes", {})
    reason = args.get("reason", "")
    info = state.character_info
    applied: dict = {}
    hp_before = int(info.get("hp", 0) or 0)
    san_before = int(info.get("san", 0) or 0)
    luck_before = int(info.get("luck", 0) or 0)

    # 装备类变更前先把"基准 AC"（不含护甲/盾牌加值）固定下来。
    # _recalc_equipment_effects 是在变更之后才算 base_ac 的，那一刻新装备已经生效，
    # 于是 base_ac = 当前AC - 新加成，把这次的加成抹平：装盾牌不涨 AC，
    # 卸下还会按"基准缺失"永久掉 2 点。基准必须在动手之前取。
    if "base_ac" not in info and any(str(k).startswith("inventory") for k in changes):
        info["base_ac"] = int(info.get("ac") or 10) - _equipped_armor_bonus(info, state)

    # 支持各规则系统的通用数值字段（delta 更新）
    numeric_delta_fields = {
        "hp", "max_hp", "mp", "max_mp", "san", "max_san", "luck",
        "healing_surges", "max_healing_surges", "spell_points",
        "power_encounter", "power_daily", "temporary_hp",
    }
    direct_set_fields = {"gold", "level", "ac", "proficiency_bonus"}

    for k, v in changes.items():
        if k == "spell_slots":
            # 法术位是完整剩余值（数组或 {spell_slots:[...], pact_slots:n}），
            # 合并与"按职业/等级封顶"都在 spell_slots 模块里做
            from backend.engine.spell_slots import apply_spell_slots_change

            current = apply_spell_slots_change(state, info.get("spell_slots"), v)
            info["spell_slots"] = current
            applied["spell_slots"] = current
        elif k in numeric_delta_fields:
            min_val = 0
            max_key = None
            if k.startswith("max_"):
                min_val = 1
            elif k in ("hp", "mp", "san", "healing_surges", "spell_points", "temporary_hp"):
                max_key = "max_" + k if k != "temporary_hp" else None
            if max_key:
                current = info.get(k, 0) + v
                current = max(min_val, min(info.get(max_key, current), current))
            else:
                current = max(min_val, info.get(k, 0) + v)
            if k == "luck":
                current = clamp_luck(state, current)
            info[k] = current
            applied[k] = current
        elif k in direct_set_fields:
            info[k] = max(0, int(v))
            applied[k] = info[k]
        elif k == "xp":
            info["xp"] = max(0, info.get("xp", 0) + v)
            applied["xp"] = info["xp"]
            # 自动升级（仅 dnd 系适用；COC/自定义不强行套用）
            if _game_system(state) in ("dnd5e", "dnd4e"):
                from backend.engine.game_systems import get_level_from_xp
                old_level = info.get("level", 1)
                new_level = get_level_from_xp(info["xp"], _game_system(state))
                if new_level > old_level:
                    info["level"] = new_level
                    applied["level"] = new_level
                    con = int(info.get("attributes", {}).get("con", 10) or 10)
                    cc = info.get("char_class", "战士")
                    attrs = info.get("attributes", {})
                    if _game_system(state) == "dnd5e":
                        from backend.engine.game_systems import (
                            DND5_CLASS_HD, get_dnd5_class_resources,
                            get_dnd5_proficiency_bonus, get_dnd5_saves,
                            get_dnd5_spell_slots, get_passive_perception,
                        )
                        hd = DND5_CLASS_HD.get(cc, 8)
                        hp_gain = max(1, (hd + 1) // 2 + (con - 10) // 2)
                        info["hit_die"] = f"{new_level}d{hd}"
                        info["max_hp"] = info.get("max_hp", hd + (con - 10) // 2) + hp_gain
                        info["hp"] = min(info["max_hp"], info.get("hp", 0) + hp_gain)
                        applied["max_hp"] = info["max_hp"]
                        prof = get_dnd5_proficiency_bonus(new_level)
                        info["proficiency_bonus"] = prof
                        info["saves"] = get_dnd5_saves(cc, attrs, prof)
                        info["passive_perception"] = get_passive_perception(
                            attrs, prof, info.get("skill_proficiencies", []))
                        info["class_resources"] = get_dnd5_class_resources(cc, attrs, new_level)
                        if cc in ("法师", "牧师", "吟游诗人", "德鲁伊", "术士", "圣武士", "游侠", "邪术师"):
                            info["spell_slots"] = get_dnd5_spell_slots(cc, new_level)
                        applied.update({
                            "proficiency_bonus": prof, "saves": info["saves"],
                            "passive_perception": info["passive_perception"],
                            "class_resources": info["class_resources"],
                        })
                        if "spell_slots" in info:
                            applied["spell_slots"] = info["spell_slots"]
                    else:
                        from backend.engine.game_systems import DND4_CLASS_HP
                        hp_gain = DND4_CLASS_HP.get(cc, 12)
                        info["max_hp"] = info.get("max_hp", 12 + (con - 10) // 2) + hp_gain
                        info["hp"] = min(info["max_hp"], info.get("hp", 0) + hp_gain)
                        applied["max_hp"] = info["max_hp"]
                    # 5e 属性提升/专长等级：多数职业 4/8/12/16/19（战士另有 6/14，游荡者 10）
                    if _game_system(state) == "dnd5e":
                        from backend.engine.game_systems import get_dnd5_asi_levels
                        asi_levels = get_dnd5_asi_levels(cc)
                    else:
                        asi_levels = []
                    if new_level in asi_levels:
                        await push_event(state, "game_event", {
                            "type": "feat_available",
                            "description": (
                                f"🎯 升至{new_level}级：可以进行属性提升"
                                f"（单项 +2 或两项各 +1，上限 20），或改为选择一项专长。"
                            ),
                            "extra": {"level": new_level, "kind": "asi_or_feat"},
                        })
        elif k.startswith("class_resource:"):
            # 职业资源增减：如 class_resource:ki_points: -1，或 {"current": 0, "max": 5}
            res_key = k.split(":", 1)[1]
            res_list = info.setdefault("class_resources", [])
            entry = next((r for r in res_list if isinstance(r, dict) and r.get("key") == res_key), None)
            if entry is None:
                entry = {"key": res_key, "name": res_key, "current": 0, "max": 0, "desc": ""}
                res_list.append(entry)
            if isinstance(v, dict):
                if "current" in v:
                    entry["current"] = max(0, min(entry.get("max", v.get("current", 0)), int(v["current"])))
                if "max" in v:
                    entry["max"] = max(0, int(v["max"]))
                    entry["current"] = min(entry.get("current", 0), entry["max"])
                if "name" in v:
                    entry["name"] = str(v["name"])
            else:
                delta = int(v)
                cap = entry.get("max", 0)
                current = max(0, entry.get("current", 0) + delta)
                if cap > 0:
                    current = min(cap, current)
                entry["current"] = current
            applied["class_resources"] = res_list
        elif k == "action_points":
            current = max(0, min(3, info.get("action_points", 1) + int(v)))
            info["action_points"] = current
            applied["action_points"] = current
        elif k == "spells_known_add":
            spells = info.setdefault("known_spells", [])
            spell = _normalize_spell(v)
            if not any((s.get("name") if isinstance(s, dict) else s) == spell["name"] for s in spells):
                spells.append(spell)
            applied["known_spells"] = spells
        elif k == "spells_known_remove":
            spells = info.setdefault("known_spells", [])
            name = v if isinstance(v, str) else (v.get("name") if isinstance(v, dict) else str(v))
            spells[:] = [s for s in spells if (s.get("name") if isinstance(s, dict) else s) != name]
            applied["known_spells"] = spells
        elif k in _DAMAGE_TRAIT_FIELDS or (
            k.rsplit("_", 1)[0] in _DAMAGE_TRAIT_FIELDS and k.endswith(("_add", "_remove"))
        ):
            # 玩家侧抗性/免疫/易伤：结构化字段（player_damage 管线读取；比塞在描述文本里可靠）
            base = k.rsplit("_", 1)[0] if k.endswith(("_add", "_remove")) else k
            values = v if isinstance(v, list) else [v]
            cleaned = [str(x).strip() for x in values if str(x).strip()]
            if k.endswith("_add"):
                current = list(info.get(base) or [])
                for item in cleaned:
                    if item not in current:
                        current.append(item)
                info[base] = current
            elif k.endswith("_remove"):
                info[base] = [x for x in (info.get(base) or []) if x not in cleaned]
            else:
                info[base] = cleaned
            applied[base] = info[base]
        elif k == "feats_add":
            # 升级到偶数级会提示选择新特长，此前没有任何写入通道（提示是一条死链）
            feats = info.setdefault("feats", [])
            incoming = v if isinstance(v, list) else [v]
            for raw_feat in incoming:
                if isinstance(raw_feat, dict):
                    feat = {
                        "id": str(raw_feat.get("id") or raw_feat.get("name") or ""),
                        "name": str(raw_feat.get("name") or raw_feat.get("id") or "新特长"),
                        "description": str(raw_feat.get("description") or ""),
                    }
                else:
                    feat = {"id": str(raw_feat), "name": str(raw_feat), "description": ""}
                if not feat["name"]:
                    continue
                if not any((f.get("name") if isinstance(f, dict) else f) == feat["name"] for f in feats):
                    feats.append(feat)
            info["feats"] = feats
            applied["feats"] = feats
        elif k == "feats_remove":
            feats = info.setdefault("feats", [])
            name = v if isinstance(v, str) else (v.get("name") if isinstance(v, dict) else str(v))
            info["feats"] = [f for f in feats if (f.get("name") if isinstance(f, dict) else f) != name]
            applied["feats"] = info["feats"]
        elif k == "concentration_clear":
            previous = info.pop("concentration", None)
            if isinstance(previous, dict) and previous.get("spell"):
                applied["concentration_cleared"] = previous["spell"]
            applied["concentration"] = None
        elif k == "exhaustion":
            # 5e 力竭：0-6 级。1/3 级由掷骰侧强制（dice_tools / combat_save_damage），
            # 4 级生命上限减半、6 级死亡在这里落数值（实现见 exhaustion_effects）。
            current = int(info.get("exhaustion", 0) or 0)
            info["exhaustion"] = max(0, min(6, current + int(v or 0)))
            applied["exhaustion"] = info["exhaustion"]
            from backend.engine.exhaustion_effects import apply_exhaustion_effects
            applied.update(apply_exhaustion_effects(state, info))
        elif k in ("conditions_add", "conditions_remove"):
            changed = _update_conditions(
                state,
                changes.get("conditions_add") if k == "conditions_add" else None,
                changes.get("conditions_remove") if k == "conditions_remove" else None,
            )
            applied["conditions"] = changed["conditions"]
            if changed["added"]:
                applied["conditions_added"] = changed["added"]
            if changed["removed"]:
                applied["conditions_removed"] = changed["removed"]
            if changed.get("blocked"):
                applied["conditions_blocked"] = changed["blocked"]
        elif k == "attributes_add":
            # 属性提升（ASI）：单项 +2 或两项各 +1；5e 属性上限 20
            attrs = info.setdefault("attributes", {})
            changed = False
            for key, delta in (v or {}).items() if isinstance(v, dict) else []:
                try:
                    dv = int(delta)
                except (TypeError, ValueError):
                    continue
                if not dv:
                    continue
                attrs[key] = max(1, min(20, int(attrs.get(key, 10) or 10) + dv))
                changed = True
            if changed:
                info["attributes"] = attrs
                applied["attributes"] = attrs
                if _game_system(state) == "dnd5e":
                    from backend.engine.game_systems import (
                        get_dnd5_proficiency_bonus, get_dnd5_saves, get_passive_perception,
                    )
                    prof = int(info.get("proficiency_bonus")
                               or get_dnd5_proficiency_bonus(info.get("level", 1)))
                    info["saves"] = get_dnd5_saves(info.get("char_class", ""), attrs, prof)
                    info["passive_perception"] = get_passive_perception(
                        attrs, prof, info.get("skill_proficiencies", []))
                    applied["saves"] = info["saves"]
                    applied["passive_perception"] = info["passive_perception"]
                _recalc_equipment_effects(state, applied)
        elif k == "inventory_add":
            items = info.setdefault("inventory", {}).setdefault("items", [])
            item = _normalize_item(v)
            if not any((i.get("name") if isinstance(i, dict) else i) == item["name"] for i in items):
                items.append(item)
            applied["inventory"] = {"items": items}
        elif k == "inventory_remove":
            items = info.setdefault("inventory", {}).setdefault("items", [])
            name = v if isinstance(v, str) else (v.get("name") if isinstance(v, dict) else str(v))
            items[:] = [i for i in items if (i.get("name") if isinstance(i, dict) else i) != name]
            applied["inventory"] = {"items": items}
        elif k == "inventory_update":
            # 物品"改"：按 name 命中后就地合并字段；new_name 支持改名。
            # 与 inventory_add 的区别是 add 只在不存在时追加，改描述/数量/类型要靠这里。
            items = info.setdefault("inventory", {}).setdefault("items", [])
            payload = dict(v) if isinstance(v, dict) else {"name": str(v)}
            target = str(payload.get("name") or "").strip()
            updates = {key: val for key, val in payload.items() if key != "name"}
            new_name = str(updates.pop("new_name", "") or "").strip()
            for index, entry in enumerate(items):
                entry_name = entry.get("name") if isinstance(entry, dict) else str(entry)
                if entry_name != target:
                    continue
                base = dict(entry) if isinstance(entry, dict) else {"name": str(entry)}
                merged = _normalize_item({**base, **updates})
                if new_name:
                    merged["name"] = new_name
                items[index] = merged
                break
            applied["inventory"] = {"items": items}
        elif k in ("inventory_equip", "inventory_unequip"):
            items = info.setdefault("inventory", {}).setdefault("items", [])
            name = v if isinstance(v, str) else (v.get("name") if isinstance(v, dict) else str(v))
            equip = (k == "inventory_equip")
            found = False
            for i, it in enumerate(items):
                item_name = it.get("name") if isinstance(it, dict) else str(it)
                if item_name == name:
                    if isinstance(it, dict):
                        it["equipped"] = equip
                    else:
                        items[i] = _normalize_item({"name": it, "equipped": equip})
                    found = True
                    break
            if found:
                _recalc_equipment_effects(state, applied)
                applied["inventory"] = {"items": items}

    # 装备变化后统一重算 AC（防止只改 inventory 不更新状态）
    if any(str(k).startswith("inventory") for k in changes):
        _recalc_equipment_effects(state, applied)

    if applied:
        # 特长被动（属性/最大生命）先算进 applied，前端与后续规则才能看到同一个数
        from backend.engine.feat_sync import sync as sync_feat_effects

        await sync_feat_effects(state, changes, applied)
        await push_event(state, "state_update", applied)
        await _handle_dying_transition(state, hp_before, int(info.get("hp", 0) or 0))
        await handle_sanity_change(state, san_before, int(info.get("san", 0) or 0))
        await handle_luck_change(state, luck_before, int(info.get("luck", 0) or 0))
        await handle_hp_threshold(state, hp_before, int(info.get("hp", 0) or 0))
    return f"状态更新 ({reason}): {json.dumps(applied, ensure_ascii=False)}"


# 拆出的辅助函数在这里再导出，既有 import（dm_agent / tests）不变
from backend.engine.character_conditions import _update_conditions, tick_conditions  # noqa: E402,F401
from backend.engine.character_dying import _handle_dying_transition, _maybe_auto_death_save  # noqa: E402,F401
from backend.engine.sanity_rules import handle_sanity_change  # noqa: E402
from backend.engine.luck_rules import clamp_luck, handle_luck_change  # noqa: E402,F401
from backend.engine.bloodied import handle_hp_threshold  # noqa: E402,F401
from backend.engine.character_equipment import (  # noqa: E402,F401
    _ARMOR_AC_BONUS, _equipped_armor_bonus, _recalc_equipment_effects,
)
from backend.engine.character_normalize import (  # noqa: E402,F401
    _format_condition, _has_feat_effect, _normalize_condition, _normalize_item, _normalize_spell,
)
