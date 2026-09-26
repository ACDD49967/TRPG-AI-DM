"""角色状态工具：状态写回、资源增减、法术位与已习得法术。

从 `backend/engine/tools.py` 拆出；那边只留 `DM_TOOLS` 装配与再导出。
`tests/test_module_layout.py` 的注册表一致性测试会核对 schema 与处理器一一对应。
"""
from backend.engine.tool_schemas import _tool


UPDATE_STATE_TOOL = _tool("update_state",
    "更新角色HP/MP/SAN/金币/经验/背包。数值键用增量(负数表示消耗)。"
    "物品用inventory_add/inventory_remove，改描述或改数量用inventory_update"
    "（{\"name\":\"旧名\",\"new_name\":\"新名\",\"description\":\"...\",\"quantity\":2}）。"
    "职业资源用键class_resource:<key>并写增量(如术法点sorcery_points、气ki_points、狂暴rage、诗人激励bardic_inspiration、"
    "圣疗lay_on_hands、引导神力channel_divinity、荒野形态wild_shape、回气second_wind、动作如潮action_surge、"
    "奥术回想arcane_recovery)；法术位用键spell_slots给完整剩余值，如{\"spell_slots\":[4,3,0,...],\"pact_slots\":2}。"
    "D&D4e行动点用action_points(0-3)（花行动点换额外行动时，combat_round 传 action_source=action_point，后端会自动扣点）。"
    "金币gold用直接赋值。"
    "特长用 feats_add/feats_remove（{\"name\":\"专长名\",\"description\":\"效果\"}，"
    "可用 attr_choice 指定属性加给谁，如{\"name\":\"运动员\",\"attr_choice\":\"dex\"}）；"
    "属性提升用 attributes_add（{\"str\":2}，上限 20，会自动重算豁免/被动感知/AC）；"
    "状态效果用 conditions_add/conditions_remove（{\"name\":\"中毒\",\"description\":\"攻击检定劣势\","
    "\"remaining_rounds\":3,\"damage_per_turn\":\"1d4\",\"damage_type\":\"毒素\","
    "\"save_dc\":13,\"save_ability\":\"con\"}），"
    "会显示在角色面板、回合末自动结算持续伤害/治疗、豁免结束并递减；"
    "习得/遗忘法术用 spells_known_add/spells_known_remove；"
    "物品用 inventory_add/inventory_remove/inventory_update；"
    "专注中断用 concentration_clear（受伤未过体质豁免、法术被解除或主动放弃时）。",
    {"changes": {"type":"object","description":"变更"},
     "reason": {"type":"string","description":"变化原因"}},
    ["changes","reason"])

GET_CHARACTER_STATE_TOOL = _tool("get_character_state",
    "以最小 token 返回角色当前状态摘要：HP/AC/金币/等级/职业资源/法术位/已习得法术。需要确认玩家现状或结算前后时调用，勿凭记忆推断。",
    {"fields": {"type": "array", "items": {"type": "string", "enum": ["core", "resources", "spell_slots", "known_spells", "inventory"]}}},
    [])

ADJUST_RESOURCE_TOOL = _tool("adjust_resource",
    "以最小 token 增减一个职业资源（自动限制在 0~上限）。resource 只填资源 key。",
    {"resource": {"type": "string", "enum": ["sorcery_points", "ki_points", "rage", "bardic_inspiration",
                                             "lay_on_hands", "channel_divinity", "wild_shape", "second_wind",
                                             "action_surge", "arcane_recovery", "action_points"]},
     "delta": {"type": "integer", "description": "正数恢复/获得，负数消耗"},
     "reason": {"type": "string"}},
    ["resource", "delta"])

CAST_SPELL_TOOL = _tool("cast_spell",
    "玩家施放一个法术时调用：自动扣减对应环位法术位（邪术师扣契约法术位），返回剩余法术位。level=法术环位，0环戏法不扣。"
    "需要专注的法术（如祝福术/魅惑人类/召唤类）传 concentration=true：同时只能维持一个专注法术，施放新专注法术会自动中断旧的；"
    "受伤时后端会自动掷体质豁免（DC = max(10, 伤害/2)），失败会自动中断专注；只需按结算文本叙述，无需自己掷或手动清除。",
    {"name": {"type": "string", "description": "法术名（用于记录）"},
     "level": {"type": "integer", "minimum": 0, "maximum": 9, "description": "法术环位"},
     "pact": {"type": "boolean", "description": "邪术师使用契约法术位时填 true"},
     "ritual": {"type": "boolean", "description": "以仪式方式施法：额外 10 分钟、不消耗法术位；需要法师/牧师/德鲁伊/吟游诗人或「仪式施法者」专长，且该法术有仪式版本"},
     "concentration": {"type": "boolean", "description": "该法术是否需要专注（5e）"}},
    ["level"])

LEARN_SPELL_TOOL = _tool("learn_spell",
    "玩家习得一个新法术后调用，写入角色卡已习得法术。法术详情应从 search_spells 结果或剧本图鉴中取，不要编造。",
    {"name": {"type": "string"},
     "level": {"type": "string", "description": "环位，如 0/1/2/3"},
     "school": {"type": "string"},
     "description": {"type": "string"},
     "casting_time": {"type": "string"},
     "range": {"type": "string"},
     "components": {"type": "string"},
     "duration": {"type": "string"},
     "classes": {"type": "array", "items": {"type": "string"}},
     "prepared": {"type": "boolean"}},
    ["name"])

FORGET_SPELL_TOOL = _tool("forget_spell",
    "玩家失去/遗忘一个已习得法术时调用。",
    {"name": {"type": "string"}},
    ["name"])
