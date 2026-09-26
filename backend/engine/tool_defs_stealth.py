"""潜行/隐藏工具：隐匿对抗观察者的被动察觉交给后端。"""
from backend.engine.tool_schemas import _tool


RESOLVE_STEALTH_TOOL = _tool("resolve_stealth",
    "【潜行/隐藏】藏起来与现身由后端判定，不要自己比 DC。action=hide：默认拿当前地点"
    "活着生物的被动察觉最高值当 DC（可用 observers 指定观察者名单），也可用 dc 直接覆盖"
    "（例如对方在打瞌睡）。隐匿 = d20+敏捷（潜行/隐匿熟练另加），身着劣势护甲自动劣势，"
    "由法术/环境带来的优势劣势用 advantage/advantage_reason 声明。成功后登记「隐藏」状态："
    "你的攻击有优势、别人打你有劣势，而**你一攻击或施法就会自动暴露**（不用再手动清）。"
    "action=reveal 表示主动现身，不掷骰。",
    {"action": {"type": "string", "enum": ["hide", "reveal"],
                "description": "hide=藏起来，reveal=主动现身"},
     "target": {"type": "string", "description": "谁在藏（默认玩家；也可写 NPC 名）"},
     "observers": {"type": "array", "items": {"type": "string"},
                   "description": "观察者名单（默认当前地点的 NPC）"},
     "dc": {"type": "number", "description": "直接指定 DC，覆盖被动察觉比对"},
     "advantage": {"type": "string", "enum": ["normal", "advantage", "disadvantage"],
                   "description": "法术/环境等未结构化来源"},
     "advantage_reason": {"type": "string", "description": "优势/劣势来源说明"},
     "reason": {"type": "string", "description": "这次潜行的原因"}},
    ["action"])
