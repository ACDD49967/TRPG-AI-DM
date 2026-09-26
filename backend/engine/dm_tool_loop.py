"""主 DM 的工具调用循环：流式生成 → 工具执行 → 强制结算守卫 → 场景校验。

从 `backend/engine/dm_agent.py` 拆出（那边只留回合编排与门面）。

**补丁契约**：`_stream_with_tools` / `execute_tool` / `push_event` 都被测试用
`patch.object(dm_agent, ...)` 打桩，所以它们经 `ToolLoopHooks` 在 dm_agent 的调用点解析，
循环里只做局部别名——这样循环体本身可以和拆分前**逐字一致**。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from backend.engine.dm_runtime import _play_mode, _safe_error_text, dm_think_mode
from backend.engine.dm_tool_protocol import repair_tool_message_pairs
from backend.engine.dm_turn import _SETTLEMENT_TOOLS


@dataclass
class ToolLoopHooks:
    """循环里被测试打桩的三个依赖（在 dm_agent 调用点解析）。"""

    stream_with_tools: Any
    execute_tool: Any
    push_event: Any


async def run_tool_loop(
    state: Any,
    *,
    client: Any,
    model: str,
    messages: list,
    module_tools: list,
    skill: Any,
    module: str,
    lite: bool,
    settlement_group: Any,
    settled_tools: set,
    settlement_tools: set,
    delegated_tools_executed: bool,
    delegation_used: bool,
    telemetry: Any,
    hooks: ToolLoopHooks,
) -> tuple[str, bool]:
    """跑完本回合的工具循环，返回 (正文, 是否已给过行动建议)。messages 就地追加。"""
    _stream_with_tools = hooks.stream_with_tools
    execute_tool = hooks.execute_tool
    push_event = hooks.push_event
    full = ""
    suggested = False
    error_streak = 0
    combat_guard_count = 0
    empty_stream_retry = 0
    # 本回合主 DM 实际执行过的工具名：只检查"有没有调用过工具"不够，
    # 模型可能查了一下 search_npcs 就把战斗叙述掉了。
    executed_tool_names: set[str] = set()
    while True:
        if state.aborted:
            await push_event(state, "error", {"code":"ABORTED","msg":"已中断"}); break
        module_max_tokens = {
            "rules": 2600, "combat": 2200, "scene": 2000,
            "social": 2200, "memory": 2000, "graph": 1800, "narrative": skill.max_tokens,
        }
        max_tokens = 1024 if _play_mode(state) == "lite" else min(skill.max_tokens, module_max_tokens.get(module, skill.max_tokens))
        think_mode = dm_think_mode(state, module)
        if telemetry is not None:
            telemetry.begin_phase("dm_generation")
            try:
                telemetry.record_sizes(
                    messages_chars=sum(len(str(m.get("content") or "")) for m in messages))
            except Exception:
                pass
        try:
            text, tcs = await _stream_with_tools(client, model, messages, module_tools, state, max_tokens, temperature=skill.temperature, thinking_mode=think_mode)
        finally:
            if telemetry is not None:
                telemetry.end_phase("dm_generation")
        # 模型只输出 reasoning、没有正文与工具调用时，追加一次“只输出正文”重试
        if (not text.strip() and not tcs and not state.aborted
                and empty_stream_retry < 1):
            empty_stream_retry += 1
            messages.append({"role": "system", "content":
                "[系统] 你刚才只返回了内部推理，没有给玩家正文。"
                "请直接输出角色扮演叙事（2-4 句，禁止输出推理过程），不要调用工具。"})
            continue
        full += text
        if any(t.get("function", {}).get("name") == "suggest_choices" for t in tcs):
            suggested = True
        if not tcs:
            # 战斗/“我先确认…”式计划独白没有调用任何工具时强制重试，避免卡住不结算
            had_tool_result = delegated_tools_executed or any(m.get("role") == "tool" for m in messages)
            plan_like = bool(re.search(r"我先|让我先|让我看看|我打算|我需要确认|我来确认|先调出|调出战力|我来结算", text))
            # 战斗进行中，或玩家声明了施法/休息（必然改变数值）时必须结算；
            # 场景里没有敌人的"攻击空气"不强制，避免多花两轮重试。
            needs_settlement = bool(settlement_group) and (
                state.in_combat or settlement_group in ("cast", "rest")
            )
            # 关键校验：玩家声明了动作时，必须真的调用对应的结算工具，
            # 而不是"随便调过某个工具"就算数。
            required_tools = _SETTLEMENT_TOOLS.get(settlement_group, set())
            had_required_settlement = bool(
                (executed_tool_names | settled_tools) & required_tools
            )
            needs_forced_settlement = (
                (required_tools and not had_required_settlement)
                or (not required_tools and not had_tool_result)
            )
            if (not state.aborted and not delegation_used and needs_forced_settlement
                    and (module == "combat" or plan_like or needs_settlement)
                    and combat_guard_count < 2):
                combat_guard_count += 1
                tool_list = " / ".join(sorted(settlement_tools)) or (
                    "dice_roll / search_npcs / search_bestiary / combat_round / enemy_attack / update_world_state")
                messages.append({"role":"system","content":
                    "[系统强制] 你刚才没有调用任何工具，输出不能算作本回合结算。"
                    f"请立即调用对应工具（{tool_list}）完成行动；"
                    "不要再输出“我先确认”“让我看看”等计划。若玩家只是侦查/观察，调用搜索或检定工具后给出结果。"})
                continue
            break
        asst = {"role":"assistant","content":text or None}
        atc = [{"id":t["id"],"type":"function","function":t["function"]} for t in tcs]
        if atc: asst["tool_calls"] = atc
        messages.append(asst)
        too_many_errors = False
        # 本轮工具调用的补充提示：必须排在整批 tool 响应之后。
        # DeepSeek 只数紧邻 assistant 的连续 tool 消息，中间夹一条 system 就会判成
        # "insufficient tool messages following tool_calls message"（实测 400，整回合失败）。
        post_hints: list[str] = []
        for t in tcs:
            tool_name = t.get("function", {}).get("name", "")
            try:
                args = json.loads(t["function"]["arguments"])
            except json.JSONDecodeError as e:
                # ReAct：把参数错误回传给 DM，让它修正后重试，而不是直接中断
                error_streak += 1
                messages.append({
                    "role": "tool",
                    "tool_call_id": t.get("id", ""),
                    "content": f"[工具参数错误] {tool_name} 参数不是合法JSON: {_safe_error_text(e)}。请修正参数后重新调用。",
                })
                if error_streak >= 3:
                    too_many_errors = True
                    break
                continue
            try:
                result = await execute_tool(tool_name, args, state)
                error_streak = 0
                executed_tool_names.add(tool_name)
            except Exception as e:
                # ReAct：工具执行失败也回传给 DM，让其接受报错并修改方案
                error_streak += 1
                messages.append({
                    "role": "tool",
                    "tool_call_id": t.get("id", ""),
                    "content": f"[工具执行失败] {tool_name} 返回错误: {_safe_error_text(e)}。请根据错误调整参数或改用其他工具。",
                })
                if error_streak >= 3:
                    too_many_errors = True
                    break
                continue
            messages.append({"role":"tool","tool_call_id":t["id"],"content":result})
            if tool_name == "combat_round":
                post_hints.append(
                    "[系统] 玩家行动已结算。所有存活且可行动的敌对单位都必须在敌人回合行动："
                    "逐个调用 enemy_attack，不要写成敌人只挨打不还手。"
                    "默认每个敌人本回合只行动一次（目标敌人通常已由 combat_round 自动反击）；"
                    "若敌人拥有传奇动作/巢穴动作/加速术/时间暂停等额外行动能力，"
                    "用 action_source 声明来源（如 legendary_action、haste、time_stop）后再次调用。")
        for hint in post_hints:
            messages.append({"role":"system","content":hint})
        if too_many_errors:
            # 提前退出前必须补齐这批 tool 响应，否则残留的 assistant.tool_calls
            # 会让后续每一次调用 400（"insufficient tool messages"）。
            repair_tool_message_pairs(messages)
            print("[DM] 工具连续错误超过3次，停止本轮工具重试")
            break

        # P0-1: 每次工具调用后强制场景校验——防止场景漂移
        ws = getattr(state, 'world_state', None)
        if ws and ws.scene.current_location != "未知":
            scene_check = (
                f"[系统校验——每轮工具调用后强制执行] "
                f"当前位置: {ws.scene.current_location} | "
                f"时间: {ws.scene.current_time or f'第{ws.scene.day_count}天'} | "
                f"天气: {ws.scene.weather} | "
                f"在场NPC: {', '.join(ws.scene.visible_npcs_here) if ws.scene.visible_npcs_here else '无'}"
                f"\n如果你接下来的叙事会改变以上任何一项，必须先调用update_scene。"
            )
            messages.append({"role":"system","content": scene_check})

        # P0-2修复：工具调用结束后确保text末尾有换行，防止下一轮文本拼接
        if text and not text.endswith('\n'):
            text += '\n'

        # 工具调用数过载保护——精简模式限制更严格
        tool_limit = 3 if lite else 5
        tool_count = sum(1 for m in messages if m["role"] == "tool")
        if tool_count >= tool_limit:
            break
    return full, suggested


__all__ = ["ToolLoopHooks", "run_tool_loop"]
