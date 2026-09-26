"""毒药工具：毒素结算（豁免 + 伤害 + 中毒状态）交给后端。"""
from backend.engine.tool_schemas import _tool


APPLY_POISON_TOOL = _tool("apply_poison",
    "【毒药/毒素】一次结算到底，不要拆成 save_damage + 手写状态两步，也不要自己判断"
    "\"这个目标抗不抗毒\"。传 target（默认玩家）、dc（体质豁免 DC）、damage（毒素伤害，"
    "如 3d6 / 8）、damage_type 固定走「毒素」管线（抗性/免疫照常生效）。"
    "默认语义按 5e 常见毒药：失败吃全额伤害并「中毒」（攻击与属性检定劣势，默认 10 轮），"
    "成功不吃伤害——若这个毒是\"成功减半\"就传 half_on_success=true。"
    "抗毒类特性（矮人坚韧等）会自动给这次豁免优势；喝了抗毒药剂之类可用 "
    "save_advantage 显式声明。毒素形态 kind=contact/ingested/injected/inhaled 只影响措辞，"
    "数值一律以图鉴卡或剧本为准（默认 DC 11 / 1d4 只是占位）。",
    {"target": {"type": "string", "description": "中毒的目标（默认玩家；也可写 NPC 名）"},
     "dc": {"type": "number", "description": "体质豁免 DC，默认 11（以卡面为准）"},
     "damage": {"type": "string", "description": "毒素伤害，如 3d6 / 8，默认 1d4"},
     "kind": {"type": "string", "enum": ["contact", "ingested", "injected", "inhaled"],
              "description": "毒素形态：接触/摄入/伤口/吸入（只影响措辞）"},
     "condition": {"type": "boolean", "description": "失败是否附加「中毒」，默认 true"},
     "condition_rounds": {"type": "integer", "description": "中毒持续轮数，默认 10"},
     "half_on_success": {"type": "boolean", "description": "成功是否减半，默认 false"},
     "save_advantage": {"type": "boolean", "description": "显式声明这次豁免有优势"},
     "save_advantage_reason": {"type": "string", "description": "优势来源，如 抗毒药剂"},
     "source": {"type": "string", "description": "毒素来源，如 巨型毒蛇咬伤"},
     "reason": {"type": "string", "description": "同 source"}},
    ["target"])
