"""检索工具：知识库、图鉴、NPC/法术速查、知识图谱与长期记忆。

从 `backend/engine/tools.py` 拆出；那边只留 `DM_TOOLS` 装配与再导出。
`tests/test_module_layout.py` 的注册表一致性测试会核对 schema 与处理器一一对应。
"""
from backend.engine.tool_schemas import _tool


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

SEARCH_NPC_TOOL = _tool("search_npcs",
    "快速查询世界状态中的 NPC 数值（HP/AC/态度/位置），返回精简摘要。与NPC互动或战斗结算前确认数值时调用，避免消耗过多 token。",
    {"query": {"type": "string", "description": "NPC 名称或关键词，留空返回前几个"},
     "top_k": {"type": "integer", "description": "返回数量，默认3，最大5"}},
    [])

ADJUST_NPC_TOOL = _tool("adjust_npc",
    "以最小 token 增减世界状态中 NPC 的数值或状态。field：hp/ac/max_hp/level 用 delta；"
    "condition_add/condition_remove 用 value（状态名）并可选 description/remaining_rounds；"
    "怪物施法者专注用 concentration（value=法术名）/ concentration_clear。",
    {"name": {"type": "string", "description": "NPC 名称"},
     "field": {"type": "string", "enum": ["hp", "ac", "max_hp", "level", "condition_add",
                                          "condition_remove", "concentration", "concentration_clear"]},
     "delta": {"type": "integer", "description": "数值字段的增量；状态字段可省略"},
     "value": {"type": "string", "description": "条件名，如 俯卧/束缚/中毒"},
     "description": {"type": "string", "description": "条件说明（可选）"},
     "remaining_rounds": {"type": "integer", "description": "剩余回合；0 表示永久到手动移除"},
     "damage_per_turn": {"type": "string", "description": "每回合伤害，如 1d4/1d6+1（可选）"},
     "damage_type": {"type": "string", "description": "每回合伤害类型（可选）"},
     "heal_per_turn": {"type": "integer", "description": "每回合治疗量（可选）"},
     "save_dc": {"type": "integer", "description": "回合末豁免 DC；成功自动移除该状态"},
     "save_ability": {"type": "string", "enum": ["str", "dex", "con", "int", "wis", "cha"]},
     "reason": {"type": "string"}},
    ["name", "field"])

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

GET_ENTITY_GRAPH_TOOL = _tool("get_entity_graph",
    "查询某角色/地点/生物/剧情的局部知识图谱子图，返回相关节点与关系（含亲密度/置信度）。用于确认人物关系、势力网络或剧情关联。",
    {"name": {"type": "string", "description": "实体名称（NPC/地点/生物/剧情旗标）"},
     "depth": {"type": "integer", "minimum": 1, "maximum": 2, "description": "关系深度，默认1"}},
    ["name"])

UPDATE_KNOWLEDGE_GRAPH_TOOL = _tool("update_knowledge_graph",
    "当剧情导致知识图谱应当变化时调用：由知识图谱子AGENT从文本中识别实体与关系并更新（结盟/敌对/信任/位置关联/共同卷入等），返回更新结果或错误。",
    {"text": {"type": "string", "description": "描述本次关系变化的文本（叙事片段/事件说明）"},
     "hint": {"type": "string", "description": "可选：提示应关注的关系类型或实体"}},
    ["text"])

GET_GRAPH_PATH_TOOL = _tool("get_graph_path",
    "查询知识图谱中两个实体之间的最短关系路径。用于确认人物如何认识、地点如何关联等。",
    {"source": {"type": "string", "description": "起点实体名"},
     "target": {"type": "string", "description": "终点实体名"},
     "max_depth": {"type": "integer", "minimum": 1, "maximum": 6, "description": "最大深度，默认4"}},
    ["source", "target"])

SEARCH_MEMORY_TOOL = _tool("search_memory",
    "检索 EverOS 长期记忆库（episodic/semantic/procedural/thread/reflection）。返回按相关度排序的记忆条目，用于确认跨会话事实、暗线、玩家偏好与历史抉择。",
    {"query": {"type": "string", "description": "检索关键词或自然语言问题"},
     "memory_types": {"type": "array", "items": {"type": "string",
                                                  "enum": ["episodic", "semantic", "procedural", "thread", "reflection"]},
                      "description": "可选，限定记忆类型"},
     "top_k": {"type": "integer", "minimum": 1, "maximum": 10, "description": "返回条数，默认5"}},
    ["query"])
