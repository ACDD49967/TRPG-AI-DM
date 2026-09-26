"""范围/豁免伤害结算：`save_damage` 工具的实现（只留编排与汇总）。

从 `combat_damage` 拆出（那边只留门面与补丁契约说明），这一层再拆三段：

- `combat_save_common`：伤害数值、失败附带状态、裁定参数（`SaveDamageContext`）；
- `combat_save_player`：玩家侧（掩体、魔法抗性/声明的优势、力竭劣势、临时生命值）；
- `combat_save_creature`：生物侧（抗性/易伤、传奇抗性、亡灵坚韧、落库）。

这里只负责：解析目标与充能 → 建立裁定参数 → 逐个目标分派 → 汇总事件与叙事。
外部/测试的 import 面不变（`_exec_save_damage`、`_damage_amount` 等继续从这里取）。

**补丁契约**：测试用 `patch.object(combat_save_damage.random, "randint")` 控制骰值——
`patch.object` 改的是 `random` 模块自身的属性，所以两个分支里的 `random.randint`
一样会被替换；`_persist_combat_damage` 仍经 `_combat()` 在调用时取 `combat` 模块属性。
"""
from __future__ import annotations

import random  # noqa: F401  补丁面：测试打桩 combat_save_damage.random.randint

from backend.engine.combat_save_common import (  # noqa: F401  再导出，保持 import 面
    ABILITY_LABELS, SaveDamageContext, _apply_failure_condition, _combat, _damage_amount,
    build_context,
)
from backend.engine.combat_save_creature import apply_to_creature  # noqa: F401  再导出
from backend.engine.combat_save_player import apply_to_player  # noqa: F401  再导出
from backend.engine.combat_targets import _resolve_enemy_from_cards
from backend.engine.session import GameSessionState, push_event, push_narrative_token


def _targets(args: dict) -> list[str]:
    raw = args.get("targets")
    if isinstance(raw, str):
        raw = [raw]
    if not raw and args.get("target"):
        raw = [args["target"]]
    return [str(t).strip() for t in (raw or []) if str(t).strip()]


def _spend_recharge(args: dict, state: GameSessionState) -> str:
    """带充能的动作先过冷却：不允许时返回拒绝原因（空串表示放行）。"""
    actor = str(args.get("actor") or "")
    recharge_ability = str(args.get("recharge_ability") or "")
    if not actor:
        return ""
    from backend.engine import recharge_rules

    actor_npc = _resolve_enemy_from_cards(state, actor, {}).get("npc")
    if not recharge_ability:
        recharge_ability = recharge_rules.match_recharge_ability(
            actor_npc, str(args.get("reason") or args.get("damage_type") or ""))
    if not recharge_ability:
        return ""
    ok, reason = recharge_rules.recharge_available(state, actor, recharge_ability, actor_npc)
    if not ok:
        return reason
    recharge_rules.mark_recharge_used(state, actor, recharge_ability, actor_npc)
    return ""


async def _exec_save_damage(args: dict, state: GameSessionState) -> str:
    """多目标各掷豁免，失败全额、成功减半，并套用抗性/免疫/易伤。

    "后端化"的一部分：这类结算此前没有工具，DM 只能自己改 HP 或凭感觉描述，
    既容易出错，也无法在界面上体现。
    """
    args = args or {}
    targets = _targets(args)
    if not targets:
        return "⚠ save_damage 需要 targets（受影响的目标名列表）"
    blocked = _spend_recharge(args, state)
    if blocked:
        return blocked

    ctx = build_context(args)
    from backend.engine import player_damage

    lines = [ctx.header_line()]
    hit_targets: list[dict] = []
    for name in targets:
        if player_damage.is_player_name(state, name):
            # 玩家也能被范围伤害打中：走玩家侧管线（豁免 → 抗性/免疫/易伤 → 临时生命值）
            detail, hit = await apply_to_player(state, name, ctx)
        else:
            detail, hit = await apply_to_creature(state, name, ctx)
        lines.append(detail)
        if hit is not None:
            hit_targets.append(hit)

    summary = "\n".join(lines)
    await push_event(state, "game_event", {
        "type": "combat",
        "description": summary,
        "extra": {"reason": ctx.reason, "damage_type": ctx.damage_type,
                  "targets": hit_targets, "enemies": hit_targets},
    })
    await push_narrative_token(state, f"\n{summary}\n")
    return summary
