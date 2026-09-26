"""环境危害工具：把坠落/严寒酷暑/窒息的结算交给后端。"""
from backend.engine.tool_schemas import _tool


APPLY_HAZARD_TOOL = _tool("apply_hazard",
    "环境危害由后端结算，不要自己估伤害或豁免结果。kind=falling 传 distance_ft"
    "（每 10 尺 1d6、上限 20d6）；kind=extreme_heat/extreme_cold 传 hours（已在严寒/酷暑中"
    "坚持的小时数，体质豁免 DC=5+前序小时数，失败力竭 +1）；kind=suffocation 直接把 HP 归 0"
    "进入濒死（超过憋气/忍耐时间后的那一步）。",
    {"kind": {"type": "string",
              "enum": ["falling", "extreme_heat", "extreme_cold", "suffocation"],
              "description": "危害类型"},
     "distance_ft": {"type": "number", "description": "坠落高度（尺），默认 10"},
     "hours": {"type": "number", "description": "严寒/酷暑已坚持的小时数，默认 1"}},
    ["kind"])
