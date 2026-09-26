# -*- coding: utf-8 -*-
"""DM 主 Agent 的“专业子 Agent 委派”层。

设计目标：
- 主 DM 只负责角色扮演、故事生成与世界操控；
- 规则裁决、场景事实、记忆连续性、关系图谱、战斗战术等专业判断，
  交给多个专业子 Agent **并发**完成；
- 子 Agent 返回“结论/事实/工具建议”，主 DM 把它们当作参谋简报采纳，
  不再把完整规则表、完整世界状态全部塞进主提示词。

本文件只保留"运行层"（调用模型、工具循环、并发与任务分配）；
简报装配在 `dm_brief.py`，公共类型在 `subagent_types.py`，都从这里再导出。
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from backend.engine.prompt_guard import extract_json_object, sanitize_user_text
from backend.engine.tools import DM_TOOLS
from backend.skills import get_agent_skill


# 公共类型与简报层各有归属模块；再导出保证既有 import 与 patch 目标不变
from backend.engine.subagent_types import (  # noqa: E402,F401
    ToolAgentResult,
    _WRITE_TOOL_NAMES,
    is_agent_result_complete,
)
from backend.engine.dm_brief import (  # noqa: E402,F401
    _SECTION_TITLES,
    _apply_skill_packs,
    _recent_text,
    _retrieved_text,
    _SKILL_FOR_TASK_KEY,
    build_dm_brief_tasks,
    delegation_execution_context,
    delegation_is_complete,
    format_dm_brief,
    get_skill_instruction,
)


# ── 基础调用 ────────────────────────────────────────────────


def _allowed_tool_schemas(pack: Any) -> list[dict]:
    """按 SKILL.md 的 allowed-tools 元数据过滤该子 Agent 可用的工具。"""
    allowed = pack.metadata.get("allowed-tools") or []
    if isinstance(allowed, str):
        allowed = [x.strip() for x in allowed.split(",") if x.strip()]
    allowed_set = {str(x).strip() for x in allowed if str(x).strip()}
    if not allowed_set:
        return []
    known = {str(t.get("function", {}).get("name", "")) for t in DM_TOOLS}
    unknown = sorted(allowed_set - known)
    if unknown:
        print(f"[Skills] {getattr(pack, 'id', '')} allowed-tools 含未知名（已忽略）: {unknown}")
    return [
        t for t in DM_TOOLS
        if str(t.get("function", {}).get("name", "")) in allowed_set
    ]


async def run_tool_subagent(
    client: Any,
    model: str,
    task: dict,
    state: Any,
    # 实测子 Agent 多数在 1 次工具调用 + 1 次总结内完成；上限收到 3 以限制最坏情况
    max_iterations: int = 3,
    timeout: float = 60,
) -> ToolAgentResult:
    """运行专业任务；超时、空正文及预算耗尽均保留已执行记录供主 DM 接手。"""
    outcome = ToolAgentResult()
    skill_name = str(task.get("skill") or "")
    pack = get_agent_skill(skill_name) if skill_name else None
    if pack is None:
        outcome.error = "专业技能包不存在，交由主 DM 完成"
        return outcome

    tools = _allowed_tool_schemas(pack)
    tool_names = {str(t.get("function", {}).get("name", "")) for t in tools}
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": (
            f"你是专业子Agent：{pack.name}。\n技能说明：{pack.description}\n\n{pack.content}\n\n"
            "按工具权限完成任务。最终只返回给主 DM 的事实、已执行工具、数值和结果；"
            "不要输出玩家叙事。尚未完成的动作必须明确标注，不得声称已结算。"
        )},
        {"role": "user", "content": (
            f"任务：{task.get('task') or ''}\n本轮上下文：\n"
            f"{sanitize_user_text(str(task.get('context') or ''))[:9000]}"
        )},
    ]
    tool_failed = False
    # 工具跑完后的"总结轮"不再重放技能包全文（第一轮 prompt_tokens 3041-4879，
    # 总结轮重放到 3370-5247 且输出 363-466 token，单次 2.4-2.9 秒，是第一次的约 2 倍）。
    # 总结轮只保留任务与工具真实结果，并限长，实测可显著压低这一跳的输入/输出量。
    followup_system = (
        f"你是专业子Agent：{pack.name}。工具已执行完毕，下面是真实结果。\n"
        "只给主 DM 输出结论：关键数值、已执行动作、未完成事项；不复述工具原文、不写玩家叙事。\n"
        "最多 120 字，直接给结论。"
    )

    async def run() -> ToolAgentResult:
        nonlocal tool_failed
        from backend.engine.dm_agent import execute_tool

        for iteration in range(max_iterations):
            if getattr(state, "aborted", False):
                outcome.error = "玩家已中断"
                return outcome
            call_messages = messages
            max_tokens = 900
            if iteration > 0:
                call_messages = [{"role": "system", "content": followup_system}, *messages[1:]]
                max_tokens = 400
            kwargs: dict[str, Any] = dict(
                model=model, messages=call_messages, max_tokens=max_tokens, temperature=0.1,
                extra_body={"thinking": {"type": "disabled"}},
            )
            if tools:
                kwargs.update(tools=tools, tool_choice="auto")
            resp = await client.chat.completions.create(**kwargs)
            choice = resp.choices[0]
            msg = choice.message
            tool_calls = list(getattr(msg, "tool_calls", None) or [])
            if not tool_calls:
                outcome.content = str(msg.content or "").strip()
                if (is_agent_result_complete(outcome.content) and not tool_failed
                        and getattr(choice, "finish_reason", "stop") == "stop"):
                    outcome.status = "completed"
                else:
                    outcome.error = "未得到完整结论或工具存在失败，需主 DM 核对"
                return outcome

            # 所有 tool call 均应有对应响应，超限调用只回报错误，不执行。
            messages.append({
                "role": "assistant", "content": msg.content or None,
                "tool_calls": [{"id": tc.id, "type": "function", "function": {
                    "name": tc.function.name, "arguments": tc.function.arguments or "{}",
                }} for tc in tool_calls],
            })
            executed_round: list[str] = []
            for index, tc in enumerate(tool_calls):
                name = tc.function.name
                args = {}
                try:
                    if index >= 4:
                        raise ValueError("本次工具调用数量超过上限")
                    if name not in tool_names:
                        raise ValueError("工具不在本 Agent 的权限范围内")
                    args = json.loads(tc.function.arguments or "{}")
                    if not isinstance(args, dict):
                        raise ValueError("工具参数必须是 JSON 对象")
                    # 在执行前记录：取消可能发生在工具已修改状态但尚未返回的时候。
                    entry = len(outcome.observations)
                    outcome.observations.append(f"{name} {json.dumps(args, ensure_ascii=False)}: 执行中，结果待核对")
                    result = str(await execute_tool(name, args, state))
                    outcome.observations[entry] = f"{name} {json.dumps(args, ensure_ascii=False)}: {result}"
                    if result.startswith(("❌", "⚠", "[工具")):
                        tool_failed = True
                    else:
                        outcome.successful_tools.append(name)
                        executed_round.append(name)
                except Exception as exc:
                    tool_failed = True
                    result = f"[工具执行失败] {type(exc).__name__}: {exc}"
                    outcome.observations.append(f"{name}: {result}")
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

            # fast-settle：结算型工具已经改完状态，再让子 Agent 用一次 LLM 往返复述这些数值
            # 属于纯开销——主 DM 拿到的 execution_context 本来就是同一批真实结果。
            # 只在任务显式声明 fast_settle、且本轮调用全是写型工具、且无一失败时生效：
            # 只查询（search_*/get_*）或只掷骰（dice_roll 不在写型集合）仍走原来的多轮。
            if (task.get("fast_settle") and not tool_failed and executed_round
                    and all(tool in _WRITE_TOOL_NAMES for tool in executed_round)):
                outcome.content = ("已结算，以下为工具权威结果：\n"
                                   + "\n".join(outcome.observations[-4:]))[:900]
                outcome.status = "completed"
                return outcome
        outcome.error = "已达到工具迭代上限，尚未返回最终结论"
        return outcome

    try:
        # 不再串行整段 Agent：各任务的上下文都是派发前的同一份快照，
        # 外层写锁无法阻止基于旧快照的决策，却会让 LLM 往返时间逐个叠加
        # （实测 3 个任务墙钟 = 各自耗时之和 21s）。状态写入由 execute_tool
        # 内部的 tool_lock 逐次串行，保证单次工具调用原子。
        return await asyncio.wait_for(run(), timeout=timeout)
    except asyncio.TimeoutError:
        outcome.status = "timeout"
        outcome.error = "任务超时，已执行记录需要核对"
    except Exception as exc:
        outcome.status = "failed"
        outcome.error = f"{type(exc).__name__}: {exc}"
    return outcome


async def run_tool_subagents(
    client: Any,
    model: str,
    tasks: list[dict],
    state: Any,
    max_concurrency: int = 4,
    timeout: float = 60,
) -> dict[str, ToolAgentResult]:
    """运行委派任务；超出预算的任务显式保留为未完成，不能静默丢失。"""
    tasks = list(tasks or [])
    sem = asyncio.Semaphore(max(1, int(max_concurrency)))

    async def one(task: dict) -> tuple[str, ToolAgentResult]:
        key = str(task.get("key", ""))
        # 技能包允许为单个任务设置更紧的预算；缺少时才使用调用方的兜底值。
        task_timeout = float(task.get("timeout") or timeout)
        async with sem:
            try:
                result = await run_tool_subagent(client, model, task, state, timeout=task_timeout)
            except Exception as exc:
                result = ToolAgentResult(status="failed", error=f"{type(exc).__name__}: {exc}")
        return key, result

    out = {str(t.get("key", "")): ToolAgentResult(error="超出委派数量预算，交由主 DM 完成")
           for t in tasks[MAX_DELEGATED_TASKS:]}
    out.update(await asyncio.gather(*(one(t) for t in tasks[:MAX_DELEGATED_TASKS])))
    return out

# 并发委派预算。实测（deepseek-chat，同一战斗回合）：
# - 3 个并发子 Agent：墙钟 ≈ 4.8-5.1 秒，7 次调用 / 27.6k token；
# - 放宽到 4 个（战斗模块的 rules/combat/world/memory 全跑）：墙钟反而涨到 6.9 秒，
#   12 次调用 / 43.8k token —— 四路并发流互相拖慢，且被省下的那个 Agent 本来就与
#   其它 Agent 并发，"挑选"省的是 token 而不是墙钟。
# 结论：保持 3。候选 ≤ 3 时连分配器都不必调用（见 dm_turn），
# 只有候选真的超过预算、必须取舍时才花那一次 1.04 秒的分配调用。


# 拆出的 runner / 规划 / 摘要在这里再导出，既有 import（dm_turn、dm_subagents、测试）不变
from backend.engine.subagent_runners import (  # noqa: E402,F401
    _compact_prompt, run_focused_agent, run_parallel_subagents,
)
from backend.engine.subagent_planning import (  # noqa: E402,F401
    MAX_DELEGATED_TASKS, plan_task_keys,
)
from backend.engine.subagent_summaries import (  # noqa: E402,F401
    summarize_rules_for_player, summarize_world_for_player,
)
