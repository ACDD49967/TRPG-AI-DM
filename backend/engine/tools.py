"""AI地下城主工具集——10个工具，OpenAI/DeepSeek function-calling格式。"""

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
    "更新角色HP/金币/经验/物品。物品用inventory_add/inventory_remove。",
    {"changes": {"type":"object","description":"变更"},
     "reason": {"type":"string","description":"变化原因"}},
    ["changes","reason"])

COMBAT_ROUND_TOOL = _tool("combat_round",
    "【必须调用】结算一轮战斗。玩家和敌人各攻击一次。战斗场景必须用此工具。",
    {"player_action": {"type":"string"},
     "player_attack_modifier": {"type":"integer"},
     "player_damage_dice": {"type":"string","description":"如1d8"},
     "enemy_name": {"type":"string"},
     "enemy_ac": {"type":"integer"},
     "enemy_attack_modifier": {"type":"integer"},
     "enemy_damage_dice": {"type":"string"},
     "enemy_hp": {"type":"integer"}},
    ["player_action","enemy_name","enemy_ac","enemy_attack_modifier","enemy_damage_dice","enemy_hp"])

DEATH_SAVE_TOOL = _tool("death_saving_throw",
    "角色HP≤0时每回合必须掷死亡豁免。d20≥10=成功, 自然20=恢复1HP, 自然1=2次失败。累计3成功=稳定, 3失败=死亡。",
    {}, [])

REST_TOOL = _tool("take_rest",
    "短休(消耗生命骰恢复HP)或长休(完全恢复,每天1次)。",
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

DM_TOOLS = [
    DICE_ROLL_TOOL, UPDATE_STATE_TOOL, COMBAT_ROUND_TOOL,
    DEATH_SAVE_TOOL, REST_TOOL, ADD_MEMORY_TOOL, SUGGEST_CHOICES_TOOL,
    UPDATE_WORLD_STATE_TOOL, REVEAL_INFO_TOOL, UPDATE_SCENE_TOOL,
    ADD_CHARACTER_NOTE_TOOL,
]
