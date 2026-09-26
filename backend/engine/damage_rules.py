"""伤害类型与抗性/免疫/易伤、生物豁免加值的确定性规则。

设计目标（"后端化"）：这些是纯规则计算，不该让 LLM 每次即兴判断。
数据来源杂（5etools 英文文本、内置中文卡、4e 的反射/强韧/意志），
所以统一从卡面文本里解析，解析不到就按属性推导。

伤害类型归一/推断/武器映射 → `damage_types`，生物豁免加值 → `damage_saves`，
这里只留"抗性/免疫/易伤"的文本解析与伤害倍率，并把上面两者再导出。
"""
from __future__ import annotations

import re
from typing import Any

from backend.engine.damage_saves import (  # noqa: F401  再导出
    _ABILITY_KEYS,
    _FOUR_E_DEFENSE,
    ability_modifier,
    creature_save_modifier,
)
from backend.engine.damage_types import (  # noqa: F401  再导出
    DAMAGE_TYPES,
    _TYPE_LOOKUP,
    _collect_text,
    canonical_damage_type,
    infer_damage_type,
    weapon_damage_type,
)
def _aliases(canonical: str) -> tuple[str, ...]:
    return DAMAGE_TYPES.get(canonical, (canonical,))


# 修饰词：与伤害类型绑定的规则词
_MODIFIERS: dict[str, tuple[str, ...]] = {
    "immunity": ("immunity", "免疫"),
    "resistance": ("resistance", "抗性"),
    "vulnerability": ("vulnerability", "易伤"),
}

# 解析时要忽略的填充词（"resistance to fire damage" 里的 to/damage）
_FILLERS = ("to", "damage", "任何", "所有", "类型", "的", "受到", "以及",
            "对", "于", "and", "or")
_CHAIN_LIMIT = 60        # 修饰词往后扫描的最大字符数
# "状态免疫：中毒" 说的是状态免疫（condition immunity），不是毒素伤害免疫。
# 伤害管线只看伤害，所以这类写法里的"免疫"要跳过，否则免疫中毒状态的构装体会被
# 误判成免疫毒素伤害（实测踩过：状态免疫：中毒 → 毒素伤害变 0）。
_CONDITION_PREFIXES = ("状态", "condition")


def _type_in_chunk(chunk: str) -> str:
    """片段里最先出现的伤害类型；没有则返回空串。"""
    text = chunk.lower()
    for filler in _FILLERS:
        text = text.replace(filler, " ")
    best_at, best = len(text) + 1, ""
    for canonical, aliases in DAMAGE_TYPES.items():
        for alias in aliases:
            index = text.find(alias.lower())
            if 0 <= index < best_at:
                best_at, best = index, canonical
    return best


def _chunk_is_filler(chunk: str) -> bool:
    text = chunk.lower()
    for filler in _FILLERS:
        text = text.replace(filler, " ")
    return not re.sub(r"[\s：:()（）\[\]【】,，、]", "", text)


def _clauses(text: str) -> list[str]:
    """按句读切分（；;。.！!？? 为边界）——修饰词的作用范围不会跨子句。"""
    return [part for part in re.split(r"[。\n.；;！!？?]", text) if part.strip()]


def _forward_types(text: str) -> set[str]:
    """修饰词之后的类型链：'to X, Y and Z' / '：火焰、冷冻'。"""
    out: set[str] = set()
    window = text[:_CHAIN_LIMIT]
    for part in re.split(r"[，,、/]|\s+and\s+|\s+or\s+|和|与|及|或", window):
        # 列表里若出现了别的修饰词（"但对挥砍有抗性"），说明进入下一个描述了
        if any(word in part.lower() for words in _MODIFIERS.values() for word in words):
            break
        chunk_type = _type_in_chunk(part)
        if chunk_type:
            out.add(chunk_type)
            continue
        if _chunk_is_filler(part):
            continue
        break
    return out


def _nearest_type_before(text: str) -> str:
    """修饰词之前（同一子句内）最近的伤害类型，用于"火焰抗性 / 对雷鸣易伤"这类写法。"""
    best_at, best = -1, ""
    for canonical, aliases in DAMAGE_TYPES.items():
        for alias in aliases:
            index = text.rfind(alias.lower())
            if index > best_at:
                best_at, best = index, canonical
    return best


def _bound_types(text: str, modifier: str) -> set[str]:
    """把某个修饰词（免疫/抗性/易伤）绑定到它作用在哪些伤害类型上。

    规则：**修饰词之后**的类型链优先（immunity to A, B and C / 抗性：火焰、冷冻）；
    之后没有类型时，才回退到**修饰词之前**最近的类型（火焰抗性）。

    这样「挥砍 挥砍抗性 免疫毒素」里的"免疫"只会绑到它后面的毒素，
    不会跨子句把前面的挥砍也算成免疫——实测踩过这个坑。
    """
    bound: set[str] = set()
    for clause in _clauses(text.lower()):
        start = 0
        while True:
            index = clause.find(modifier, start)
            if index < 0:
                break
            if any(word in clause[max(0, index - 8):index] for word in _CONDITION_PREFIXES):
                start = index + len(modifier)
                continue
            forward = _forward_types(clause[index + len(modifier):])
            if forward:
                bound |= forward
            else:
                before = _nearest_type_before(clause[:index])
                if before:
                    bound.add(before)
            start = index + len(modifier)
    return bound


def _has_modifier(text: str, canonical: str, kind: str) -> bool:
    lowered = text.lower()
    for modifier in _MODIFIERS[kind]:
        if modifier in lowered and canonical in _bound_types(lowered, modifier):
            return True
    return False




def damage_multiplier(entity: Any, damage_type: Any, extra_text: str = "") -> tuple[float, str]:
    """按 5e 规则返回 (伤害倍率, 说明)。

    免疫 → 0；抗性 → 0.5；易伤 → 2。同一类型多个来源不叠加（取最强的一条）。
    """
    canonical = canonical_damage_type(damage_type)
    if not canonical:
        return 1.0, ""
    text = _collect_text(entity, extra_text).lower()
    if not text.strip():
        return 1.0, ""

    # 修饰词按"最近绑定"解析：同一段文本里列出多个伤害类型时不会互相串台
    immunity = _has_modifier(text, canonical, "immunity")
    resistance = _has_modifier(text, canonical, "resistance")
    vulnerability = _has_modifier(text, canonical, "vulnerability")

    if immunity:
        return 0.0, f"免疫{canonical}"
    if resistance and vulnerability:
        # 5e：同时有抗性与易伤时互相抵消
        return 1.0, f"{canonical}抗性与易伤相互抵消"
    if resistance:
        return 0.5, f"{canonical}抗性"
    if vulnerability:
        return 2.0, f"{canonical}易伤"
    return 1.0, ""

