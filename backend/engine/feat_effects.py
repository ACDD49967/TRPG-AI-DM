"""特长（feats）被动效果：把图鉴里声明的 effect 真正接到结算上。

背景：`feats.py` 声明了 51 个 effect key，但此前只有 3 个被代码读取
（`concentration_advantage` / `ignore_cover` / `luck_points`）。玩家在 4/8/12…
级用属性提升换来的「警觉」「健壮」「运动员」，数值上完全没有变化——又是一类
"规则写了，但没有任何代码路径负责它"。

这里只接**确定性、可自动结算**的部分（需要 DM 临场判断的仍留在提示词里）：

- `initiative_bonus`       → 先攻加值（警觉 +5），落进先攻表
- `hp_bonus` / `future_level_hp_bonus` → 每级最大生命（健壮 +2/级），随升级增长
- `attr_choice` + `attr_bonus` → 加专长时按选择加属性（可重复调用，差值结算）
- `ac_bonus_dual_wield`    → 双持武器时 AC 加值（双持客 +1）
- `min_hit_die_heal`       → 生命骰最低治疗量（强健：2×CON 调整值）
- `speed_bonus`            → 移动力，写进给 DM 的角色信息

属性与生命都用"期望值 vs 已应用值"的差值同步（`sync`），所以加/删/反复调用都安全；
已应用值记录在 `character_info["feat_attr_bonuses"]` / `["feat_hp_bonus"]` 里。
"""
from __future__ import annotations

import re
from typing import Any

from backend.engine.feats import FEATS_LIST
from backend.engine.session import GameSessionState
from backend.engine.tool_shims import _game_system

_HP_PER_LEVEL_RE = re.compile(r"level\s*\*\s*(\d+)", re.I)
# 与前端 status/inventory.tsx 的 isWeapon 保持同一套判断：type 优先，名字兜底
_WEAPON_NAME_RE = re.compile(r"剑|斧|弓|弩|匕首|矛|锤|杖|棍|鞭|刀|枪|戟|链枷|战|刃")
# 重甲判定：项目里的简化甲名。"链甲衫/半身板甲"是中型甲，必须先排除
_HEAVY_ARMOR_EXCLUDE = ("链甲衫", "半身板甲")
_HEAVY_ARMOR_KEYS = ("板甲", "全身甲", "锁子甲", "环甲", "链甲")
_PHYSICAL_DAMAGE = {"钝击", "穿刺", "挥砍"}
_RANGED_NAME_RE = re.compile(r"弓|弩|枪|投掷|远程|射击|箭")


def catalog_entry(feat: Any) -> dict:
    """按 id 或 name 在图鉴里找到特长定义（找不到返回 {}）。"""
    if isinstance(feat, dict):
        keys = {str(feat.get("id") or ""), str(feat.get("name") or "")}
    else:
        keys = {str(feat)}
    keys.discard("")
    for entry in FEATS_LIST:
        if keys & {str(entry.get("id") or ""), str(entry.get("name") or "")}:
            return entry
    return {}


def _effects(state: GameSessionState) -> list[dict]:
    """当前角色身上所有特长的 effect（仅 5e；非 5e 局不套用这套图鉴）。"""
    if _game_system(state) != "dnd5e":
        return []
    out = []
    for feat in state.character_info.get("feats") or []:
        effect = (catalog_entry(feat).get("effect") or {})
        if effect:
            out.append(effect)
    return out


def _sum_effect(effects: list[dict], key: str) -> int:
    total = 0
    for effect in effects:
        try:
            total += int(effect.get(key) or 0)
        except (TypeError, ValueError):
            continue
    return total


def _spec_total(spec: Any, level: int) -> int:
    """把 hp_bonus 的写法折算成"当前等级下应得的加值"：2 / "level*2" / "3*level"。"""
    if isinstance(spec, str):
        match = _HP_PER_LEVEL_RE.search(spec)
        if match:
            return max(0, int(match.group(1)) * max(1, int(level or 1)))
        try:
            return max(0, int(spec))
        except ValueError:
            return 0
    try:
        return max(0, int(spec or 0))
    except (TypeError, ValueError):
        return 0


def initiative_bonus(state: GameSessionState) -> int:
    return _sum_effect(_effects(state), "initiative_bonus")


def speed_bonus(state: GameSessionState) -> int:
    return _sum_effect(_effects(state), "speed_bonus")


def min_hit_die_heal(state: GameSessionState) -> int:
    """生命骰每颗的最低治疗量（强健：CON 调整×2）。"""
    if not any("min_hit_die_heal" in effect for effect in _effects(state)):
        return 0
    try:
        con_mod = (int(state.character_info.get("attributes", {}).get("con", 10) or 10) - 10) // 2
    except (TypeError, ValueError):
        con_mod = 0
    return max(0, con_mod * 2)


def hp_bonus_total(state: GameSessionState) -> int:
    """特长在当前等级下应给的最大生命加值（健壮 = 2×等级）。

    图鉴里「健壮」同时写了 `hp_bonus: "level*2"` 与 `future_level_hp_bonus: 2`，
    两者说的是同一件事：写法已经按等级增长时不再叠加 future，否则会算成 4×等级。
    """
    level = max(1, int(state.character_info.get("level", 1) or 1))
    scaled = 0
    absolute = 0
    future = 0
    for effect in _effects(state):
        spec = effect.get("hp_bonus")
        if isinstance(spec, str) and _HP_PER_LEVEL_RE.search(spec):
            scaled += _spec_total(spec, level) // level
        else:
            absolute += _spec_total(spec, level)
        future += _spec_total(effect.get("future_level_hp_bonus"), 1)
    if scaled:
        return scaled * level + absolute
    return absolute + future * level


def is_weapon(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    if str(item.get("type") or "").lower() in ("weapon", "武器", "近战武器", "远程武器"):
        return True
    return bool(_WEAPON_NAME_RE.search(str(item.get("name") or "")))


def dual_wield_ac_bonus(info: dict) -> int:
    """双持客：两手都握武器时 AC +1。未装备两件武器则不加。"""
    inventory = info.get("inventory") or {}
    items = inventory.get("items", []) if isinstance(inventory, dict) else []
    equipped = [it for it in items if isinstance(it, dict) and it.get("equipped")]
    # 特长在身上 + 至少两件已装备武器，才给加值
    feat_bonus = 0
    for feat in info.get("feats") or []:
        effect = catalog_entry(feat).get("effect") or {}
        try:
            feat_bonus = max(feat_bonus, int(effect.get("ac_bonus_dual_wield") or 0))
        except (TypeError, ValueError):
            continue
    if not feat_bonus:
        return 0
    return feat_bonus if sum(1 for it in equipped if is_weapon(it)) >= 2 else 0


def wearing_heavy_armor(info: dict) -> bool:
    inventory = info.get("inventory") or {}
    items = inventory.get("items", []) if isinstance(inventory, dict) else []
    for item in items:
        if not isinstance(item, dict) or not item.get("equipped"):
            continue
        name = str(item.get("name") or "")
        if any(key in name for key in _HEAVY_ARMOR_EXCLUDE):
            continue
        if any(key in name for key in _HEAVY_ARMOR_KEYS):
            return True
    return False


def damage_reduction(state: GameSessionState, damage_type: str = "") -> int:
    """重甲大师：穿重甲时，钝击/穿刺/挥砍伤害减免 3（5e 只对非魔法武器生效）。"""
    canonical = str(damage_type or "").strip()
    if canonical and canonical not in _PHYSICAL_DAMAGE:
        return 0
    info = state.character_info
    total = 0
    for feat in info.get("feats") or []:
        effect = catalog_entry(feat).get("effect") or {}
        if not effect.get("heavy_armor_dr_3"):
            continue
        if wearing_heavy_armor(info):
            total += 3
    return total


def power_attack(state: GameSessionState, action_text: str = "") -> tuple[int, int, str]:
    """巨武器大师 / 神射手的「-5 命中 / +10 伤害」。

    返回 `(命中减值, 伤害加值, 来源名)`；没有对应特长（或远近战不匹配）时返回 `(0, 0, "")`。
    远程用「神射手」，其余按近战用「巨武器大师」——两个特长的 -5/+10 不能互相替代。
    """
    if _game_system(state) != "dnd5e":
        return 0, 0, ""
    ranged = bool(_RANGED_NAME_RE.search(str(action_text or "")))
    want = "power_shot_minus5_plus10" if ranged else "power_attack_minus5_plus10"
    for effect in _effects(state):
        if effect.get(want):
            return 5, 10, "神射手" if ranged else "巨武器大师"
    return 0, 0, ""


def power_feat_names(state: GameSessionState) -> list[str]:
    """角色拥有的、能开启 -5/+10 的特长名（用于给 DM 的可用提示）。"""
    keys = {"power_attack_minus5_plus10": "巨武器大师", "power_shot_minus5_plus10": "神射手"}
    names = []
    for effect in _effects(state):
        for key, label in keys.items():
            if effect.get(key) and label not in names:
                names.append(label)
    return names


# 后端不强行结算、但必须让主 DM 记住的特长机制（其余由代码兜底，见模块头注释）。
# 键 = feats.py 里的 effect key；值 = 给模型的短句（越短越省 token）。
_DM_JUDGED_HINTS: dict[str, str] = {
    "cannot_be_surprised": "不受突袭，隐藏敌人对你无优势",
    "trap_detection_advantage": "侦测陷阱/密门时感知检定优势",
    "trap_save_advantage": "陷阱伤害豁免优势",
    "long_range_no_disadvantage": "远程长射程无劣势",
    "ignore_disengage": "脱离近战不引发借机攻击",
    "opportunity_stops_movement": "借机攻击命中后目标停止移动",
    "no_ao_on_melee": "近战攻击不引发借机攻击",
    "difficult_terrain_dash_ok": "疾走不受困难地形影响",
    "climb_no_penalty": "攀爬不消耗额外移动",
    "stand_up_5ft": "起身只需 5 尺移动",
    "crossbow_no_disadvantage_melee": "近战中使用弩无劣势",
    "hand_crossbow_bonus_action": "每回合可用附赠动作射击手弩",
    "dual_wield_non_light": "可用非轻型武器双持",
    "bonus_attack_on_crit_kill": "暴击或击杀后可用附赠动作再攻击一次（action_source=bonus_action）",
    "shield_shove_bonus_action": "盾牌撞击为附赠动作",
    "shield_ac_to_dex_save": "持盾时 AC 加值也计入敏捷豁免",
    "polearm_bonus_d4_attack": "长柄武器可用附赠动作以 d4 柄击",
    "polearm_opportunity_on_enter": "敌人进入触及范围即触发借机攻击",
    "pin_action": "擒抱成功后可再用动作压制",
    "advantage_vs_grappled": "对被你擒抱的目标攻击有优势",
    "evasion_reaction": "可用反应把攻击转向邻近生物",
    "reaction_attack_on_ally_targeted": "敌人攻击队友时可用反应反击",
    "spell_as_opportunity_attack": "借机攻击可用戏法",
    "somatic_with_weapons": "持武器仍可完成法术姿势",
    "ritual_spell_access": "可仪式施法（不需要准备位）",
    "always_know_north": "始终知道北方",
    "perfect_recall_month": "可回忆过去一个月所见",
    "one_1st_level_spell_daily": "每天可免费施展一次一环法术",
    "two_cantrips": "额外掌握两个戏法",
    "inspiring_speech_temp_hp": "可用激励演讲给队友临时生命",
    "stabilize_restores_1hp": "稳定濒死同伴时同时恢复 1 HP",
    "short_rest_heal_bonus": "用治疗包短休治疗额外回复 1d6+4+等级",
    "ignore_element_resistance": "可无视元素抗性",
    "damage_1_as_2": "元素伤害 1 视作 2",
    "gain_three_proficiencies": "额外获得三项技能/工具熟练",
}
MAX_MECHANIC_HINTS = 6


def mechanic_hints(state: GameSessionState) -> list[str]:
    """需要主 DM 临场判断的特长机制（后端已自动结算的不在这里重复）。

    只列角色真正拥有的特长，并截断到 MAX_MECHANIC_HINTS 条——这段会进每一轮的
    角色信息，必须控 token（6 条约 120-200 字符）。
    """
    hints: list[str] = []
    for effect in _effects(state):
        for key, text in _DM_JUDGED_HINTS.items():
            if effect.get(key) and text not in hints:
                hints.append(text)
    return hints[:MAX_MECHANIC_HINTS]


__all__ = [
    "catalog_entry", "initiative_bonus", "speed_bonus",
    "min_hit_die_heal", "hp_bonus_total", "dual_wield_ac_bonus", "is_weapon",
    "damage_reduction", "wearing_heavy_armor",
    "power_attack", "power_feat_names",
    "mechanic_hints", "MAX_MECHANIC_HINTS",
]
