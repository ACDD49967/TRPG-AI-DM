"""骰子裁判：d20 检定、COC 的 d100、自定义规则里的任意骰式。

从 session_tools 拆出：它是规则裁决里最独立的一块（只依赖 rules 与事件推送），
拆开后 session_tools 回到「记忆/装备/休息」这些会话类工具的职责。
"""
from __future__ import annotations

import random
import re

from backend.engine.rules import (
    AdvantageMode, ability_mod_for_skill, parse_dice_expression, skill_check,
)
from backend.engine.session import (
    GameSessionState, push_event, push_narrative_token,
)
from backend.engine.tool_shims import _game_system


def dice_from_custom_rules(info: dict) -> tuple[int, int] | None:
    """从自定义规则文本里找出玩家声明的判定骰（优先非 d20 的骰式）。

    玩家的规则就是这局的规则来源；不能指望模型每次都自觉传 dice 参数，
    所以后端直接把规则里写明的骰式当作默认骰。
    """
    text = str((info or {}).get("custom_rules") or "").lower()
    for token in re.findall(r"\d{0,2}d\d{1,4}", text):
        parsed = parse_dice_expression(token)
        if parsed is not None and parsed != (1, 20):
            return parsed
    return None


async def _exec_dice_roll(args: dict, state: GameSessionState) -> str:
    skill = args["skill_name"]
    dc = args.get("dc", 15)
    system = _game_system(state)

    # 休息/生命骰恢复由 take_rest 结算（自动恢复 HP 与职业资源），
    # 用 d20 检定来表示“短休恢复量”既不合规则也会误导玩家。
    if any(token in str(skill) for token in ("短休", "长休", "生命骰", "休息", "恢复量")):
        return (
            "⚠ 休息与生命骰恢复不需要掷 d20：请调用 take_rest"
            "（rest_type=short/long），HP、法术位与职业资源会按规则自动结算。"
        )

    if system == "coc":
        # COC 7e：d100 百分比检定
        target = max(1, min(99, dc + int(args.get("modifier", 0) or 0)))
        roll = random.randint(1, 100)
        if roll <= 5 or (target > 0 and roll <= max(1, target // 5)):
            result = "极限成功"
        elif roll <= target // 2:
            result = "困难成功"
        elif roll <= target:
            result = "成功"
        elif roll >= 96 and roll > target:
            result = "大失败"
        else:
            result = "失败"
        line = f"🎲 {skill}: d100={roll} vs {target}% → {result}"
        await push_event(state, "dice_roll", {
            "skill": skill, "dc": target, "roll": roll, "modifier": 0,
            "result": result,
            # 前端战斗记录直接显示 display，避免它按 d20 模板拼出错误的骰名
            "display": f"{skill}: d100={roll} vs {target}% → {result}",
        })
        if result in ("极限成功", "困难成功", "大失败"):
            line += f" [{'克苏鲁神话在低语…' if result=='大失败' else '漂亮的检定！'}]"
        await push_narrative_token(state, f"\n{line}\n")
        return line

    # 自定义规则系统：玩家的规则可以规定别的判定骰（如 2d10 取和对抗目标值）。
    # 只对 custom 生效——5e/4e 有各自规范的 d20，不能让模型用参数改掉；
    # 骰式仍由后端解析与投掷，避免"叙事里写 2d10、工具实际掷 d20"这种前后不一。
    if system == "custom":
        parsed = parse_dice_expression(str(args.get("dice") or ""))
        if parsed is None or parsed == (1, 20):
            # 模型没声明骰式时，按玩家规则里写的骰式投掷（例如规则写着"用 2d10"）
            parsed = dice_from_custom_rules(state.character_info)
        if parsed is not None and parsed != (1, 20):
            count, faces = parsed
            rolls = [random.randint(1, faces) for _ in range(count)]
            modifier = int(args.get("modifier", 0) or 0)
            total = sum(rolls) + modifier
            result = "成功" if total >= dc else "失败"
            formula = f"{count}d{faces}=" + "+".join(str(r) for r in rolls)
            if modifier:
                formula += f"{modifier:+d}"
            formula += f"={total}"
            await push_event(state, "dice_roll", {
                "skill": skill, "dc": dc, "roll": total, "modifier": modifier,
                "result": result, "formula": formula, "dice": f"{count}d{faces}",
                "display": f"{skill}: {formula} vs DC{dc} → {result}",
            })
            line = f"🎲 {skill}: {formula} vs DC{dc} → {result}"
            await push_narrative_token(state, f"\n{line}\n")
            return line

    # dnd5e / dnd4e / custom：默认 d20 检定
    attrs = state.character_info.get("attributes", {})
    auto_mod = ability_mod_for_skill(skill, attrs)
    # 熟练加值：1-4级=+2, 5-8级=+3, 9-12级=+4
    level = state.character_info.get("level", 1)
    prof_bonus = 2 if level <= 4 else 3 if level <= 8 else 4 if level <= 12 else 5
    # 检查是否有对应技能的熟练项
    skills = state.character_info.get("skill_proficiencies", [])
    is_proficient = any(s in skill for s in skills)
    modifier = auto_mod + (prof_bonus if is_proficient else 0)
    # 检查特长影响
    for f in state.character_info.get("feats", []):
        if f.get("id") == "lucky": modifier += 0  # 幸运点由AI决定是否使用

    adv_str = args.get("advantage", "normal")
    try: advantage = AdvantageMode(adv_str)
    except ValueError: advantage = AdvantageMode.NORMAL

    # 力竭 1 级起：属性检定劣势（5e/4e）。模型声明的优势与它抵消，
    # 不让"力竭"只停留在提示词里由 AI 自觉。
    exhaustion_note = ""
    try:
        from backend.engine.time_supplies import exhaustion_level
        if system in ("dnd5e", "dnd4e") and exhaustion_level(state) >= 1:
            if advantage == AdvantageMode.ADVANTAGE:
                advantage = AdvantageMode.NORMAL
                exhaustion_note = "力竭1级：检定劣势（与优势抵消）"
            elif advantage == AdvantageMode.NORMAL:
                advantage = AdvantageMode.DISADVANTAGE
                exhaustion_note = "力竭1级：检定劣势"
    except Exception:
        exhaustion_note = ""

    roll = skill_check(skill, dc, modifier, advantage)
    roll_event = {**roll.to_event_data(), "modifier": modifier}
    if exhaustion_note:
        roll_event["advantage"] = advantage.value
        roll_event["advantage_note"] = exhaustion_note
    await push_event(state, "dice_roll", roll_event)

    internal = ""
    if roll.result.value == "大成功":
        internal = "【自然20——命运在这一刻换了边站。给玩家一个他们不会忘记的时刻。】"
    elif roll.result.value == "大失败":
        internal = "【自然1——灾难悄然而至。要有后果，但要让它有趣到玩家事后会笑着说'还记得那次吗'。】"

    line = f"🎲 {skill}: d20={roll.roll}"
    if modifier: line += f"{'+' if modifier>=0 else ''}{modifier}"
    line += f"={roll.total} vs DC{dc} → {roll.result.value}"
    if is_proficient: line += " [熟练]"
    if exhaustion_note:
        line += f" [{exhaustion_note}]"

    # 兜底：模型有时用通用 dice_roll 代替 death_saving_throw 来掷死亡豁免，
    # 这种情况也要记进“本回合已掷”，否则回合末的自动补掷会多掷一次。
    if "死亡" in str(skill) or "death" in str(skill).lower():
        ws = getattr(state, "world_state", None)
        state._death_save_turn = int(getattr(ws, "turn_count", 0) or 0)

    # 玩家看到的只有骰子结果；内部指导只返回给 LLM，不推送到叙事流
    await push_narrative_token(state, f"\n{line}\n")
    return line + (f"\n{internal}" if internal else "")
