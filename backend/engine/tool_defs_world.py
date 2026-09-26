"""世界与内容库工具：记忆、选项、世界状态、场景、笔记与图鉴/地图/法术登记。

从 `backend/engine/tools.py` 拆出；那边只留 `DM_TOOLS` 装配与再导出。
`tests/test_module_layout.py` 的注册表一致性测试会核对 schema 与处理器一一对应。
"""
from backend.engine.tool_schemas import _tool


ADD_MEMORY_TOOL = _tool("add_memory",
    "记录重要剧情事实到长期记忆。获得重要物品/杀死关键NPC/解锁区域/重大转折时调用。",
    {"memory_text": {"type":"string","description":"事实陈述"},
     "importance": {"type":"number","minimum":0.0,"maximum":1.0}},
    ["memory_text"])

FORGET_MEMORY_TOOL = _tool("forget_memory",
    "删掉一条记错的长期记忆（与 /api/memories 同一存储层）：传 memory_id，"
    "或传 content（正文片段）让后端匹配最近的一条。只在记忆与事实矛盾、玩家纠正了记录、"
    "或此前记错时使用；删的是记忆库，不动世界状态（那用 prune_world_state）。",
    {"memory_id": {"type":"string","description":"记忆 id（从 /api/memories 或 search_memory 得到）"},
     "content": {"type":"string","description":"要删的记忆正文片段（匹配用）"},
     "reason": {"type":"string","description":"为什么删"}},
    [])

RECORD_PLOT_MEMORY_TOOL = _tool("record_plot_memory",
    "记录剧情暗线/大事件/重要人物影响的长期记忆。用于幕后剧情、伏笔、NPC影响等；暗线默认对玩家隐藏。",
    {"kind": {"type":"string","enum":["major_event","hidden_thread","character_impact"],"description":"类型：大事件/暗线/人物影响"},
     "title": {"type":"string","description":"大事件标题或暗线key或人物名"},
     "description": {"type":"string","description":"事件/暗线描述"},
     "impact": {"type":"string","description":"对世界或人物的影响"},
     "status": {"type":"string","enum":["未触发","进行中","已完成","已失败"],"description":"暗线状态，默认未触发"},
     "related_npcs": {"type":"array","items":{"type":"string"}},
     "related_locations": {"type":"array","items":{"type":"string"}},
     "strength": {"type":"number","minimum":0,"maximum":100,"description":"关系亲密度 0-100（可选）"},
     "confidence": {"type":"number","minimum":0,"maximum":1,"description":"关系置信度 0-1（可选）"},
     "visible_to_players": {"type":"boolean","description":"暗线是否对玩家可见，默认 false"}},
    ["kind","title"])

SUGGEST_CHOICES_TOOL = _tool("suggest_choices",
    "玩家不知所措时给2-4个有趣的具体建议。每个选项必须是简洁纯文本（不超过25字），禁止Markdown、编号、换行、引号。",
    {"options": {"type":"array","items":{"type":"string","maxLength":25},"minItems":2,"maxItems":4}},
    ["options"])

# ── 世界状态工具 ──

UPDATE_WORLD_STATE_TOOL = _tool("update_world_state",
    "修改持久化世界状态——仅在玩家行动已被检定/判定生效后调用。可新增/更新/删除NPC、地点、旗标、值得注意的场景/物品/线索、角色笔记与关系边；世界状态必须有增有减，过期内容要主动删除，避免冒险笔记只增不减。",
    {"action": {"type":"string","enum":["update_npc","add_npc","set_flag","add_location","update_location","set_world_rule","add_notable","update_notable","remove_notable","remove_npc","remove_location","remove_flag","remove_character_note","remove_relation"]},
     "target": {"type":"string"},
     "changes": {"type":"object"},
     "reason": {"type":"string"}},
    ["action","target","changes","reason"])

PRUNE_WORLD_STATE_TOOL = _tool("prune_world_state",
    "清理世界状态中的过期内容：已完成的旧旗标、已解决的值得注意条目、长期未出场且已死亡的次要NPC、已废弃地点、悬空关系、过长日志/笔记。用于防止冒险笔记与世界上下文只增不减。",
    {"scope": {"type":"string","enum":["all","npcs","locations","flags","notes","notables","relations","logs"],
               "description":"清理范围，默认 all"},
     "older_than_turns": {"type":"integer","minimum":1,"maximum":999,
                          "description":"超过多少轮未更新视为过期，默认 20"},
     "dry_run": {"type":"boolean",
                 "description":"true 时只返回将清理多少条，不实际删除"}},
    [])

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
     "visible_npcs_here": {"type":"array","items":{"type":"string"},"description":"当前在场的NPC名列表"},
     "light": {"type":"string","description":"光照：明亮/微光/黑暗（后端据此算攻击优势与潜行；进洞、点火把、熄灯、入夜都要更新）"},
     "light_source": {"type":"string","description":"光源描述，如 火把/月光/无光"}},
    [])

ADD_CHARACTER_NOTE_TOOL = _tool("add_character_note",
    "添加角色视角笔记——以玩家角色的口吻评价NPC、事件或记录线索。每轮重要互动后调用。使用第一人称，符合角色的种族/职业/属性特点。如：野蛮人会说'这家伙看着不靠谱，但拳头够硬'；法师会说'此人的言行暗示他掌握了某种我不熟悉的奥术知识'。",
    {"target": {"type":"string","description":"目标名称(NPC名/事件/地点)"},
     "target_type": {"type":"string","enum":["npc","event","quest","location"],
                     "description":"笔记类型：npc=人物评价, event=事件记录, quest=任务线索, location=地点印象"},
     "comment": {"type":"string","description":"角色视角的简短评价(1-2句,第一人称,符合角色性格)"},
     "clue": {"type":"string","description":"相关线索或推论(如有,可选)"},
     "related_npcs": {"type":"array","items":{"type":"string"},"description":"与该目标产生关联的其他NPC名（用于更新关系图谱）"},
     "strength": {"type":"number","minimum":0,"maximum":100,"description":"关系亲密度 0-100（可选）"},
     "confidence": {"type":"number","minimum":0,"maximum":1,"description":"关系置信度 0-1（可选）"}},
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
