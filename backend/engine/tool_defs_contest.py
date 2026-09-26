"""对抗动作工具：擒抱 / 推撞 / 逃脱的对抗检定与状态落地。"""
from backend.engine.tool_schemas import _tool


RESOLVE_CONTEST_TOOL = _tool("resolve_contest",
    "【对抗动作】擒抱/推撞/逃脱由后端掷对抗检定并落地状态：玩家说\"我抓住/抱住/摔倒/推倒它\""
    "时要先调这个工具，叙事写成\"试图抓住/想把它按倒\"，不要先写\"已经抓住了\"再补判，"
    "也不要手掷两个 d20 自己查加值。action=grapple：力量（运动）对抗目标的"
    "力量（运动）或敏捷（杂技）——目标可选更优项（不传 defense 时后端取更高的那项），"
    "成功后目标获得「擒抱」（速度归 0）。action=shove：同一对抗，"
    "mode=prone 放倒（目标「俯卧」）/ mode=push 推开 5 尺（位移自己用 set_tactical_state 更新）。"
    "action=escape：自己被擒抱时用动作挣脱，target 写擒抱者的名字。"
    "目标比发起方大出两级以上时无效；目标无法行动（失能/麻痹/昏迷/石化）时自动成功并落地状态。"
    "attacker 默认玩家；NPC 对玩家动手时把 attacker 写成 NPC 的名字（这样不消耗玩家的主行动）。",
    {"action": {"type": "string", "enum": ["grapple", "shove", "escape"],
                "description": "grapple=擒抱，shove=推撞，escape=挣脱"},
     "attacker": {"type": "string", "description": "发起方名字（默认玩家）"},
     "target": {"type": "string", "description": "对抗的目标名字"},
     "mode": {"type": "string", "enum": ["prone", "push"],
              "description": "推撞方式：prone=放倒，push=推开 5 尺"},
     "defense": {"type": "string", "enum": ["str", "dex"],
                 "description": "防御方选择的对抗项（留空取更优的那项）"},
     "advantage": {"type": "string", "enum": ["normal", "advantage", "disadvantage"],
                   "description": "未结构化来源的优势/劣势（如居高临下）"},
     "advantage_reason": {"type": "string", "description": "优势/劣势来源说明"},
     "reason": {"type": "string", "description": "这次对抗的原因"}},
    ["action", "target"])
