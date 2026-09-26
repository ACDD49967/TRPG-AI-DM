"""角色信息块：主 DM 每轮都要看到的角色卡摘要。

从 `backend/engine/dm_prompts.py` 拆出；系统提示装配在 dm_system_prompt，
父模块 `dm_prompts` 只做再导出（所有既有 import 与测试补丁语义不变）。
"""
from __future__ import annotations

from typing import Any

from backend.engine.character_state import _format_condition
from backend.engine.session import GameSessionState


def _play_mode(state: Any) -> str:
    from backend.engine import dm_agent
    return dm_agent._play_mode(state)


# ═══════════════════════════════════════════════════════════════
# 辅助
# ═══════════════════════════════════════════════════════════════


def build_character_info(state: GameSessionState) -> str:
    info = state.character_info
    attrs = info.get("attributes", {})
    inv = info.get("inventory", {})
    feats = info.get("feats", [])
    skills = info.get("skill_proficiencies", [])

    gender = info.get('gender', '未指定')
    char_class = info.get('char_class', '战士')
    # AC: 优先使用预计算值（来自create_new_game），否则动态计算
    ac = info.get('ac', 0)
    if not ac:
        dex = attrs.get("dex", 10)
        dex_mod = (dex - 10) // 2
        if char_class in ('战士', '圣武士'): ac = 16
        elif char_class == '游侠': ac = 14 + max(-2, min(2, dex_mod))
        elif char_class == '野蛮人': ac = 10 + dex_mod + (attrs.get("con", 10) - 10) // 2
        elif char_class == '武僧': ac = 10 + dex_mod + (attrs.get("wis", 10) - 10) // 2
        else: ac = 11 + dex_mod
        race_name = info.get('race', '')
        if '矮人' in race_name and '山地' in race_name: ac += 1
        ac = max(8, min(22, ac))

    system = info.get("game_system", "dnd5e")
    ac_line = f" | AC: {ac}" if system != "coc" else ""
    if system == "coc":
        identity_line = f"性别: {gender} | 身份: {char_class}（调查员）"
    else:
        identity_line = f"性别: {gender} | 种族: {info.get('race','人类')} | 职业: {char_class} | 等级: {info.get('level',1)}"
    lines = [
        f"姓名: {state.character_name}",
        identity_line,
        f"HP: {info.get('hp',30)}/{info.get('max_hp',30)}{ac_line} | 金币: {info.get('gold',10)}",
    ]

    if system == "dnd5e":
        lines.append(f"熟练加值: {info.get('proficiency_bonus', 2)} | 法术位: {info.get('spell_slots', [])}")
        resources = info.get("class_resources", [])
        if resources:
            lines.append("职业资源: " + " | ".join(f"{r.get('name')}: {r.get('current', 0)}/{r.get('max', 0)}" for r in resources))
        known_spells = info.get("known_spells", [])
        if known_spells:
            lines.append("已习得法术: " + "、".join(
                f"{s.get('name')}({s.get('level', '?')}环{s.get('school', '')})" for s in known_spells))
    elif system == "dnd4e":
        lines.append(f"回复力: {info.get('healing_surges', 0)}/{info.get('max_healing_surges', 0)} (每次 {info.get('surge_value', 0)} HP)")
        # 里程碑进度也交给 DM：否则它会自己"发"行动点，或忘了每两次遭遇才算一次
        done = int(info.get("encounters_since_extended_rest", 0) or 0)
        next_in = 2 - (done % 2)
        lines.append(f"行动点: {info.get('action_points', 1)} | 里程碑: 本次休息后 {done} 次遭遇（还差 {next_in} 次） | 防御: AC {info.get('ac', ac)} 强韧 {info.get('fortitude', 10)} 反射 {info.get('reflex', 10)} 意志 {info.get('will', 10)}")
    elif system == "coc":
        lines.append(f"MP: {info.get('mp', 0)} | SAN: {info.get('san', 0)} | 幸运: {info.get('luck', 0)} | 伤害加值: {info.get('damage_bonus', '0')}")
        if info.get("permanent_insanity"):
            lines.append("理智状态: 已永久疯狂（SAN 归零，不可逆）——描写要体现崩溃症状，不要当作正常调查员")

    known_spells_all = info.get("known_spells", [])
    if known_spells_all and system != "dnd5e":
        lines.append("已习得法术: " + "、".join(
            f"{s.get('name')}({s.get('level', '?')}环{s.get('school', '')})" for s in known_spells_all))

    # 自定义系统的规则文本此前只在 rules/combat 模块的规则块里出现，
    # 叙事/社交/场景等模块（以及子 Agent 的规则上下文）完全看不到它——
    # 而它就是这局的唯一规则来源，缺了只能靠模型自己编。
    # 角色信息在所有模块都会被追加，所以把精简版放这里；完整版仍在规则块里。
    if system == "custom":
        custom_rules = str(info.get("custom_rules") or "").strip()
        if custom_rules:
            head = custom_rules[:800]
            suffix = "…（完整规则见规则模块）" if len(custom_rules) > len(head) else ""
            lines.append(
                "本局自定义规则（必须遵守）: " + head + suffix
                + "｜判定骰以规则为准：规则要求 2d10/3d6 等时，dice_roll 必须传 dice=\"该骰式\"，不要默认 d20。")

    if attrs:
        names = {"str":"力","dex":"敏","con":"体","int":"智","wis":"感","cha":"魅"}
        if system == "coc":
            parts = [f"{names.get(k,k)}:{v}" for k, v in attrs.items()]
        else:
            parts = [f"{names.get(k,k)}:{v}({(v-10)//2:+d})" for k, v in attrs.items()]
        lines.append("属性: " + " | ".join(parts))

    skill_values = info.get("skills", {}) or {}
    if skill_values:
        lines.append("技能: " + "、".join(f"{k}:{v}" for k, v in skill_values.items() if v))
    elif skills:
        lines.append("技能熟练: " + ", ".join(skills))
    if info.get("custom_classes"):
        lines.append("剧本专属职业/身份: " + ", ".join(info["custom_classes"]))
    if info.get("custom_skills"):
        lines.append("剧本专属技能: " + ", ".join(info["custom_skills"]))
    if info.get("extra_attributes"):
        lines.append("额外属性: " + " | ".join(f"{k}:{v}" for k, v in info["extra_attributes"].items()))
    if feats:
        lines.append("特长: " + ", ".join(f["name"] for f in feats))
        # 后端已自动结算的先攻/生命/AC/减伤等不在这里重复；这里只提醒需要 DM 临场判断的机制，
        # 否则模型只能看到专长名，很容易漏掉"不受突袭 / 陷阱优势 / 借机攻击"这类细节。
        from backend.engine.feat_effects import mechanic_hints, speed_bonus
        hints = mechanic_hints(state)
        if hints:
            lines.append("特长机制: " + "；".join(hints))
        speed = speed_bonus(state)
        if speed:
            lines.append(f"移动力: {30 + speed} 尺（含特长加值 {speed} 尺）")
    conditions = info.get("conditions") or []
    if conditions:
        lines.append("当前状态效果: " + "；".join(_format_condition(c) for c in conditions))
    concentration = info.get("concentration")
    if isinstance(concentration, dict) and concentration.get("spell"):
        lines.append(f"正在专注: {concentration['spell']}（再施放需要专注的法术会中断当前法术）")

    items_list = inv.get("items", [])
    if items_list:
        names = [i.get("name", str(i)) if isinstance(i, dict) else str(i) for i in items_list]
        lines.append(f"背包: {', '.join(names)}")

    return "\n".join(lines)
