from __future__ import annotations


import random

import re

from typing import Any


from backend.engine.rules import RollResult, combat_attack_roll

from backend.engine.combat_coc import resolve_coc_round
from backend.engine.session import GameSessionState, push_event, push_narrative_token

from backend.engine.tool_executor import primary_action_available

from backend.engine.world_state import NpcEntry
from backend.engine.tool_shims import _game_system, _as_bool


async def _exec_update_state(args: dict, state: Any) -> str:
    from backend.engine import character_state
    return await character_state._exec_update_state(args, state)


# NPC 等级 → 击败经验。等级在本项目里表示威胁强度，取值对齐 5e 低阶 CR 区间，
# 单人跑团没有队伍分摊，因此按单人全额发放。


async def _exec_combat_round(args: dict, state: GameSessionState) -> str:
    p_action = str(args.get("player_action", "攻击"))
    enemy = str(args.get("enemy_name", "敌人"))
    system = _game_system(state)

    # 4e：声明用行动点换额外行动时，点数必须真的扣（实现见 action_economy）
    from backend.engine.action_economy import deny_extra_action_without_action_point
    denied = await deny_extra_action_without_action_point(state, system, args)
    if denied:
        return denied
    # 敌人是否可以主动行动：被绑/待宰/昏迷/无力等不得反击或主动攻击
    enemy_can_act = bool(args.get("enemy_can_act", True))
    helpless_text = f"{enemy} {args.get('enemy_condition', '')} {args.get('enemy_notes', '')}"
    if re.search(r"待宰|被绑|捆绑|失去意识|昏迷|无力|跪着|跪地|囚|笼中|陷阱|无助|重伤|濒死|倒下", helpless_text, re.I):
        enemy_can_act = False

    # 玩家侧：角色卡推导（参数缺省时）
    info = state.character_info
    if args.get("player_attack_modifier") is not None:
        p_mod = int(args["player_attack_modifier"])
    elif system == "coc":
        skill_map = info.get("skills", {}) or {}
        hit = next((v for k, v in skill_map.items() if k and k in p_action), 0)
        p_mod = int(hit or 50)
    else:
        p_mod = _player_attack_bonus(state, p_action)
    p_dice = str(args.get("player_damage_dice", "") or _weapon_dice_from_inventory(state) or "1d8")

    # 敌人侧：NPC卡 → 生物图鉴卡 → 参数；并注册为实际实体
    enemy_stats = _resolve_enemy_from_cards(state, enemy, args)
    target_npc = enemy_stats.get("npc")
    if target_npc is not None and (
        not bool(getattr(target_npc, "alive", True)) or int(getattr(target_npc, "hp", 0) or 0) <= 0
    ):
        return (
            f"❌ {enemy} 已阵亡，不能作为攻击目标。"
            "如果场上还有别的敌人，请先用 update_world_state(add_npc) 登记一个可区分的名称"
            "（例如「地精斥候B」）再攻击，不要复用已死亡的单位名。"
        )
    e_ac = int(enemy_stats["e_ac"])
    e_mod = int(enemy_stats["e_mod"])
    e_dice = str(enemy_stats["e_dice"])
    e_hp = int(enemy_stats["e_hp"])
    e_max_hp = int(enemy_stats.get("e_max_hp") or e_hp)
    npc = enemy_stats.get("npc")

    # ── 战场态势：掩体加 AC、近战要先接近 ──────────────────
    from backend.engine import battlefield, character_state
    player_name = str(getattr(state, "character_name", "") or "玩家")
    ignore_cover = character_state._has_feat_effect(state, "ignore_cover")
    target_band = battlefield.normalize_band(args.get("target_band")) or battlefield.band_of(state, enemy)
    target_cover = battlefield.normalize_cover(args.get("target_cover")) or battlefield.cover_of(state, enemy)
    if target_band or target_cover:
        battlefield.set_placement(state, enemy, target_band, target_cover)
    closing = _as_bool(args.get("close_distance"))
    if not battlefield.can_be_targeted(target_cover, ignore_cover):
        return (f"⚠ {enemy} 正处于全掩体后，无法直接攻击。可以让它探头/移动后再攻，"
                f"或用 set_tactical_state 更新它的掩体等级；也可以改打别的目标。")
    if not battlefield.melee_reachable(target_band) and not closing:
        label, dist = battlefield.BANDS.get(target_band, ("较远", "超出近战距离"))
        return (f"⚠ {enemy} 目前处于{label}（{dist}），近战够不到。"
                f"请先声明 close_distance=true 冲上去（本回合移动），"
                f"或改用远程/法术手段；也可以用 set_tactical_state 更新档位。")
    cover_bonus = battlefield.cover_ac_bonus(target_cover) if not ignore_cover else 0
    if cover_bonus:
        e_ac += cover_bonus

    # 通用特长：巨武器大师 / 神射手的 -5/+10（仅 5e 有意义）
    from backend.engine import feat_effects
    power_feats = feat_effects.power_feat_names(state) if system == "dnd5e" else []
    power_hit_pen, power_dmg, power_src = (0, 0, "")
    if _as_bool(args.get("power_attack")):
        power_hit_pen, power_dmg, power_src = feat_effects.power_attack(
            state, f"{p_action} {_equipped_weapon_name(state)}")
        if not power_src:
            return (f"⚠ {player_name} 没有对应特长，不能声明强力攻击（-5 命中 / +10 伤害）："
                    "巨武器大师用于近战，神射手用于远程。请按普通攻击结算，"
                    "或先确认角色卡上的特长。")
    attack_mod = p_mod - power_hit_pen
    from backend.engine.combat_advantage import player_attack_advantage
    advantage = player_attack_advantage(
        state, args, action=p_action, weapon=_equipped_weapon_name(state),
        enemy_npc=npc, system=system, player_name=player_name)

    # 玩家防御：优先角色卡 AC
    attrs = info.get("attributes", {})
    player_ac = int(info.get("ac", 0) or 0)
    if not player_ac:
        dex_mod = (attrs.get("dex", 10) - 10) // 2
        cc = info.get("char_class", "战士")
        if cc in ('战士', '圣武士'): player_ac = 16
        elif cc == '游侠': player_ac = 14 + max(-2, min(2, dex_mod))
        elif cc == '野蛮人': player_ac = 10 + dex_mod + (attrs.get("con", 10) - 10) // 2
        elif cc == '武僧': player_ac = 10 + dex_mod + (attrs.get("wis", 10) - 10) // 2
        else: player_ac = 11 + dex_mod
        if '矮人' in info.get("race", "") and '山地' in info.get("race", ""):
            player_ac += 1
        player_ac = max(8, min(22, player_ac))

    if system == "coc":
        # COC 的 d100 对抗整段已拆到 combat_coc（含 40% 技能兜底与敌人反击）
        return await resolve_coc_round(
            args, state, enemy=enemy, p_action=p_action, p_mod=p_mod, p_dice=p_dice,
            e_mod=e_mod, e_hp=e_hp, npc=npc, enemy_can_act=enemy_can_act)

    roll_kwargs = {"advantage": advantage.mode} if advantage.mode.value != "normal" else {}
    ph, pd = combat_attack_roll("你", e_ac, attack_mod, p_dice, **roll_kwargs)
    if pd and power_dmg:
        pd += power_dmg  # 强力攻击的伤害加值算在抗性之前
    # 敌人侧抗性/免疫/易伤：伤害类型取 DM 声明 → 动作里提到的武器 → 已装备武器
    from backend.engine.damage_rules import (
        canonical_damage_type, damage_multiplier, weapon_damage_type,
    )
    p_type = (canonical_damage_type(args.get("damage_type"))
              or weapon_damage_type(p_action)
              or weapon_damage_type(_equipped_weapon_name(state)))
    p_mult, p_note = damage_multiplier(
        _find_bestiary_card(state, enemy) or npc or {},
        p_type, extra_text=" ".join(getattr(npc, "traits", []) or []))
    applied_pd = max(0, int(pd * p_mult))
    if applied_pd > 0 and p_type:
        from backend.engine.turn_start_effects import record_damage_type
        record_damage_type(state, enemy, p_type)
    new_e_hp = max(0, e_hp - applied_pd)
    ed = 0
    roll_event = {
        "skill": p_action or "攻击", "dc": e_ac,
        "roll": ph.roll, "modifier": attack_mod, "result": ph.result.value,
    }
    if advantage.summary():
        roll_event.update(advantage.event_data())
    await push_event(state, "dice_roll", roll_event)
    # 亡灵坚韧：这一击把带该特性的生物打到 0 HP 时，由后端掷体质豁免决定去留
    fortitude_note = ""
    if new_e_hp <= 0 and applied_pd > 0 and npc is not None:
        from backend.engine.undead_fortitude import resolve_undead_fortitude
        fort = await resolve_undead_fortitude(
            state, npc, enemy, damage=applied_pd, damage_type=p_type,
            critical=(getattr(ph.result, "value", ph.result) == RollResult.CRITICAL_SUCCESS.value))
        fortitude_note = str(fort.get("note") or "")
        if fort.get("applied"):
            new_e_hp = int(fort.get("hp") or 1)
    # 敌人攻击由 enemy_attack 工具在敌人回合/剧情中单独调用，避免“穿反甲”式自动反伤

    system_hint = "D&D4e" if system == "dnd4e" else ("D&D5e" if system == "dnd5e" else "自定义")
    lines = [f"⚔️ 战斗结算（{system_hint} d20）",
             f"攻击: d20={ph.roll}+{attack_mod}={ph.total} vs AC{e_ac}→{ph.result.value}"]
    if advantage.summary():
        lines.append(f"[{advantage.summary()}]")
    if power_src:
        lines.append(f"[强力攻击（{power_src}）：-5 命中 / +10 伤害]")
    if closing:
        battlefield.set_placement(state, player_name, "engaged", target_cover, "冲入近战")
        lines.append(f"[移动：你冲上前与{enemy}缠斗]")
        if cover_bonus:
            lines.append(f"[目标掩体 AC+{cover_bonus}]")
    elif cover_bonus:
        lines.append(f"[目标掩体 AC+{cover_bonus}]")
    if pd:
        # 命中就报数：免疫/抗性把伤害降到 0 或减半时，玩家仍要看到原因
        lines.append(f"造成 {applied_pd} 点伤害 (敌人HP: {new_e_hp}/{e_max_hp})")
        if p_note:
            lines.append(f"[{p_note}]")
    if fortitude_note:
        lines.append(f"[{fortitude_note}]")
    if ed: lines.append(f"{enemy}反击: {ed} 点伤害")
    # 先写回并结算经验，再组装玩家可见的结算行（击败时带上 XP）
    xp_gain = await _persist_combat_damage(state, npc, new_e_hp)
    if new_e_hp <= 0:
        lines.append(f"💀 {enemy}被击败！" + (f"（+{xp_gain} XP）" if xp_gain else ""))
    if power_feats:
        lines.append(f"[{'/'.join(power_feats)}可用: 声明 power_attack=true 换 -5命中/+10伤害]")

    desc = "\n".join(lines)
    extras = {"enemy_name": enemy, "enemy_hp_remaining": new_e_hp,
              "player_damage_taken": ed, "player_damage_dealt": applied_pd,
              "damage_type": p_type, "note": p_note,
              "undead_fortitude": fortitude_note,
              "enemy_dead": new_e_hp <= 0, "system": system,
              "enemies": _build_combat_snapshot(state, args.get("enemy_names") or [], enemy, new_e_hp)}

    await push_narrative_token(state, f"\n{desc}\n")
    await push_event(state, "game_event", {"type": "combat", "description": desc, "extra": extras})
    if ed:
        await _exec_update_state({"changes": {"hp": -ed}, "reason": f"{enemy}造成{ed}伤害"}, state)

    # 目标敌人若仍能行动，立即结算其一次反击；dedup 保证主DM随后不会重复结算
    if enemy_can_act and new_e_hp > 0 and primary_action_available(state, enemy):
        enemy_result = await _exec_enemy_attack(
            {"enemy_name": enemy, "attacker_condition": str(args.get("enemy_condition") or "")},
            state)
        desc += "\n" + enemy_result

    ws = getattr(state, 'world_state', None)
    if ws and ws.scene.current_location != "未知":
        desc += f"\n[场景确认: {ws.scene.current_location}, {ws.scene.current_time or f'第{ws.scene.day_count}天'}]"
    return desc


def _roll_damage_simple(spec: str) -> int:
    """解析 '2d6+3' 并掷出伤害。"""
    try:
        import re as _re
        m = _re.match(r"(\d*)d(\d+)(?:\+(\d+))?", spec.strip().lower())
        if not m:
            return 0
        num = int(m.group(1) or 1)
        sides = int(m.group(2))
        bonus = int(m.group(3) or 0)
        return sum(random.randint(1, sides) for _ in range(num)) + bonus
    except Exception:
        return 0


# ── 目标解析已拆分到 backend.engine.combat_targets ───────────
# 这里再导出，保持既有调用方（media_tools、dm_agent、测试）不变。
from backend.engine.combat_targets import (  # noqa: E402
    _find_bestiary_card, _first_dice, _first_int, _register_combatant_from_card,
    _resolve_enemy_from_cards, _resolve_npc_hp,
)

# 拆出的辅助函数在这里再导出，dm_agent / tool_executor 的 import 面不变
from backend.engine.combat_rewards import (  # noqa: E402,F401
    _NPC_LEVEL_XP, _award_defeat_xp, _defeat_xp_for, _persist_combat_damage,
)
from backend.engine.combat_state import _build_combat_snapshot, _refresh_combat_state  # noqa: E402,F401
from backend.engine.combat_weapons import (  # noqa: E402,F401
    _equipped_weapon_name, _player_attack_bonus, _weapon_dice_from_inventory,
)

# 伤害/敌人攻击处理器已拆到 combat_damage，这里再导出，
# dm_agent / tool_executor / 测试的 import 面与 patch 目标都不变。
from backend.engine.combat_damage import (  # noqa: E402,F401
    _exec_enemy_attack, _exec_save_damage,
)
