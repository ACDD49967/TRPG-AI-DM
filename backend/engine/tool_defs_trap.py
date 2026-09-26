"""陷阱工具：发现/解除的判定与"失败多少算踩响"交给后端。"""
from backend.engine.tool_schemas import _tool


RESOLVE_TRAP_TOOL = _tool("resolve_trap",
    "【陷阱】发现与解除由后端结算，不要自己比 DC，也不要自己判断失败多少算触发。"
    "stage=detect 传 detect_dc：不传 searching 时用被动察觉直接比 DC（不掷骰）；"
    "searching=true 时掷 d20+察觉（注意到可疑痕迹再主动搜查时用）。"
    "stage=disarm 传 disarm_dc：检定失败 5 点以内只是没拆开、可以再试；"
    "失败 5 点以上或掷出自然 1 立刻触发陷阱。要结算触发伤害时同时给 damage"
    "（伤害骰或固定值，如 2d6 / 10）、damage_type、ability（默认 dex）、dc（默认同解除 DC），"
    "后端会走既有豁免管线（成功减半、抗性/免疫/临时生命值照常）。",
    {"name": {"type": "string", "description": "陷阱名称，用于日志"},
     "stage": {"type": "string", "enum": ["detect", "disarm"],
               "description": "detect=发现，disarm=解除"},
     "detect_dc": {"type": "number", "description": "发现 DC，默认 12"},
     "disarm_dc": {"type": "number", "description": "解除 DC，默认 12"},
     "searching": {"type": "boolean",
                   "description": "是否主动搜索（true 才掷察觉检定）"},
     "damage": {"type": "string", "description": "触发时的伤害骰或固定值，如 2d6 / 10"},
     "damage_type": {"type": "string", "description": "伤害类型，如 穿刺/火焰"},
     "ability": {"type": "string", "enum": ["str", "dex", "con", "int", "wis", "cha"],
                 "description": "触发时的豁免属性，默认 dex"},
     "dc": {"type": "number", "description": "触发时的豁免 DC，默认同解除 DC"},
     "target": {"type": "string", "description": "触发时受影响的目标，默认玩家"}},
    ["name", "stage"])
