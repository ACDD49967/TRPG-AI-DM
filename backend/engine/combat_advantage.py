"""攻击检定的优势/劣势裁定。

把 5e 中可由结构化状态直接判定的来源收敛到后端：
状态效果、俯卧、束缚/麻痹等受击状态、力竭、长射程与身处近战的远程攻击。
未建模的特殊来源（包抄、高台、特定法术/生物特性）仍允许 DM 通过
`advantage` + `advantage_reason` 声明，不会被固定流程封死。

词汇与数据模型（schema / AdvantageDecision）在 `combat_advantage_base`，
群体战术与阳光敏感在 `combat_advantage_env`；这里只留裁定逻辑并再导出两者。
"""
from __future__ import annotations

from typing import Any, Callable

from backend.engine.combat_advantage_base import (  # noqa: F401  再导出
    ATTACK_ADVANTAGE_SCHEMA,
    ENEMY_ATTACK_ADVANTAGE_SCHEMA,
    PLAYER_ATTACK_ADVANTAGE_SCHEMA,
    AdvantageDecision,
    _has,
    _norm,
    _parse_declared,
    _truthy,
    infer_attack_kind,
)
from backend.engine.combat_advantage_env import (  # noqa: F401  再导出
    _pack_tactics_source,
    _sunlight_disadvantage,
    in_sunlight,
)
from backend.engine.rules import AdvantageMode
def resolve_attack_advantage(
    *,
    attacker_text: str = "",
    target_text: str = "",
    attacker_exhaustion: int = 0,
    declared: Any = "",
    declared_reason: str = "",
    attack_kind: str = "",
    attacker_band: str = "",
    long_range: bool = False,
    has_feat_effect: Callable[[str], bool] | None = None,
    system: str = "dnd5e",
    extra_advantages: list[str] | None = None,
    extra_disadvantages: list[str] | None = None,
) -> AdvantageDecision:
    """裁定一次攻击的优势/劣势。

    `declared` 只在后端没有结构化来源时作为兜底，避免模型用一个参数
    覆盖已经存在的目盲/中毒/束缚等硬状态。
    """
    decision = AdvantageDecision()
    declared_mode = _parse_declared(declared)
    if system not in ("dnd5e", "dnd4e"):
        if declared_mode != AdvantageMode.NORMAL:
            decision.mode = declared_mode
            label = str(declared_reason or "DM 声明").strip()
            (decision.advantages if declared_mode == AdvantageMode.ADVANTAGE
             else decision.disadvantages).append(label)
        return decision

    attacker = _norm(attacker_text)
    target = _norm(target_text)
    kind = infer_attack_kind(explicit=attack_kind)
    feat = has_feat_effect or (lambda _key: False)

    if _has(attacker, "目盲", "失明", "blinded"):
        decision.disadvantages.append("攻击者目盲")
    if _has(attacker, "中毒", "poisoned"):
        decision.disadvantages.append("攻击者中毒")
    if _has(attacker, "俯卧", "倒地", "prone"):
        decision.disadvantages.append("攻击者俯卧")
    if _has(attacker, "束缚", "restrained"):
        decision.disadvantages.append("攻击者被束缚")
    if _has(attacker, "恐惧", "害怕", "frightened"):
        decision.disadvantages.append("攻击者恐惧")
    if int(attacker_exhaustion or 0) >= 3:
        decision.disadvantages.append("攻击者力竭3级")
    if _has(attacker, "隐形", "invisible", "隐藏", "hidden", "未被看见", "unseen"):
        decision.advantages.append("攻击者未被看见")

    if _has(target, "俯卧", "倒地", "prone"):
        if kind == "melee":
            decision.advantages.append("目标俯卧（近战）")
        else:
            decision.disadvantages.append("目标俯卧（远程）")
    if _has(target, "束缚", "restrained", "麻痹", "paralyzed", "震慑", "stunned",
            "昏迷", "unconscious", "石化", "petrified", "目盲", "blinded"):
        decision.advantages.append("目标无法有效防御")
    if _has(target, "隐形", "invisible", "隐藏", "hidden", "未被看见", "unseen"):
        decision.disadvantages.append("目标未被看见")
    if _has(target, "擒抱", "grappled", "束缚", "restrained") and feat("advantage_vs_grappled"):
        decision.advantages.append("擒抱专长")

    if kind == "ranged":
        if _has(attacker_band, "缠斗", "engaged", "近战"):
            if feat("crossbow_no_disadvantage_melee"):
                decision.neutral.append("弩专家抵消近战远程劣势")
            else:
                decision.disadvantages.append("远程攻击时身处近战")
        if long_range:
            if feat("long_range_no_disadvantage"):
                decision.neutral.append("神射手抵消长射程劣势")
            else:
                decision.disadvantages.append("远程长射程")

    decision.advantages.extend(str(x) for x in (extra_advantages or []) if str(x).strip())
    decision.disadvantages.extend(str(x) for x in (extra_disadvantages or []) if str(x).strip())

    if decision.advantages and decision.disadvantages:
        decision.mode = AdvantageMode.NORMAL
        decision.cancelled = True
    elif decision.advantages:
        decision.mode = AdvantageMode.ADVANTAGE
    elif decision.disadvantages:
        decision.mode = AdvantageMode.DISADVANTAGE
    elif declared_mode != AdvantageMode.NORMAL:
        decision.mode = declared_mode
        label = str(declared_reason or "DM 声明").strip()
        (decision.advantages if declared_mode == AdvantageMode.ADVANTAGE
         else decision.disadvantages).append(label)
    return decision


def player_attack_advantage(state: Any, args: dict, *, action: str, weapon: str = "",
                            enemy_npc: Any = None, system: str = "dnd5e",
                            player_name: str = "") -> AdvantageDecision:
    """从角色卡与参数组装玩家攻击的优势/劣势裁定。"""
    from backend.engine import battlefield, character_state

    info = state.character_info
    from backend.engine import light_rules

    enemy_name = str(getattr(enemy_npc, "name", "") or "")
    light_adv, light_dis = light_rules.visibility_reasons(
        state, player_name or str(getattr(state, "character_name", "") or "你"), enemy_name)
    attacker_text = " ".join([
        str(args.get("player_condition") or ""),
        " ".join(str(c) for c in (info.get("conditions") or [])),
    ])
    target_text = " ".join([
        str(args.get("enemy_condition") or ""),
        str(args.get("enemy_notes") or ""),
        " ".join(str(t) for t in getattr(enemy_npc, "traits", []) or []),
        " ".join(str(c) for c in getattr(enemy_npc, "conditions", []) or []),
    ])
    return resolve_attack_advantage(
        attacker_text=attacker_text,
        target_text=target_text,
        attacker_exhaustion=int(info.get("exhaustion") or 0),
        declared=args.get("advantage"),
        declared_reason=str(args.get("advantage_reason") or ""),
        attack_kind=infer_attack_kind(action, weapon, explicit=args.get("attack_kind")),
        attacker_band=battlefield.band_of(state, player_name),
        long_range=_truthy(args.get("long_range")),
        has_feat_effect=lambda key: character_state._has_feat_effect(state, key),
        system=system,
        extra_advantages=light_adv,
        extra_disadvantages=light_dis,
    )


def enemy_attack_advantage(state: Any, args: dict, *, enemy: str,
                           enemy_npc: Any = None, dice: str = "",
                           enemy_action: str = "", system: str = "dnd5e",
                           attacker_band: str = "") -> AdvantageDecision:
    """从 NPC 特性与玩家状态组装敌人攻击的优势/劣势裁定。"""
    traits_text = " ".join(str(t) for t in getattr(enemy_npc, "traits", []) or [])
    pack_tactics = _pack_tactics_source(state, enemy, traits_text)
    sunlight = _sunlight_disadvantage(state, traits_text)
    from backend.engine import light_rules

    light_adv, light_dis = light_rules.visibility_reasons(
        state, enemy, str(getattr(state, "character_name", "") or "玩家"))
    return resolve_attack_advantage(
        attacker_text=" ".join([
            traits_text,
            str(args.get("attacker_condition") or ""),
            " ".join(str(c) for c in getattr(enemy_npc, "conditions", []) or []),
        ]),
        target_text=" ".join([
            " ".join(str(c) for c in (state.character_info.get("conditions") or [])),
            str(args.get("player_condition") or ""),
        ]),
        declared=args.get("advantage"),
        declared_reason=str(args.get("advantage_reason") or ""),
        attack_kind=infer_attack_kind(enemy_action, dice, traits_text,
                                      explicit=args.get("attack_kind")),
        attacker_band=attacker_band,
        long_range=_truthy(args.get("long_range")),
        system=system,
        extra_advantages=([pack_tactics] if pack_tactics else []) + light_adv,
        extra_disadvantages=([sunlight] if sunlight else []) + light_dis,
    )
