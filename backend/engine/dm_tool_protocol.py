"""工具调用消息配对：守住「assistant.tool_calls 后面紧跟等量 tool 响应」这条协议不变量。

OpenAI / DeepSeek 都要求 `assistant` 消息里的每个 `tool_call_id` 都有对应的 `tool` 响应，
而且这条响应要**紧挨着**那条 assistant 消息。违反时的报错只有一句
（实测报文：`insufficient tool messages following tool_calls message`），
后果却是整回合失败：玩家侧弹出 SSE 错误，这一轮白跑，还白白消耗一次完整调用。

实测踩到的两种畸形序列：
1. 提前退出（连续错误保护）导致某个 tool_call 根本没有响应；
2. 工具循环在两条 tool 响应中间插了一条 system 提示（combat_round 后的强制提示），
   网关只数紧邻的 tool 消息，于是判 3 条 tool_call 只有 1 条响应。

这里把两种都当成同一条协议不变量统一体检：调用模型前先修形，而不是在每个退出点各写一遍。
"""
from __future__ import annotations

MISSING_TOOL_RESULT = "[工具未执行] 该调用没有返回结果，请勿假设它已经生效。"


def _leading_tool_ids(messages: list, start: int) -> tuple[set, int]:
    """返回紧跟在 assistant 之后的连续 tool 响应 id 集合与扫描下标。

    只认连续段——网关就是这么校验的；中间夹一条 system 提示会截断这段响应。
    """
    answered = set()
    scan = start
    while scan < len(messages) and messages[scan].get("role") == "tool":
        answered.add(messages[scan].get("tool_call_id"))
        scan += 1
    return answered, scan


def _window(messages: list, start: int) -> tuple[list, list, int]:
    """收集紧随 assistant 的 tool / system 消息，返回 (tool 列表, 提示列表, 结束下标)。"""
    tools: list = []
    hints: list = []
    scan = start
    while scan < len(messages) and messages[scan].get("role") in ("tool", "system"):
        (tools if messages[scan].get("role") == "tool" else hints).append(messages[scan])
        scan += 1
    return tools, hints, scan


def unpaired_tool_calls(messages: list) -> list[str]:
    """只读体检：返回没有「紧邻 tool 响应」的 tool_call_id（测试与门禁用）。"""
    dangling: list[str] = []
    index = 0
    while index < len(messages):
        msg = messages[index]
        calls = msg.get("tool_calls") if msg.get("role") == "assistant" else None
        if not calls:
            index += 1
            continue
        answered, index = _leading_tool_ids(messages, index + 1)
        dangling.extend(c.get("id") for c in calls
                        if isinstance(c, dict) and c.get("id") not in answered)
    return dangling


def repair_tool_message_pairs(messages: list) -> int:
    """修形：补齐缺失响应 + 把夹在响应中间的 system 提示挪到整批响应之后。

    就地修改 messages，返回修复的问题数（补齐条数 + 挪位处数）。只补齐、不覆盖：
    已有的 tool 响应原样保留，避免改动模型已经看到的真实结果。
    """
    repaired = 0
    index = 0
    while index < len(messages):
        msg = messages[index]
        calls = msg.get("tool_calls") if msg.get("role") == "assistant" else None
        if not calls:
            index += 1
            continue
        tools, hints, scan = _window(messages, index + 1)
        answered = {m.get("tool_call_id") for m in tools}
        fillers = [{"role": "tool", "tool_call_id": c.get("id"), "content": MISSING_TOOL_RESULT}
                   for c in calls
                   if isinstance(c, dict) and c.get("id") not in answered]
        ordered = tools + fillers + hints
        if ordered != messages[index + 1:scan]:
            messages[index + 1:scan] = ordered
            repaired += len(fillers) + (1 if hints and tools else 0)
        index = index + 1 + len(ordered)
    return repaired


__all__ = ["MISSING_TOOL_RESULT", "repair_tool_message_pairs", "unpaired_tool_calls"]