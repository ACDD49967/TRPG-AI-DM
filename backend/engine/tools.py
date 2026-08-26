"""AI 跑团主持工具集——OpenAI/DeepSeek function-calling 格式。"""

def _tool(name, desc, props, required=None):
    return {
        "type": "function",
        "function": {
            "name": name, "description": desc,
            "parameters": {"type": "object", "properties": props,
                           "required": required or list(props.keys())},
        },
    }

# ── 核心游戏工具 ──

DICE_ROLL_TOOL = _tool("dice_roll",
    "D20技能检定。玩家有风险的行为时调用。modifier=对应属性调整值。DC:5极简10简15中20难25极难30传奇。",
    {"skill_name": {"type":"string","description":"检定名"},
     "dc": {"type":"integer","description":"难度等级"},
     "modifier": {"type":"integer","description":"属性调整值，默认0"},
     "advantage": {"type":"string","enum":["normal","advantage","disadvantage"]}},
    ["skill_name","dc"])

UPDATE_STATE_TOOL = _tool("update_state",
    "更新角色HP/MP/SAN/金币/经验/背包。数值键用增量(负数表示消耗)。物品用inventory_add/inventory_remove。"
    "职业资源用键class_resource:<key>并写增量(如术法点sorcery_points、气ki_points、狂暴rage、诗人激励bardic_inspiration、"
    "圣疗lay_on_hands、引导神力channel_divinity、荒野形态wild_shape、回气second_wind、动作如潮action_surge、"
    "奥术回想arcane_recovery)；法术位用键spell_slots给完整剩余值，如{\"spell_slots\":[4,3,0,...],\"pact_slots\":2}。"
    "D&D4e行动点用action_points(0-3)。金币gold用直接赋值。",
    {"changes": {"type":"object","description":"变更"},
     "reason": {"type":"string","description":"变化原因"}},
    ["changes","reason"])

COMBAT_ROUND_TOOL = _tool("combat_round",
    "【必须调用】结算一轮战斗。只传 player_action 与 enemy_name 即可：工具会自动从角色卡计算玩家攻击/伤害，并从 NPC 卡或生物图鉴卡取敌人 AC/HP/攻击，结算后自动把伤害写回该实体的 HP。若实体尚未入册，先调 update_world_state(add_npc) 或 add_scenario_bestiary。",
    {"player_action": {"type":"string", "description": "玩家本轮动作"},
     "player_attack_modifier": {"type":"integer", "description": "可选，缺省自动按角色卡属性+熟练计算"},
     "player_damage_dice": {"type":"string", "description": "可选，缺省自动取背包武器伤害"},
     "enemy_name": {"type":"string", "description": "必须与NPC卡/图鉴卡名称一致"},
     "enemy_ac": {"type":"integer", "description": "可选，缺省取实体卡AC"},
     "enemy_attack_modifier": {"type":"integer", "description": "可选，缺省按实体卡属性计算"},
     "enemy_damage_dice": {"type":"string", "description": "可选，缺省从实体卡特性/动作解析"},
     "enemy_hp": {"type":"integer", "description": "可选，缺省取实体卡当前HP"}},
    ["player_action", "enemy_name"])

DEATH_SAVE_TOOL = _tool("death_saving_throw",
    "角色HP≤0时每回合必须掷死亡豁免。d20≥10=成功, 自然20=恢复1HP, 自然1=2次失败。累计3成功=稳定, 3失败=死亡。",
    {}, [])

REST_TOOL = _tool("take_rest",
    "短休(消耗生命骰恢复HP，并恢复气/引导神力/荒野形态/回气/动作如潮/奥术回想/契约法术位)或长休(HP/MP/法术位/职业资源/回复力全部恢复,行动点重置为1)。",
    {"rest_type": {"type":"string","enum":["short","long"]}},
    ["rest_type"])

ADD_MEMORY_TOOL = _tool("add_memory",
    "记录重要剧情事实到长期记忆。获得重要物品/杀死关键NPC/解锁区域/重大转折时调用。",
    {"memory_text": {"type":"string","description":"事实陈述"},
     "importance": {"type":"number","minimum":0.0,"maximum":1.0}},
    ["memory_text"])

SUGGEST_CHOICES_TOOL = _tool("suggest_choices",
    "玩家不知所措时给2-4个有趣的具体建议。",
    {"options": {"type":"array","items":{"type":"string"},"minItems":2,"maxItems":4}},
    ["options"])

# ── 世界状态工具 ──

UPDATE_WORLD_STATE_TOOL = _tool("update_world_state",
    "修改持久化世界状态——仅在玩家行动已被检定/判定生效后调用。更新NPC/旗标/地点。",
    {"action": {"type":"string","enum":["update_npc","add_npc","set_flag","add_location","set_world_rule"]},
     "target": {"type":"string"},
     "changes": {"type":"object"},
     "reason": {"type":"string"}},
    ["action","target","changes","reason"])

REVEAL_INFO_TOOL = _tool("reveal_info",
    "【高频使用】当玩家通过检定/对话/探索揭示了之前隐藏的信息时调用。揭示NPC隐藏字段(性格/动机/秘密等)、发现新地点、公开旗标。信息应随玩家努力逐步解锁——不要一次性揭示全部。每次揭示后更新场景描述。",
    {"target_type": {"type":"string","enum":["npc_field","npc_all","location","flag","secret"]},
     "target_name": {"type":"string","description":"NPC名/地点名/旗标键"},
     "field": {"type":"string","description":"字段: appearance/personality/motivation/secret/relation_to_plot"},
     "trigger": {"type":"string","description":"触发揭示的玩家行动和检定结果(如: 洞察检定d20=18成功)"}},
    ["target_type","target_name","trigger"])

UPDATE_SCENE_TOOL = _tool("update_scene",
    "【高频使用】更新当前场景信息。玩家移动/时间流逝/天气变化/NPC进出时调用。几乎每轮都应检查。",
    {"current_location": {"type":"string","description":"当前位置"},
     "current_time": {"type":"string","description":"游戏内时间"},
     "weather": {"type":"string"},
     "atmosphere": {"type":"string","description":"氛围描述"},
     "visible_npcs_here": {"type":"array","items":{"type":"string"},"description":"当前在场的NPC名列表"}},
    [])

ADD_CHARACTER_NOTE_TOOL = _tool("add_character_note",
    "添加角色视角笔记——以玩家角色的口吻评价NPC、事件或记录线索。每轮重要互动后调用。使用第一人称，符合角色的种族/职业/属性特点。如：野蛮人会说'这家伙看着不靠谱，但拳头够硬'；法师会说'此人的言行暗示他掌握了某种我不熟悉的奥术知识'。",
    {"target": {"type":"string","description":"目标名称(NPC名/事件/地点)"},
     "target_type": {"type":"string","enum":["npc","event","quest","location"],
                     "description":"笔记类型：npc=人物评价, event=事件记录, quest=任务线索, location=地点印象"},
     "comment": {"type":"string","description":"角色视角的简短评价(1-2句,第一人称,符合角色性格)"},
     "clue": {"type":"string","description":"相关线索或推论(如有,可选)"}},
    ["target","target_type","comment"])

UPDATE_BESTIARY_TOOL = _tool("update_bestiary_entry",
    "游戏中临时修改/新增生物图鉴条目（仅本局生效，不写入知识库）。用于玩家遭遇变异、NPC透露新情报等。",
    {"name": {"type": "string", "description": "生物名称"},
     "changes": {"type": "object", "description": "要修改/新增的字段，如 description/stats/details"},
     "reason": {"type": "string"}},
    ["name", "changes", "reason"])

UPDATE_CITY_TOOL = _tool("update_city_entry",
    "游戏中临时修改/新增城市/地点背景（仅本局生效，不写入知识库）。用于玩家探索后发现新信息。",
    {"name": {"type": "string", "description": "城市/地点名称"},
     "changes": {"type": "object", "description": "要修改/新增的字段，如 description/details/locations"},
     "reason": {"type": "string"}},
    ["name", "changes", "reason"])

ADD_SCENARIO_BESTIARY_TOOL = _tool("add_scenario_bestiary",
    "在当前剧本中新增一个生物图鉴条目（仅当前剧本生效，不写入知识库）。用于遭遇新怪物、NPC召唤物或特殊生物时。",
    {"name": {"type": "string", "description": "生物名称"},
     "description": {"type": "string", "description": "外观/习性或背景简述"},
     "stats": {"type": "object", "description": "数值，如 HP/AC/攻击/技能等"},
     "tags": {"type": "array", "items": {"type": "string"}, "description": "标签，如 人形生物/神话生物"}},
    ["name"])

ADD_SCENARIO_MAP_TOOL = _tool("add_scenario_map",
    "在当前剧本中新增一张地图（仅当前剧本生效，不写入知识库）。用于发现新区域、进入地城或需要展示场景布局时。",
    {"name": {"type": "string", "description": "地图/地点名称"},
     "description": {"type": "string", "description": "区域描述"},
     "locations": {"type": "array", "items": {"type": "object"}, "description": "可选地点标记 [{name,x,y}]"}},
    ["name"])

ADD_SCENARIO_SPELL_TOOL = _tool("add_scenario_spell",
    "在当前剧本中新增法术/仪式（仅当前剧本生效，不写入知识库）。用于玩家习得新法术、发现仪式或需要展示施法细节时。",
    {"name": {"type": "string", "description": "法术/仪式名称"},
     "description": {"type": "string", "description": "效果描述"},
     "level": {"type": "string", "description": "环位，如 0/1/2"},
     "school": {"type": "string", "description": "学派，如 防护/塑能"},
     "ritual": {"type": "boolean", "description": "是否仪式"},
     "casting_time": {"type": "string"},
     "range": {"type": "string"},
     "components": {"type": "string"},
     "duration": {"type": "string"},
     "classes": {"type": "array", "items": {"type": "string"}}},
    ["name"])

GENERATE_NAME_TOOL = _tool("generate_name",
    "生成一个符合种族/背景的 NPC 名字。",
    {"race": {"type": "string", "description": "种族，如人类/精灵/矮人"}},
    ["race"])

ROLL_TREASURE_TOOL = _tool("roll_treasure",
    "根据挑战等级（CR）生成一组财宝掉落。",
    {"cr": {"type": "integer", "description": "怪物挑战等级"}},
    ["cr"])

NPC_QUIRK_TOOL = _tool("npc_quirk",
    "为 NPC 生成一个随机怪癖/习惯，让角色更鲜活。",
    {}, [])

SEARCH_KNOWLEDGE_TOOL = _tool("search_knowledge",
    "主动检索知识库中的规则/生物/法术/物品/城市资料。用于需要准确细节时。",
    {"query": {"type": "string", "description": "检索关键词"},
     "top_k": {"type": "integer", "description": "返回数量，默认3"}},
    ["query"])

SEARCH_BESTIARY_TOOL = _tool("search_bestiary",
    "快速查询当前剧本生物图鉴，返回匹配生物的精简摘要。用于遭遇/引入怪物前快速确认数值与设定，避免消耗过多 token。",
    {"query": {"type": "string", "description": "生物名称或关键词"},
     "top_k": {"type": "integer", "description": "返回数量，默认3，最大5"}},
    ["query"])

SEARCH_LOCATIONS_TOOL = _tool("search_locations",
    "快速查询当前剧本地点图鉴，返回匹配地点的精简摘要。用于推进剧情时确认地点设定，避免消耗过多 token。",
    {"query": {"type": "string", "description": "地点名称或关键词"},
     "top_k": {"type": "integer", "description": "返回数量，默认3，最大5"}},
    ["query"])

SEARCH_SPELLS_TOOL = _tool("search_spells",
    "快速查询当前剧本法术/仪式图鉴，返回匹配法术的精简摘要。用于施法、仪式或玩家询问法术细节时确认设定，避免消耗过多 token。",
    {"query": {"type": "string", "description": "法术/仪式名称或关键词"},
     "top_k": {"type": "integer", "description": "返回数量，默认3，最大5"}},
    ["query"])

# ── 低 token 角色资源/法术/NPC 快速工具 ──

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
    "玩家施放一个法术时调用：自动扣减对应环位法术位（邪术师扣契约法术位），返回剩余法术位。level=法术环位，0环戏法不扣。",
    {"name": {"type": "string", "description": "法术名（用于记录）"},
     "level": {"type": "integer", "minimum": 0, "maximum": 9, "description": "法术环位"},
     "pact": {"type": "boolean", "description": "邪术师使用契约法术位时填 true"}},
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

SEARCH_NPC_TOOL = _tool("search_npcs",
    "快速查询世界状态中的 NPC 数值（HP/AC/态度/位置），返回精简摘要。与NPC互动或战斗结算前确认数值时调用，避免消耗过多 token。",
    {"query": {"type": "string", "description": "NPC 名称或关键词，留空返回前几个"},
     "top_k": {"type": "integer", "description": "返回数量，默认3，最大5"}},
    [])

ADJUST_NPC_TOOL = _tool("adjust_npc",
    "以最小 token 增减世界状态中 NPC 的数值。field 只填：hp/ac/max_hp/level；delta 负数=受伤/消耗。",
    {"name": {"type": "string", "description": "NPC 名称"},
     "field": {"type": "string", "enum": ["hp", "ac", "max_hp", "level"]},
     "delta": {"type": "integer"},
     "reason": {"type": "string"}},
    ["name", "field", "delta"])

ADJUST_BESTIARY_TOOL = _tool("adjust_bestiary",
    "以最小 token 修改本局临时生物图鉴条目数值（仅本局生效）。field 可填 stats 中的任意键，如 HP/AC/攻击。",
    {"name": {"type": "string", "description": "生物名称"},
     "field": {"type": "string", "description": "数值字段名，如 HP/AC"},
     "delta": {"type": "integer"},
     "reason": {"type": "string"}},
    ["name", "field", "delta"])

PROMOTE_NPC_TOOL = _tool("promote_npc",
    "将简单NPC提升为重要NPC（完整角色卡），可同时补充性格/动机/秘密/特质/属性等。重要NPC在玩家笔记中显示完整官方卡。",
    {"name": {"type": "string", "description": "NPC 名称"},
     "personality": {"type": "string"},
     "motivation": {"type": "string"},
     "secret": {"type": "string"},
     "relation_to_plot": {"type": "string"},
     "traits": {"type": "array", "items": {"type": "string"}},
     "attributes": {"type": "object"},
     "skills": {"type": "array", "items": {"type": "string"}},
     "equipment": {"type": "array", "items": {"type": "string"}},
     "related_locations": {"type": "array", "items": {"type": "string"}},
     "related_npcs": {"type": "array", "items": {"type": "string"}},
     "related_creatures": {"type": "array", "items": {"type": "string"}},
     "appearance": {"type": "string"}},
    ["name"])

GET_BESTIARY_CARD_TOOL = _tool("get_bestiary_card",
    "返回指定生物图鉴条目的完整卡面（含六维/豁免/技能/特性/动作/栖息地/传说/弱点），用于需要完整数值时。与 search_bestiary 精简摘要互补。",
    {"name": {"type": "string", "description": "生物名称或ID"}},
    ["name"])

GET_LOCATION_CARD_TOOL = _tool("get_location_card",
    "返回指定地点/地图条目的完整卡面（含类型/状态/文化/区域/人物/危险/秘密/子地点），用于需要完整地点设定时。",
    {"name": {"type": "string", "description": "地点名称或ID"}},
    ["name"])

DM_TOOLS = [
    DICE_ROLL_TOOL, UPDATE_STATE_TOOL, COMBAT_ROUND_TOOL,
    DEATH_SAVE_TOOL, REST_TOOL, ADD_MEMORY_TOOL, SUGGEST_CHOICES_TOOL,
    UPDATE_WORLD_STATE_TOOL, REVEAL_INFO_TOOL, UPDATE_SCENE_TOOL,
    ADD_CHARACTER_NOTE_TOOL, UPDATE_BESTIARY_TOOL, UPDATE_CITY_TOOL,
    ADD_SCENARIO_BESTIARY_TOOL, ADD_SCENARIO_MAP_TOOL, ADD_SCENARIO_SPELL_TOOL,
    GENERATE_NAME_TOOL, ROLL_TREASURE_TOOL, NPC_QUIRK_TOOL, SEARCH_KNOWLEDGE_TOOL,
    SEARCH_BESTIARY_TOOL, SEARCH_LOCATIONS_TOOL, SEARCH_SPELLS_TOOL,
    GET_CHARACTER_STATE_TOOL, ADJUST_RESOURCE_TOOL, CAST_SPELL_TOOL,
    LEARN_SPELL_TOOL, FORGET_SPELL_TOOL, SEARCH_NPC_TOOL, ADJUST_NPC_TOOL,
    ADJUST_BESTIARY_TOOL, PROMOTE_NPC_TOOL, GET_BESTIARY_CARD_TOOL, GET_LOCATION_CARD_TOOL,
]
