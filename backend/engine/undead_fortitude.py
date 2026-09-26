"""亡灵坚韧（Undead Fortitude）：0 HP 时靠体质豁免站住。

规则：伤害把该生物打到 0 HP 时，它做一次 DC = 5 + 本次伤害的体质豁免；
光耀伤害或暴击不触发。成功则改为 1 HP。

交给后端的理由：DC 要按每次伤害算、还要区分伤害类型与是否暴击，
让 LLM 每次即兴判断既容易算错，也容易"忘了"这条特性。
"""
from __future__ import annotations

import random
import re
from typing import Any

_PATTERN = re.compile(r"undead\s+fortitude|亡灵坚韧|不死坚韧|不朽坚韧|亡骸坚韧", re.I)
_RADIANT = "光耀"


def _text_of(entity: Any) -> str:
    parts: list[str] = []
    for attr in ("traits", "special_abilities", "features", "description"):
        value = getattr(entity, attr, None)
        if isinstance(value, (list, tuple)):
            parts.extend(str(v) for v in value)
        elif value:
            parts.append(str(value))
    return " ".join(parts)


def has_undead_fortitude(entity: Any) -> bool:
    """特性名出现在 traits 等文本里即视为拥有。"""
    if entity is None:
        return False
    return bool(_PATTERN.search(_text_of(entity)))


def fortitude_dc(damage: int) -> int:
    """DC = 5 + 本次伤害，至少为 6。"""
    return 5 + max(1, int(damage or 0))


async def resolve_undead_fortitude(
    state: Any, npc: Any, name: str, *,
    damage: int, damage_type: str = "", critical: bool = False,
) -> dict:
    """结算亡灵坚韧。

    返回 ``{"applied": bool, "hp": int, "note": str, "roll": int, "dc": int}``。
    ``applied`` 为 True 时调用方应把该生物的血量改成 1；未触发则保持 0 HP。
    """
    if not has_undead_fortitude(npc):
        return {"applied": False, "hp": 0, "note": "", "roll": 0, "dc": 0}

    from backend.engine.damage_rules import canonical_damage_type, creature_save_modifier

    dc = fortitude_dc(damage)
    if canonical_damage_type(damage_type) == _RADIANT or critical:
        reason = "暴击压制" if critical else "光耀伤害压制"
        return {"applied": False, "hp": 0,
                "note": f"亡灵坚韧：{reason}，无法触发", "roll": 0, "dc": dc}

    mod, source = creature_save_modifier(npc, {}, "con")
    roll = random.randint(1, 20)
    total = roll + mod
    success = roll == 20 or (roll != 1 and total >= dc)
    note = (f"亡灵坚韧：DC{dc} 体质豁免 d20={roll}"
            f"{'+' if mod >= 0 else ''}{mod}={total} → "
            f"{'成功，以 1 HP 站住' if success else '失败'}")
    from backend.engine.session import push_event
    await push_event(state, "dice_roll", {
        "skill": f"{name} 亡灵坚韧·体质豁免", "dc": dc,
        "roll": roll, "modifier": mod, "source": source,
        "result": "成功" if success else "失败",
    })
    return {"applied": success, "hp": 1 if success else 0, "note": note,
            "roll": roll, "dc": dc}
