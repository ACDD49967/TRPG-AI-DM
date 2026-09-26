"""豁免伤害结算的公共部分：伤害数值、失败附带的状态、裁定参数。

从 `combat_save_damage` 拆出（那边只留编排）：玩家侧 → `combat_save_player`、
生物侧 → `combat_save_creature`。`combat_save_damage` 再导出这里的名字，
外部 import 面（含测试直接用的 `_damage_amount`）保持不变。

**补丁契约**：测试用 `patch.object(combat_save_damage.random, "randint")` 控制骰值——
`patch.object` 改的是 `random` 模块自身的属性，所以本模块与两个分支里的
`random.randint` 一样会被替换；`_persist_combat_damage` 仍经 `_combat()`
在调用时取 `combat` 模块属性，不打桩 `combat` 模块本身。
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.engine.session import GameSessionState
from backend.engine.tool_shims import _as_bool

ABILITY_LABELS = {"str": "力量", "dex": "敏捷", "con": "体质",
                  "int": "智力", "wis": "感知", "cha": "魅力"}
DEFAULT_DC = 13


def _combat():
    """延迟拿 combat 模块：保留测试对 combat.* 的打桩语义，同时避免模块级循环导入。"""
    from backend.engine import combat
    return combat


def _damage_amount(spec) -> int:
    """伤害参数：数字或纯数字字符串按固定值算，其余（如 8d6）按骰子表达式掷。

    模型把「22」写成字符串时，若一律丢进骰子解析会得到 0 伤害，这里统一收口。
    """
    if isinstance(spec, (int, float)):
        return int(spec)
    text = str(spec or "0").strip()
    try:
        return int(float(text))
    except ValueError:
        return _combat()._roll_damage_simple(text)


async def _apply_failure_condition(state: GameSessionState, target: str, name: str, *,
                                   reason: str, rounds: int = 0, note: str = "") -> str:
    """豁免失败时给目标附上状态（中毒/束缚等）。

    返回该写进日志的状态名；目标不存在或被免疫时返回空串（不要写成"已中毒"）。
    """
    from backend.engine.condition_apply import apply_named_condition
    from backend.engine.condition_rules import (
        condition_block_reason, creature_condition_immunities, player_condition_immunities,
    )
    from backend.engine.player_damage import is_player_name

    if is_player_name(state, target):
        immunities = player_condition_immunities(state)
    else:
        world = getattr(state, "world_state", None)
        npc = world.get_npc(str(target)) if world is not None else None
        if npc is None:
            return ""
        immunities = creature_condition_immunities(npc)
    if condition_block_reason(name, immunities):
        return ""
    await apply_named_condition(
        state, target, name, add=True,
        reason=note or f"{reason}：豁免失败", rounds=rounds)
    return name


@dataclass(frozen=True)
class SaveDamageContext:
    """一次范围/豁免伤害结算的裁定参数（两个分支共用，避免长参数表）。"""

    ability: str
    ability_label: str
    dc: int
    base_damage: int
    damage_type: str
    magic: bool
    half_on_success: bool
    reason: str
    extra_advantage: bool = False
    extra_advantage_reason: str = ""
    condition_on_failure: str = ""
    condition_rounds: int = 0
    condition_note: str = ""
    legendary_resistance: bool = False

    def header_line(self) -> str:
        return (f"💥 {self.reason}：{self.ability_label}豁免 DC {self.dc}，"
                f"基础伤害 {self.base_damage}"
                + (f"（{self.damage_type}）" if self.damage_type else ""))


def build_context(args: dict) -> SaveDamageContext:
    """把工具参数归一成一份裁定参数（缺省与容错都集中在这里）。"""
    from backend.engine.damage_rules import canonical_damage_type

    args = args or {}
    ability = str(args.get("ability") or "dex").lower()
    if ability not in ABILITY_LABELS:
        ability = "dex"
    try:
        dc = int(args.get("dc") or DEFAULT_DC)
    except (TypeError, ValueError):
        dc = DEFAULT_DC
    try:
        condition_rounds = int(args.get("condition_rounds") or 0)
    except (TypeError, ValueError):
        condition_rounds = 0
    return SaveDamageContext(
        ability=ability,
        ability_label=ABILITY_LABELS[ability],
        dc=dc,
        base_damage=_damage_amount(args.get("damage")),
        damage_type=canonical_damage_type(args.get("damage_type")),
        magic=_as_bool(args.get("magic")),
        half_on_success=_as_bool(args.get("half_on_success", True)),
        reason=str(args.get("reason") or f"{ability.upper()} 豁免"),
        # 额外声明项：毒素抗性之类的"豁免优势"，以及失败时附带的状态（中毒等）
        extra_advantage=_as_bool(args.get("save_advantage")),
        extra_advantage_reason=str(args.get("save_advantage_reason") or "").strip(),
        condition_on_failure=str(args.get("condition_on_failure") or "").strip(),
        condition_rounds=condition_rounds,
        condition_note=str(args.get("condition_description") or ""),
        legendary_resistance=_as_bool(args.get("legendary_resistance")),
    )
