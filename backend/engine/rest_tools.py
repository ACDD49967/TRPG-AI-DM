"""休息工具：5e 的生命骰短休、4e 的回复力短休与长休恢复。

从 session_tools 拆出：休息是独立的规则域（涉及 HP / 法术位 / 职业资源 / 回复力），
拆开后 session_tools 只留记忆、装备、死亡豁免与行动建议。
"""
from __future__ import annotations

from backend.engine.character_state import _exec_update_state
from backend.engine.feat_effects import min_hit_die_heal
from backend.engine.milestones import reset_encounters
from backend.engine.rules import short_rest
from backend.engine.session import GameSessionState, push_event
from backend.engine.tool_shims import _game_system


SHORT_REST_RESOURCE_KEYS = {"ki_points", "channel_divinity", "wild_shape", "second_wind", "action_surge", "arcane_recovery"}




async def _exec_rest(args: dict, state: GameSessionState) -> str:
    # 5e：短休 1 小时、长休 8 小时，战斗中不可能完成
    if getattr(state, "in_combat", False):
        return "⚠ 战斗中无法休息：请先脱离战斗（撤离、谈判或击退所有敌人）后再短休或长休。"
    rest_type = args.get("rest_type", "short")
    info = state.character_info
    hp, mhp = info.get("hp", 10), info.get("max_hp", 30)
    con_mod = (info.get("attributes", {}).get("con", 10) - 10) // 2
    level = info.get("level", 1)
    system = _game_system(state)

    if rest_type == "short":
        if system == "dnd4e":
            # 4e 短休靠消耗回复力：每次回复 = surge_value 点 HP，缺多少补多少、上限是剩余回复力。
            # 此前这里走的是 5e 的生命骰公式，导致回复力只涨不跌、短休恢复也用错了规则。
            from backend.engine import time_rules
            surge_value = int(info.get("surge_value", 0) or 0)
            have = int(info.get("healing_surges", 0) or 0)
            missing = max(0, int(mhp) - int(hp))
            if surge_value <= 0 or have <= 0 or missing <= 0:
                rested = await time_rules.advance(state, 60, "短休")
                return (f"🛌 短休: 没有消耗回复力（HP 已满，或回复力/单次回复量为 0）\n"
                        f"{rested['summary']}")
            used = min(have, max(1, (missing + surge_value - 1) // surge_value))
            healed = min(missing, used * surge_value)
            await _exec_update_state(
                {"changes": {"hp": healed, "healing_surges": -used},
                 "reason": "4e 短休（消耗回复力）"}, state)
            rested = await time_rules.advance(state, 60, "短休")
            return (f"🛌 短休: 消耗 {used} 点回复力，恢复 {healed} HP"
                    f"（每次回复 {surge_value} HP，剩余回复力 {have - used}）\n{rested['summary']}")
        hd_rem = getattr(state, '_hit_dice_remaining', level)
        result = short_rest(hp, mhp, level, con_mod, hd_rem,
                            dice_to_use=args.get("hit_dice"),
                            min_per_die=min_hit_die_heal(state))
        state._hit_dice_remaining = result["hit_dice_remaining"]
        changes = {"hp": result["hp_restored"]}
        # 短休恢复的职业资源（奥术回想每日一次，由会话状态记录）
        for r in info.get("class_resources", []):
            if r.get("key") not in SHORT_REST_RESOURCE_KEYS:
                continue
            if r.get("key") == "arcane_recovery" and getattr(state, "_arcane_recovery_used", False):
                continue
            changes[f"class_resource:{r['key']}"] = {"current": r.get("max", r.get("current", 0))}
            if r.get("key") == "arcane_recovery":
                state._arcane_recovery_used = True
        # 邪术师契约法术位短休恢复
        if system == "dnd5e" and info.get("char_class") == "邪术师":
            from backend.engine.game_systems import get_dnd5_spell_slots
            changes["spell_slots"] = get_dnd5_spell_slots("邪术师", level)
        await _exec_update_state({"changes": changes, "reason": "短休"}, state)
        # 时间成本由后端推进：短休 = 1 小时（跨天会结算口粮/饮水与力竭）
        from backend.engine import time_rules
        rested = await time_rules.advance(state, 60, "短休")
        return f"🛌 短休: +{result['hp_restored']}HP，短休资源已恢复\n{rested['summary']}"

    # 长休：HP/MP 全满，全部职业资源与法术位恢复
    changes = {"hp": max(0, mhp - hp)}
    if info.get("max_mp"):
        changes["mp"] = max(0, info.get("max_mp", 0) - info.get("mp", 0))
    for r in info.get("class_resources", []):
        changes[f"class_resource:{r['key']}"] = {"current": r.get("max", r.get("current", 0))}
    if system == "dnd5e":
        from backend.engine.game_systems import get_dnd5_spell_slots
        cc = info.get("char_class", "")
        if cc in ("法师", "牧师", "吟游诗人", "德鲁伊", "术士", "圣武士", "游侠", "邪术师"):
            changes["spell_slots"] = get_dnd5_spell_slots(cc, level)
        # 5e「幸运」专长：每次长休把幸运点重置回 3（此前只写在 feats 图鉴里，没人写回）
        from backend.engine.luck_rules import lucky_feat_points
        lucky_points = lucky_feat_points(state)
        if lucky_points:
            changes["luck"] = lucky_points - int(info.get("luck", 0) or 0)
    elif system == "dnd4e":
        changes["action_points"] = 1 - info.get("action_points", 1)
        reset_encounters(state)  # 延长休息：里程碑重新计数
        if info.get("max_healing_surges"):
            changes["healing_surges"] = info.get("max_healing_surges", 0) - info.get("healing_surges", 0)
    # 5e 规则：长休最多恢复"一半生命骰"（向下取整，至少 1），不能直接补满
    hd_total = max(1, int(level or 1))
    hd_left = int(getattr(state, "_hit_dice_remaining", hd_total) or 0)
    state._hit_dice_remaining = min(hd_total, hd_left + max(1, hd_total // 2))
    state._arcane_recovery_used = False
    await _exec_update_state({"changes": changes, "reason": "长休"}, state)
    # 长休 = 8 小时；有口粮时力竭 −1
    from backend.engine import time_rules
    rested = await time_rules.finish_long_rest(state)
    text = "🛌 长休: HP/法术位/职业资源全部恢复"
    if rested:
        text += f"\n{rested}"
    return text


