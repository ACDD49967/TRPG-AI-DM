"""敌人回合主动攻击：`enemy_attack` 工具的实现（玩家攻击后的自动反伤不在此列）。

从 `combat_damage` 拆出（那边只留门面与补丁契约说明）。

**补丁契约**：`_roll_damage_simple` / `_persist_combat_damage` / `combat_attack_roll`
在测试里是通过 `patch.object(combat, ...)` 打桩的，所以统一经 `_combat()`
在调用时取模块属性，而不是 import 时就绑定函数对象（否则 patch 会静默失效）。
"""
from __future__ import annotations

import random

from backend.engine.combat_state import _build_combat_snapshot, _refresh_combat_state
from backend.engine.combat_targets import _resolve_enemy_from_cards
from backend.engine.session import GameSessionState, push_event, push_narrative_token
from backend.engine.tool_shims import _as_bool, _game_system


def _combat():
    """延迟拿 combat 模块：保留测试对 combat.* 的打桩语义，同时避免模块级循环导入。"""
    from backend.engine import combat
    return combat

async def _exec_enemy_attack(args: dict, state: GameSessionState) -> str:
    """敌人回合主动攻击：在剧情中到达敌人回合时调用，不是玩家攻击后的自动反伤。"""
    enemy = str(args.get("enemy_name", "敌人"))
    recharge_ability = str(args.get("recharge_ability") or "")
    from backend.engine import recharge_rules
    from backend.engine.turn_start_effects import apply_turn_start_effects, is_pending_regeneration
    pre_stats = _resolve_enemy_from_cards(state, enemy, args)
    pre_npc = pre_stats.get("npc")
    if not recharge_ability and pre_npc is not None:
        recharge_ability = recharge_rules.match_recharge_ability(
            pre_npc, str(args.get("enemy_action") or args.get("damage_type") or ""))
    start_note = await apply_turn_start_effects(state, enemy, pre_npc) if pre_npc is not None else ""
    if pre_npc is not None and (
        not bool(getattr(pre_npc, "alive", True)) or int(getattr(pre_npc, "hp", 0) or 0) <= 0
    ) and not is_pending_regeneration(state, enemy):
        return f"⚠ {enemy} 已阵亡，无法行动。"
    recharge_ok, recharge_reason = recharge_rules.recharge_available(
        state, enemy, recharge_ability, pre_npc)
    if not recharge_ok:
        return recharge_reason
    # 行动经济：每个敌人每回合 1 次主行动；传奇动作/加速术/时间暂停等额外行动需显式声明来源
    from backend.engine.tool_executor import consume_action, declared_action_source
    source, requested = declared_action_source(args)
    allowed, reason = consume_action(state, enemy, source, requested)
    if not allowed:
        return f"⚠ {enemy}：{reason}"
    system = _game_system(state)
    enemy_stats = _resolve_enemy_from_cards(state, enemy, args)
    target_npc = enemy_stats.get("npc")
    if target_npc is not None and not start_note:
        start_note = await apply_turn_start_effects(state, enemy, target_npc)
    if target_npc is not None:
        # 回合开始效果会改 HP；末尾的写回必须使用新值，不能用解析时的旧快照
        enemy_stats["e_hp"] = int(getattr(target_npc, "hp", 0) or 0)
    if target_npc is not None and (
        not bool(getattr(target_npc, "alive", True)) or int(getattr(target_npc, "hp", 0) or 0) <= 0
    ):
        return f"⚠ {enemy} 在回合开始效果后倒下。\n{start_note}".strip()
    e_mod = int(enemy_stats["e_mod"])
    e_dice = str(enemy_stats["e_dice"])
    npc = enemy_stats.get("npc")

    attrs = state.character_info.get("attributes", {})
    player_ac = int(state.character_info.get("ac", 0) or 0)
    if not player_ac:
        dex_mod = (attrs.get("dex", 10) - 10) // 2
        cc = state.character_info.get("char_class", "战士")
        player_ac = (16 if cc in ("战士", "圣武士") else
                     14 + max(-2, min(2, dex_mod)) if cc == "游侠" else
                     10 + dex_mod + (attrs.get("con", 10) - 10) // 2 if cc == "野蛮人" else
                     10 + dex_mod + (attrs.get("wis", 10) - 10) // 2 if cc == "武僧" else
                     11 + dex_mod)
        player_ac = max(8, min(22, player_ac))

    # 战场态势：防御方的掩体加 AC；玩家已拉开距离时近战要先接近（借机攻击是反应，不受此限）
    from backend.engine import battlefield as _bf
    action_source = str(args.get("action_source") or "").lower()
    player_name = str(getattr(state, "character_name", "") or "玩家")
    player_cover = _bf.normalize_cover(args.get("player_cover")) or _bf.cover_of(state, player_name)
    player_band = _bf.normalize_band(args.get("player_band")) or _bf.band_of(state, player_name)
    if player_cover:
        _bf.set_placement(state, player_name, player_band, player_cover)
    if not _bf.can_be_targeted(player_cover):
        return ((f"{start_note}\n" if start_note else "")
                + f"⚠ {player_name} 正处于全掩体后，{enemy} 无法直接攻击。"
                f"请改用范围手段、逼迫其离开掩体，或更新态势。")
    if (not _bf.melee_reachable(player_band) and action_source != "opportunity_attack"
            and not _as_bool(args.get("close_distance"))):
        label, dist = _bf.BANDS.get(player_band, ("较远", "超出近战距离"))
        return ((f"{start_note}\n" if start_note else "")
                + f"⚠ {player_name} 已在{label}（{dist}），{enemy} 的近战够不到。"
                f"请声明 close_distance=true 让其接近，或改用远程/投掷攻击。")
    cover_bonus = _bf.cover_ac_bonus(player_cover)
    if cover_bonus:
        player_ac += cover_bonus

    from backend.engine.combat_advantage import enemy_attack_advantage
    advantage = enemy_attack_advantage(
        state, args, enemy=enemy, enemy_npc=npc, dice=e_dice,
        enemy_action=str(args.get("enemy_action") or ""), system=system,
        attacker_band=_bf.band_of(state, enemy) or player_band)
    if recharge_ability and npc is not None:
        recharge_rules.mark_recharge_used(state, enemy, recharge_ability, npc)

    if system == "coc":
        # 与 combat_round 的 COC 分支保持一致：NPC 卡没有 D&D 属性时 e_mod 会是个位数，
        # 直接当技能百分比用会导致敌人几乎永远打不中；没有显式声明就按 40% 兜底。
        if args.get("enemy_attack_modifier") is None and int(e_mod or 0) <= 10:
            e_mod = 40
        e_skill = max(1, min(99, int(e_mod or 40)))
        er = random.randint(1, 100)
        if er <= e_skill:
            ed = _combat()._roll_damage_simple(e_dice)
            result = "命中"
        else:
            ed = 0
            result = "未命中"
        await push_event(state, "dice_roll", {
            "skill": f"{enemy}攻击", "dc": e_skill,
            "roll": er, "modifier": 0, "result": "成功" if ed else "失败",
        })
        line = f"{enemy}攻击: d100={er} vs {e_skill}% → {result}"
    else:
        roll_kwargs = {"advantage": advantage.mode} if advantage.mode.value != "normal" else {}
        enemy_hit, ed = _combat().combat_attack_roll(enemy, player_ac, e_mod, e_dice, **roll_kwargs)
        roll_event = {
            "skill": f"{enemy}攻击", "dc": player_ac,
            "roll": enemy_hit.roll, "modifier": e_mod, "result": enemy_hit.result.value,
        }
        if advantage.summary():
            roll_event.update(advantage.event_data())
        await push_event(state, "dice_roll", roll_event)
        line = f"{enemy}攻击玩家 → AC{player_ac}"
        if cover_bonus:
            line += f"[玩家掩体 AC+{cover_bonus}]"
        if advantage.summary():
            line += f"[{advantage.summary()}]"

    # 玩家侧伤害统一走管线：临时生命值 → 抗性/免疫/易伤 → HP 与死亡豁免。
    # 先算再写文案，玩家看到的数字就是实际扣血（不是抗性前的原始值）。
    taken = 0
    if ed:
        from backend.engine import player_damage
        from backend.engine.damage_rules import canonical_damage_type, infer_damage_type
        traits_text = " ".join(getattr(npc, "traits", []) or [])
        enemy_damage_type = (canonical_damage_type(args.get("damage_type"))
                             or infer_damage_type(f"{traits_text} {e_dice}"))
        outcome = await player_damage.apply(
            state, ed, damage_type=enemy_damage_type,
            reason=f"{enemy}造成伤害", source=f"{enemy}攻击")
        taken = int(outcome["hp_damage"]) + int(outcome["temp_absorbed"])
        line += f"，造成 {taken} 点伤害"
        if outcome["temp_absorbed"]:
            line += f"（临时生命值吸收 {outcome['temp_absorbed']}）"
        if outcome["note"]:
            line += f" [{outcome['note']}]"

    await push_narrative_token(state, f"\n{line}\n")
    current_hp = int(enemy_stats.get("e_hp", 0) or 0)
    await push_event(state, "game_event", {"type": "combat", "description": line,
                                           "extra": {"player_damage_taken": taken, "enemy_name": enemy,
                                                     "enemy_hp_remaining": current_hp,
                                                     "enemies": _build_combat_snapshot(state, args.get("enemy_names") or [], enemy, current_hp)}})
    # 若敌人已有 NPC 实体，持久化当前血量（敌人攻击不影响自己血量，只保留实体存在）
    if npc is not None:
        await _combat()._persist_combat_damage(state, npc, int(enemy_stats.get("e_hp", 0) or 0))
    _refresh_combat_state(state)
    return ((f"{start_note}\n" if start_note else "") + line)
