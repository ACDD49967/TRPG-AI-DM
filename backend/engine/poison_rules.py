"""毒药/毒素：抗毒识别 + `apply_poison` 工具实现。

5e 的毒药是"一次体质豁免决定伤害与中毒状态"的确定性结算：失败吃毒素伤害并「中毒」
（攻击检定与属性检定劣势，5.x 已建模），成功多数不吃伤害；矮人坚韧、怪物特性里的
抗毒会给这次豁免优势。此前 DM 要自己拼 save_damage + 状态写入两步，还得记住
"这个目标抗不抗毒"——现在一次调用交给后端。

数值来源：默认值只是占位（DC 11 / 1d4），真实毒性以图鉴卡或剧本为准，
DM 用 `dc` / `damage` 传进来即可；毒药形态（接触/摄入/吸入/伤害）只影响叙事措辞。
"""
from __future__ import annotations

from typing import Any

from backend.engine.session import GameSessionState

POISON_DAMAGE_TYPE = "毒素"
POISONED = "中毒"
POISONED_ROUNDS = 10          # 5e 常见毒药："中毒 1 分钟"，按 10 轮记
_DEFAULT_DC = 11
_DEFAULT_DAMAGE = "1d4"

_KIND_LABELS = {
    "contact": "接触",
    "ingested": "摄入",
    "injected": "伤口",
    "injury": "伤口",
    "inhaled": "吸入",
}
# "抗毒"类特性：出现这些字样就给对抗毒素的豁免优势（与 magic_resistance 同一套文本启发式）
_RESILIENCE_MARKERS = (
    "抗毒", "毒素抗性", "toxic resistance", "poison resistance",
    "dwarven resilience", "矮人坚韧", "对抗毒素的豁免有优势", "毒素豁免优势",
)


def _flatten(value: Any, parts: list[str]) -> None:
    if isinstance(value, str):
        if value.strip():
            parts.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            _flatten(item, parts)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _flatten(item, parts)


def has_poison_resilience(*sources: Any) -> bool:
    parts: list[str] = []
    for source in sources:
        _flatten(source, parts)
    text = "\n".join(parts).lower()
    return any(marker in text for marker in _RESILIENCE_MARKERS)


def _player_poison_sources(state: Any) -> list[Any]:
    info = getattr(state, "character_info", {}) or {}
    inventory = info.get("inventory")
    items = inventory.get("items") if isinstance(inventory, dict) else inventory
    equipped = [item for item in (items or [])
                if isinstance(item, dict) and item.get("equipped")]
    return [
        info.get("race_traits"), info.get("species_traits"), info.get("class_proficiencies"),
        info.get("feats"), info.get("damage_traits_notes"), info.get("active_effects"),
        [item.get("name") for item in equipped],
        [item.get("description") for item in equipped],
    ]


def poison_save_advantage(state: Any, target: str) -> str:
    """目标是否有对抗毒素的豁免优势；返回说明文本（没有则空串）。"""
    from backend.engine.player_damage import is_player_name

    target = str(target or "").strip()
    if target and is_player_name(state, target):
        return "抗毒" if has_poison_resilience(*_player_poison_sources(state)) else ""
    world = getattr(state, "world_state", None)
    npc = world.get_npc(target) if world is not None else None
    if npc is None:
        return ""
    if has_poison_resilience(getattr(npc, "traits", None) or [],
                             getattr(npc, "equipment", None) or [],
                             getattr(npc, "notes", "") or ""):
        return "抗毒"
    return ""


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in ("1", "true", "yes", "y", "是", "真")


def _int_arg(value: Any, default: int) -> int:
    try:
        return int(float(value)) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _first_value(args: dict, keys: tuple[str, ...]) -> Any:
    """按候选键名取第一个非空值（模型对参数名的猜测并不完全可预测）。"""
    for key in keys:
        value = (args or {}).get(key)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, (list, tuple)):
            value = value[0]
        return value
    return None


async def _exec_apply_poison(args: dict, state: GameSessionState) -> str:
    """毒素结算：体质豁免 → 失败吃伤害并「中毒」，抗毒目标豁免取优势。"""
    from backend.engine.combat_save_damage import _exec_save_damage
    from backend.engine.player_damage import is_player_name

    args = args or {}
    target = str(_first_value(args, ("target", "targets", "creature", "victim", "目标")) or "").strip()
    target = target or str(getattr(state, "character_name", "") or "玩家")
    if is_player_name(state, target):
        target = str(getattr(state, "character_name", "") or "玩家")
    dc = _int_arg(_first_value(args, ("dc", "poison_dc", "save_dc", "豁免dc")), _DEFAULT_DC)
    damage = _first_value(args, ("damage", "poison_damage", "damage_dice", "伤害"))
    if damage in (None, "", 0, "0"):
        damage = _DEFAULT_DAMAGE
    kind = str(_first_value(args, ("kind", "poison_kind", "类型")) or "").strip().lower()
    kind_label = _KIND_LABELS.get(kind, "")
    source_name = str(args.get("source") or args.get("reason") or "毒素").strip() or "毒素"

    # 抗毒：默认自动识别；DM 可以用 save_advantage 显式覆盖（例如喝了抗毒药剂）
    auto_note = poison_save_advantage(state, target)
    if "save_advantage" in args:
        advantage = _as_bool(args.get("save_advantage"))
        advantage_note = str(args.get("save_advantage_reason") or "").strip() or "抗毒"
        if not advantage:
            advantage_note = ""
    else:
        advantage = bool(auto_note)
        advantage_note = auto_note

    add_condition = _as_bool(args.get("condition", True))
    rounds = _int_arg(args.get("condition_rounds"), POISONED_ROUNDS if add_condition else 0)
    half_on_success = _as_bool(args.get("half_on_success", False))
    header = f"🧪 {source_name}" + (f"（{kind_label}型毒素）" if kind_label else "")
    header += f"：{target} 体质豁免 DC {dc}"
    detail = await _exec_save_damage({
        "targets": [target], "dc": dc, "damage": damage, "damage_type": POISON_DAMAGE_TYPE,
        "ability": "con", "half_on_success": half_on_success, "reason": source_name,
        "save_advantage": advantage, "save_advantage_reason": advantage_note,
        "condition_on_failure": POISONED if add_condition else "",
        "condition_rounds": rounds,
        "condition_description": f"{source_name}",
    }, state)
    lines = [header]
    if advantage_note:
        lines.append(f"（{target} 有抗毒：豁免优势）")
    lines.append(detail)
    return "\n".join(lines)
