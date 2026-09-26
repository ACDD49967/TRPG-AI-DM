"""工具执行层：工具分发、写锁、行动经济账本、冒险笔记推送与同回合重复调用保护。

这里只做"执行与约束"，处理器按域放在各自模块：
session_tools（骰子/记忆/休息/死亡豁免/建议）、media_tools（图鉴/地图/法术）、
world_tools（世界状态/场景/NPC/图谱）、character_state（角色状态变更）、
combat（战斗与伤害）。按需延迟导入，避免循环依赖。
"""
from __future__ import annotations
# 行动经济（主行动/额外行动配额 + 4e 行动点）拆到 action_economy，这里再导出
from backend.engine.action_economy import (  # noqa: F401
    ACTION_SOURCE_QUOTA, DEFAULT_EXTRA_ACTION_QUOTA, _ledger, _tracker,
    consume_action, declared_action_source, normalize_actor,
    primary_action_available, spend_action_point,
)

import asyncio
import re
from typing import Any


# 同回合重复调用保护（去重表 + 记结果）拆到 tool_settlement，这里再导出保持 import 面
from backend.engine.tool_settlement import (  # noqa: F401  再导出
    ACTION_SOURCE_LIFTS_DEDUPE, DEDUPE_TOOLS, call_key, duplicate_result, remember_result,
)

_SETTLEMENT_TOOLS = DEDUPE_TOOLS   # 兼容旧名（外部按这个键查过）

# 玩家一回合消耗"主行动"的工具：攻击、施法、休息、对抗动作（擒抱/推撞/逃脱）、
# 潜行（Hide）与解除机关。它们共享同一份行动账本，否则会出现"一回合连放三个不同法术"
# "同回合连休两次""同一个回合里擒抱三次""藏起来之后还照打"这类不合理流程；
# 合法多动（狡诈动作把 Hide 当附赠、多段攻击、时间暂停……）仍可用 action_source 声明。
_PLAYER_PRIMARY_ACTION_TOOLS = {
    "combat_round", "cast_spell", "take_rest", "resolve_contest",
    "resolve_stealth", "resolve_trap",
    # 冲刺（Dash）在 5e 里就是一次动作；追兵是 NPC 时不扣玩家的（_charges_player_action 看 actor）
    "resolve_chase",
}

# 触发"建立先攻表"的战斗类工具：第一次交战时后端掷先攻并交给 DM 顺序提示
_INITIATIVE_TRIGGER_TOOLS = {"combat_round", "enemy_attack", "save_damage"}

_JOURNAL_TOOLS = {
    "update_state", "combat_round", "update_world_state", "prune_world_state", "update_scene",
    "adjust_npc", "promote_npc", "add_scenario_bestiary", "add_scenario_map",
    "add_scenario_spell", "reveal_info", "update_bestiary_entry",
    "update_city_entry", "adjust_bestiary", "learn_spell", "forget_spell",
    "cast_spell", "update_knowledge_graph", "add_memory",
    "record_plot_memory", "add_character_note",
}

# 额外行动的来源与默认配额。默认每个单位每回合 1 次主行动；
# 多段攻击、动作如潮、传奇动作、时间暂停等属于合法额外行动，
# 但必须由 DM 显式声明来源，且不能超过合理次数（防止把失败结果重掷一遍）。
def _combat_targets(name: str, args: dict) -> list[str]:
    """从参数里收集参战单位名，保证"第一次攻击"就能把目标纳入先攻表。"""
    names = [str(args.get("enemy_name") or "")]
    for extra in (args.get("enemy_names") or []):
        names.append(str(extra or ""))
    for target in (args.get("targets") or []):
        names.append(str(target if isinstance(target, str) else (target or {}).get("name", "")))
    return [n for n in names if n]


async def _ensure_initiative(state: Any, name: str, args: dict) -> None:
    """战斗类工具触发时确保后端先攻表存在；第一次交战时把顺序告知玩家与 DM。"""
    from backend.engine import initiative
    from backend.engine.session import push_event

    surprise = str(args.get("surprise", "")).strip().lower() in ("1", "true", "yes", "y", "是", "真")
    surprise_side = ""
    if surprise and name == "combat_round":
        surprise_side = "enemy"      # 玩家突袭敌方
    elif surprise and name == "enemy_attack":
        surprise_side = "player"     # 敌方突袭玩家
    fresh = _tracker(state) is None
    tracker = initiative.ensure(state, _combat_targets(name, args), surprise_side=surprise_side)
    if tracker is None:
        return
    if fresh:
        await push_event(state, "game_event", {
            "type": "initiative",
            "description": f"先攻顺序：{tracker.order_line()}",
            "extra": tracker.payload(),
        })
        initiative.replace_hint(state, tracker.summary())


_HANDLERS: dict[str, Any] | None = None


def _handlers() -> dict[str, Any]:
    """延迟构建处理器表，避免与 dm_agent 形成导入环。"""
    global _HANDLERS
    if _HANDLERS is not None:
        return _HANDLERS
    from backend.engine import (
        battlefield, character_state, combat, graph_tools, media_tools, session_tools, spell_tools,
        chase_rules, contest_rules, hazards, poison_rules, stealth_rules, time_rules,
        trap_rules, world_tools,
    )
    from backend.engine import dm_agent as dm  # 仅剩 _game_system 等运行期通用工具
    from backend.dm_toolbox import generate_name, npc_quirk, roll_treasure, search_knowledge

    _HANDLERS = {
        # 会话与规则裁决
        "dice_roll": session_tools._exec_dice_roll,
        "update_state": character_state._exec_update_state,
        "combat_round": combat._exec_combat_round,
        "enemy_attack": combat._exec_enemy_attack,
        "save_damage": combat._exec_save_damage,
        "set_tactical_state": battlefield._exec_set_tactical_state,
        "add_memory": session_tools._exec_add_memory,
        "record_plot_memory": session_tools._exec_record_plot_memory,
        "equip_item": session_tools._exec_equip_item,
        "suggest_choices": session_tools._exec_suggest_choices,
        "death_saving_throw": session_tools._exec_death_save,
        "take_rest": session_tools._exec_rest,
        "advance_time": time_rules._exec_advance_time,
        "apply_hazard": hazards._exec_apply_hazard,
        "resolve_trap": trap_rules._exec_resolve_trap,
        "resolve_stealth": stealth_rules._exec_resolve_stealth,
        "resolve_contest": contest_rules._exec_resolve_contest,
        "apply_poison": poison_rules._exec_apply_poison,
        "resolve_chase": chase_rules._exec_resolve_chase,
        "search_memory": session_tools._exec_search_memory,
        "forget_memory": session_tools._exec_forget_memory,
        # 世界与关系
        "update_world_state": world_tools._exec_update_world_state,
        "prune_world_state": world_tools._exec_prune_world_state,
        "reveal_info": world_tools._exec_reveal_info,
        "update_scene": world_tools._exec_update_scene,
        "add_character_note": world_tools._exec_character_note,
        "search_npcs": world_tools._exec_search_npcs,
        "adjust_npc": world_tools._exec_adjust_npc,
        "promote_npc": world_tools._exec_promote_npc,
        "get_character_state": world_tools._exec_get_character_state,
        "adjust_resource": world_tools._exec_adjust_resource,
        "get_entity_graph": graph_tools._exec_get_entity_graph,
        "update_knowledge_graph": graph_tools._exec_update_knowledge_graph,
        "get_graph_path": graph_tools._exec_get_graph_path,
        # 内容库与施法
        "update_bestiary_entry": media_tools._exec_update_bestiary,
        "update_city_entry": media_tools._exec_update_city,
        "add_scenario_bestiary": media_tools._exec_add_scenario_bestiary,
        "add_scenario_map": media_tools._exec_add_scenario_map,
        "add_scenario_spell": spell_tools._exec_add_scenario_spell,
        "search_bestiary": media_tools._exec_search_bestiary,
        "search_locations": media_tools._exec_search_locations,
        "search_spells": spell_tools._exec_search_spells,
        "adjust_bestiary": media_tools._exec_adjust_bestiary,
        "get_bestiary_card": media_tools._exec_get_bestiary_card,
        "get_location_card": media_tools._exec_get_location_card,
        "cast_spell": spell_tools._exec_cast_spell,
        "learn_spell": spell_tools._exec_learn_spell,
        "forget_spell": spell_tools._exec_forget_spell,
        # 工具箱与检索
        "generate_name": lambda a, s: generate_name(a.get("race", "人类")),
        "roll_treasure": lambda a, s: "、".join(roll_treasure(int(a.get("cr", 1)))),
        "npc_quirk": lambda a, s: npc_quirk(),
        "search_knowledge": lambda a, s: str(search_knowledge(
            a.get("query", ""), dm._game_system(s), int(a.get("top_k", 3)), s.username)),
    }
    return _HANDLERS


def _player_actor(state: Any) -> str:
    return getattr(state, "character_name", "") or "玩家"


def _action_cost_hook(name: str):
    """需要"域自己"判断算不算玩家动作的工具，返回该域的实现（没有则 None）。

    潜行/陷阱这类工具的行动者不一定是玩家（DM 也可能让 NPC 藏起来、或在结算 NPC 踩到的
    机关），判断规则放在各自模块里，执行层只负责问一句。
    """
    if name == "resolve_stealth":
        from backend.engine import stealth_rules
        return stealth_rules.costs_player_action
    if name == "resolve_trap":
        from backend.engine import trap_rules
        return trap_rules.costs_player_action
    return None


def _charges_player_action(name: str, args: dict, state: Any) -> bool:
    """这次调用是否消耗玩家的主行动。

    多数玩家工具没有发起者参数，一律算在玩家头上；对抗动作（`resolve_contest`）
    可以是 NPC 对玩家动手，潜行/陷阱的行动者也可能不是玩家，那时不该扣玩家的主行动。
    """
    if name not in _PLAYER_PRIMARY_ACTION_TOOLS:
        return False
    hook = _action_cost_hook(name)
    if hook is not None:
        return bool(hook(args or {}, state))
    actor = str((args or {}).get("attacker") or (args or {}).get("actor") or "").strip()
    if not actor:
        return True
    from backend.engine.player_damage import is_player_name

    return is_player_name(state, actor)


def player_action_block_reason(state: Any) -> str:
    """角色状态不允许行动时的原因；可行动返回空串。"""
    if getattr(state, "character_dead", False):
        return "角色已死亡，无法再行动。可以创建新角色继续这个世界的冒险，或通过复活法术/读档恢复。"
    try:
        hp = int((getattr(state, "character_info", {}) or {}).get("hp", 1) or 0)
    except (TypeError, ValueError):
        hp = 1
    if getattr(state, "dying", False) or hp <= 0:
        return "角色已倒地昏迷（HP 0），本回合不能行动、移动或施法；请等待死亡豁免或被同伴救治。"
    return ""


async def execute_tool(name: str, args: dict, state: Any) -> str:
    """执行一次工具调用；返回给模型观察的文本结果。"""
    fn = _handlers().get(name)
    if fn is None:
        return f"未知: {name}"

    # 战斗顺序：战斗类工具触发后端先攻表（第一次交战时掷先攻并给出顺序提示）
    if name in _INITIATIVE_TRIGGER_TOOLS:
        # 前置校验（全掩体/近战距离）放在消耗行动之前，避免"够不到"白吃一次主行动
        from backend.engine import battlefield
        blocked = battlefield.preflight_attack(state, name, args)
        if blocked:
            return blocked
        await _ensure_initiative(state, name, args)

    action_source, requested_actions = declared_action_source(args)
    # 声明了额外行动来源时（多段攻击/传奇动作等），同样的参数会被合法地重复调用，
    # 此时交给行动经济账本按配额管控，不做"参数完全相同即拒绝"。
    explicit_extra_action = bool(action_source) and name in ACTION_SOURCE_LIFTS_DEDUPE
    if not explicit_extra_action:
        reused = duplicate_result(state, name, args)
        if reused:
            return reused

    # 行动经济：玩家每回合 1 次主行动（攻击/施法/休息共用）；多段攻击、动作如潮、
    # 加速术、传奇动作等额外行动需显式声明来源。既拦住"失败后重掷"，也不封死合法多动。
    if _charges_player_action(name, args, state):
        block = player_action_block_reason(state)
        if block:
            return f"⚠ {block}"
        allowed, reason = consume_action(state, _player_actor(state), action_source, requested_actions)
        if not allowed:
            return f"⚠ {reason}"

    async def _invoke():
        result = fn(args, state)
        if asyncio.iscoroutine(result):
            result = await result
        return result

    lock = getattr(state, "tool_lock", None)
    if lock is None:
        result = await _invoke()
    else:
        # 多个专业子 Agent 并发调用工具时，串行化状态变更，避免世界状态竞态
        async with lock:
            result = await _invoke()

    if not explicit_extra_action:
        remember_result(state, name, args, result)

    # 出手暴露：攻击/施法会打破隐藏（5e：一动手就现形），规则与清理由 stealth_rules 负责
    from backend.engine import stealth_rules

    exposed = await stealth_rules.break_stealth_after_tool(name, args, state)
    if exposed:
        result = f"{result}\n{exposed}"

    # 数据及时更新：世界/角色/图谱发生变化后立即推送冒险笔记
    try:
        ws = getattr(state, "world_state", None)
        if ws is not None and name in _JOURNAL_TOOLS:
            from backend.engine.session import push_event
            await push_event(state, "journal_update", ws.to_player_journal())
    except Exception as e:
        from backend.logging_utils import get_logger
        get_logger("tool_executor.journal").warning("journal_update 推送失败: %s", e, exc_info=True)
    return result
