"""对抗动作：擒抱 / 推撞 / 逃脱——力量（运动）对抗对方的运动或杂技。

5e 把这类动作写成"用一次攻击换一次对抗检定"，此前项目里完全没有实现：
DM 要么直接叙事"他抓住你了"，要么手掷两个 d20 自己查加值，结果不进状态、
也不受行动经济约束。这里把它做成确定性规则：

- 擒抱成功 → 目标获得「擒抱」（速度归 0）；
- 推撞成功 → 目标「俯卧」或被推开 5 尺（位移交给 DM 用 set_tactical_state 更新）；
- 逃脱成功 → 解除自己的「擒抱」；
- 体型比对方大出两级以上无效；目标无法行动（失能/麻痹/昏迷…）时自动成功。

数值与体型判定在 `contest_modifiers`，擒抱状态的维护（谁抓着谁、擒抱者倒下自动解除）
在 `grapple_state`；这里只留对抗流程并再导出两边的名字。
"""
from __future__ import annotations

import random
from typing import Any

from backend.engine.condition_apply import apply_named_condition, has_condition
from backend.engine.contest_modifiers import (  # noqa: F401  再导出
    SIZE_ORDER, acrobatics_modifier, athletics_modifier, can_action_target,
    defense_modifier, is_helpless, size_index,
)
from backend.engine.grapple_state import (  # noqa: F401  再导出
    GRAPPLE, cannot_act, grappling_targets, holds_grapple, release_grapples_by, same_name,
)
from backend.engine.session import GameSessionState, push_event

PRONE = "俯卧"
_GRAPPLE_WORDS = ("擒抱", "grappled")
_GRAPPLE_ACTIONS = ("grapple", "擒抱", "抓取")
_SHOVE_ACTIONS = ("shove", "推撞", "绊摔", "推开", "摔倒", "推倒")
_ESCAPE_ACTIONS = ("escape", "逃脱", "挣脱")
# 模型有时把动作写成 contest_kind/kind，或直接用动词；这里都收下
_ACTION_ALIASES = {
    "抓": "grapple", "抱住": "grapple", "锁住": "grapple",
    "击倒": "shove", "撞开": "shove", "推": "shove",
    "脱身": "escape", "摆脱": "escape", "挣开": "escape",
}
_ACTOR_KEYS = ("attacker", "contestant_a", "actor", "initiator", "grappler", "谁发起")
_TARGET_KEYS = ("target", "contestant_b", "defender", "opponent", "victim", "目标")


def _first_str(args: dict, keys: tuple[str, ...]) -> str:
    """按候选键名取第一个非空字符串（模型对参数名的猜测并不完全可预测）。"""
    for key in keys:
        value = (args or {}).get(key)
        if isinstance(value, (list, tuple)) and value:
            value = value[0]
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _action_arg(args: dict) -> str:
    raw = _first_str(args, ("action", "contest_kind", "kind", "行动")) or "grapple"
    text = raw.lower()
    return _ACTION_ALIASES.get(text, text)


def _int_arg(value: Any, default: int = 0) -> int:
    try:
        return int(float(value)) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _declared_advantage(args: dict) -> tuple[bool, bool, str]:
    """读取 DM 声明的优势/劣势；未结构化来源才允许声明（与攻击裁定同一约定）。"""
    mode = str(args.get("advantage") or "").strip().lower()
    note = str(args.get("advantage_reason") or "").strip()
    return mode == "advantage", mode == "disadvantage", note


def _roll(advantage: bool, disadvantage: bool) -> int:
    rolls = [random.randint(1, 20)]
    if advantage or disadvantage:
        rolls.append(random.randint(1, 20))
    if len(rolls) == 1:
        return rolls[0]
    return max(rolls) if advantage else min(rolls)


async def _resolve_contest_roll(state: GameSessionState, *, actor: str, target: str,
                                actor_mod: int, defense: str, label: str,
                                advantage: bool, disadvantage: bool) -> tuple[bool, str]:
    """掷一次对抗检定，返回 (行动方是否获胜, 可叙述的说明行)。"""
    defender_mod = defense_modifier(state, target, defense)
    actor_roll = _roll(advantage, disadvantage)
    defender_roll = _roll(False, False)
    actor_total, defender_total = actor_roll + actor_mod, defender_roll + defender_mod
    # 5e 的对抗检定是"总点高者胜"；自然 20/1 不自动成功或失败，
    # 平局算防御方守住，避免"同为 15 却判定进攻成功"这种不公平结果。
    success = actor_total > defender_total
    await push_event(state, "dice_roll", {
        "skill": label, "dc": defender_total, "roll": actor_roll,
        "modifier": actor_mod, "result": "成功" if success else "失败",
    })
    line = (f"🤼 {label}：{actor} d20={actor_roll}{'+' if actor_mod >= 0 else ''}{actor_mod}"
            f"={actor_total} vs {target} d20={defender_roll}"
            f"{'+' if defender_mod >= 0 else ''}{defender_mod}={defender_total} → "
            f"{'成功' if success else '失败'}")
    return success, line


async def _exec_resolve_contest(args: dict, state: GameSessionState) -> str:
    from backend.engine.player_damage import is_player_name

    args = args or {}
    action = _action_arg(args)
    actor = _first_str(args, _ACTOR_KEYS)
    if not actor or is_player_name(state, actor):
        actor = str(getattr(state, "character_name", "") or "玩家")
    target = _first_str(args, _TARGET_KEYS)
    if not target:
        return "⚠ resolve_contest 需要 target（对抗的目标）"
    advantage, disadvantage, reason_note = _declared_advantage(args)

    if action in _ESCAPE_ACTIONS:
        if not has_condition(state, actor, *_GRAPPLE_WORDS):
            return (f"⚠ {actor} 当前没有被擒抱，不需要逃脱检定。"
                    f"如果刚才只是叙事里「抓住了」，请先补一次 resolve_contest"
                    f"(action=grapple) 的对抗检定，成功才写进状态。")
        if cannot_act(state, target):
            # 擒抱者已经倒下/无法行动：直接挣脱，不必再掷对抗
            await apply_named_condition(state, actor, GRAPPLE, add=False,
                                        reason=f"{target} 已无法继续擒抱")
            return f"👐 {target} 已经无法行动，{actor} 轻易挣脱了擒抱。"
        escape_mod = max(athletics_modifier(state, actor), acrobatics_modifier(state, actor))
        success, line = await _resolve_contest_roll(
            state, actor=actor, target=target, actor_mod=escape_mod,
            defense=str(args.get("defense") or "str"), label=f"{actor} 逃脱擒抱",
            advantage=advantage, disadvantage=disadvantage)
        if success:
            await apply_named_condition(state, actor, GRAPPLE, add=False, reason="挣脱擒抱")
            return line + f"\n{actor} 挣脱了{target}的擒抱。"
        return line + f"\n{actor} 仍被{target}擒抱着。"

    if action not in _GRAPPLE_ACTIONS + _SHOVE_ACTIONS:
        return "⚠ resolve_contest 需要 action：grapple（擒抱）/ shove（推撞）/ escape（逃脱）"
    if is_player_name(state, actor) and is_player_name(state, target):
        return f"⚠ {target} 就是{actor}自己，请把 target 写成对手的名字"

    blocked = can_action_target(state, actor, target)
    if blocked:
        return f"⚠ {blocked}"

    attacker_mod = athletics_modifier(state, actor)
    if action in _SHOVE_ACTIONS:
        mode = str(args.get("mode") or args.get("shove_mode") or "prone").strip().lower()
        label = f"{actor} 推撞（{'放倒' if mode not in ('push', '推开', '推开5尺') else '推开'}）"
    else:
        mode = ""
        label = f"{actor} 擒抱"
    detail = f"（{reason_note}）" if reason_note else ""

    if is_helpless(state, target):
        # 5e：目标无法行动时这类对抗自动成功，不必掷骰
        if action in _SHOVE_ACTIONS and mode in ("push", "推开", "推开5尺"):
            return f"🤼 {label}：{target} 无法行动，自动成功——把它推开 5 尺。{detail}"
        name = PRONE if action in _SHOVE_ACTIONS else GRAPPLE
        await apply_named_condition(state, target, name, add=True, reason=f"{label}（自动成功）")
        return f"🤼 {label}：{target} 无法行动，自动成功——{target} 获得「{name}」。{detail}"

    success, line = await _resolve_contest_roll(
        state, actor=actor, target=target, actor_mod=attacker_mod,
        defense=str(args.get("defense") or ""), label=label,
        advantage=advantage, disadvantage=disadvantage)
    if not success:
        return line + detail
    if action in _GRAPPLE_ACTIONS:
        await apply_named_condition(
            state, target, GRAPPLE, add=True, reason=f"被{actor}擒抱",
            extra={"grappled_by": actor})
        return line + f"\n{target} 被擒抱（速度归 0），可以用动作做逃脱检定挣脱。" + detail
    if mode in ("push", "推开", "推开5尺"):
        return line + f"\n{target} 被推开 5 尺（用 set_tactical_state 更新距离档位）。" + detail
    await apply_named_condition(state, target, PRONE, add=True, reason=f"被{actor}推倒")
    return line + f"\n{target} 被放倒，获得「{PRONE}」（起身要花半速移动）。" + detail
