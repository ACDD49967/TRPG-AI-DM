"""追逐工具：冲刺配额、体质豁免与"跑出视线"交给后端。"""
from backend.engine.tool_schemas import _tool


RESOLVE_CHASE_TOOL = _tool("resolve_chase",
    "【追逐】长距离追逃由后端记账，不要自己数「还能冲几次」，也不要直接宣布跑掉了。"
    "action=dash（默认）：某单位冲刺一次；免费次数 = 3 + 体质调整值，超出后每次都要掷"
    "体质豁免 DC 10（可用 dc 覆盖），失败力竭 +1（力竭后果后端自动生效）。"
    "action=escape：被追的人尝试跑出视线——隐匿对抗追兵的被动察觉，成功即结束追逐并清零计数"
    "（追兵用 pursuers 指定，留空则取当前在场 NPC）。"
    "action=end：追逐结束/放弃追击，清空冲刺计数。actor 默认玩家；追兵是 NPC 时要写 NPC 名。",
    {"action": {"type": "string", "enum": ["dash", "escape", "end"],
                "description": "dash=冲刺，escape=甩掉追兵，end=结束追逐"},
     "actor": {"type": "string", "description": "谁在跑（默认玩家；NPC 写 NPC 名）"},
     "pursuers": {"type": "array", "items": {"type": "string"},
                  "description": "追兵名单（escape 用；留空取当前在场 NPC）"},
     "dc": {"type": "number", "description": "超出免费额度后的体质豁免 DC，默认 10"},
     "reason": {"type": "string", "description": "这次追逃的原因"}},
    ["action"])
