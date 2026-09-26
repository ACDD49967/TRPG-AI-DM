"""回合收尾：建议任务、补叙事、反八股、世界维护、后台推进、记忆压缩与自动存档。

从 `backend/engine/dm_agent.py` 的主循环拆出（那里只留工具循环与错误处理）。

**为什么依赖走 hooks 而不是 import**：`tests/test_turn_execution.py` /
`tests/test_settlement_enforcement.py` 会用
`patch.object(dm_agent, "_generate_suggestions_subagent")`、
`patch.object(dm_agent, "push_event")` 这类写法替换这些函数。
如果本模块在 import 时就把它们绑定成局部名字，补丁会**静默失效**
（于是测试真的去跑 LLM 建议、真的落盘自动存档）。所以在 `dm_agent` 的调用点
解析后通过 `FinalizeHooks` 传进来，语义与拆分前完全一致。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from backend.engine.character_conditions import tick_conditions
from backend.engine.character_dying import _maybe_auto_death_save
from backend.engine.dm_runtime import sanitize_narrative
from backend.engine.session import GameSessionState


@dataclass
class FinalizeHooks:
    """收尾阶段用到的可替换依赖（在 dm_agent 调用点解析，保证测试补丁生效）。"""

    generate_suggestions: Any      # _generate_suggestions_subagent(state, player_input, full)
    advance_background: Any        # advance_background_plot_if_due(state)
    compress_memory: Any           # compress_memory_if_needed(state)
    auto_save: Any                 # auto_save_if_needed(state)
    stream_with_tools: Any         # _stream_with_tools(client, model, messages, tools, state, ...)
    push_event: Any                # push_event(state, event_type, data)


async def finish_turn(
    state: GameSessionState,
    *,
    full: str,
    messages: list,
    suggested: bool,
    delegation_used: bool,
    telemetry: Any,
    client: Any,
    model: str,
    skill: Any,
    player_input: str,
    hooks: FinalizeHooks,
) -> str:
    """回合收尾：返回补充叙事之后的最终正文。"""
    push_event = hooks.push_event

    # 建议子 Agent 与回合收尾并行：先启动任务，end_of_turn 后再取结果
    suggestions_task = None
    if not suggested and not state.aborted:
        suggestions_task = asyncio.create_task(
            hooks.generate_suggestions(state, player_input, full)
        )

    # 工具结算后补足剧情：不能让玩家只看到数值/事件摘要
    tool_result_count = sum(1 for m in messages if m.get("role") == "tool")
    if telemetry is not None:
        # 归因用：补叙事触发前，主 DM 第一遍正文到底有多长（<80 才会触发补写）
        try:
            telemetry.record_sizes(pre_polish_chars=len(full.strip()))
        except Exception:
            pass
    if (tool_result_count > 0 or delegation_used) and len(full.strip()) < 80 and not state.aborted:
        messages.append({
            "role": "system",
            "content": (
                "[系统] 工具结算已完成。请立刻根据工具结果输出2-4句对应剧情叙事："
                "描写动作、反应、环境与后果；不要复述数值，不要输出主持人独白，不要再次调用工具。"
            ),
        })
        try:
            if telemetry is not None:
                telemetry.begin_phase("narrative_polish")
            narrative_full, _ = await hooks.stream_with_tools(
                client, model, messages, [], state,
                max_tokens=700, temperature=skill.temperature,
                thinking_mode="low",
            )
            if narrative_full.strip():
                full += ("" if not full or full.endswith("\n") else "\n") + narrative_full.strip()
        except Exception:
            pass
        finally:
            if telemetry is not None:
                telemetry.end_phase("narrative_polish")

    # 反八股过滤
    full = sanitize_narrative(full)

    # 回合收尾（濒死补掷 / 状态递减 / 世界维护 / 后台推进 / 建议与记忆落盘）单独计时：
    # 这段里也可能发生模型调用，之前没有归属阶段，会被记成无名的 "llm"。
    if telemetry is not None:
        telemetry.begin_phase("post_turn")
    # 濒死安全网：DM 漏掷死亡豁免时回合末补掷，保证濒死时钟一定推进
    if not state.aborted:
        try:
            death_text = await _maybe_auto_death_save(state)
            if death_text:
                full += ("\n\n" if full.strip() else "") + death_text
                print("[Dying] DM 未掷死亡豁免，已自动补掷一次")
        except Exception as e:
            print(f"[Dying] 自动死亡豁免失败（已忽略）: {e}")

    # P0-2: end_of_turn时自动同步journal——不再依赖AI主动调用update_scene
    ws = getattr(state, 'world_state', None)
    if ws:
        ws.advance_turn()
        # 状态效果按回合递减/过期
        try:
            await tick_conditions(state)
        except Exception as e:
            print(f"[Conditions] 状态效果结算失败（已忽略）: {e}")
        # 世界状态维护：每轮裁剪日志，每 10 轮清理过期实体；避免世界状态只增不减
        try:
            if ws.turn_count % 10 == 0:
                summary = ws.maintenance(scope="all", older_than_turns=20)
                if summary.get("removed_total"):
                    await push_event(state, "journal_update", ws.to_player_journal())
            else:
                ws.maintenance(scope="logs", older_than_turns=20)
        except Exception as e:
            print(f"[WorldState] 自动维护失败（已忽略）: {e}")
        # 低成本后台剧情推进：仅在整轮结束时按频率触发，不阻塞主叙事
        await hooks.advance_background(state)
        ws.save()
        await push_event(state, "journal_update", ws.to_player_journal())
        # 每 10 轮整理一次长期记忆：合并重复、衰减低价值、重建 index.md
        if ws.turn_count % 10 == 0 and not state.aborted:
            try:
                from backend.long_term_memory import consolidate_memories
                await asyncio.to_thread(consolidate_memories, state.username)
            except Exception as e:
                print(f"[Memory] 长期记忆整理失败: {e}")

    await push_event(state, "end_of_turn", {})
    if suggestions_task is not None:
        # 建议不影响本轮叙事与结算：已完成就立即推；没完成交给后台继续，
        # 避免每个回合末尾都为这几个选项固定多等约 1 秒（实测 post_turn 1.1s）。
        async def _push_choices_when_ready(task: Any) -> None:
            try:
                options = await task
                if options:
                    await push_event(state, "choices", {"options": options})
                    print(f"[DMSubAgent] 生成建议 {len(options)} 个")
            except Exception as e:
                print(f"[DMSubAgent] 建议生成失败: {e}")

        if suggestions_task.done():
            await _push_choices_when_ready(suggestions_task)
        else:
            asyncio.create_task(_push_choices_when_ready(suggestions_task))
    state.memory.add_turn(player_input=player_input, dm_response=full)
    await hooks.compress_memory(state)
    # 默认每轮自动存档
    hooks.auto_save(state)
    if telemetry is not None:
        telemetry.end_phase("post_turn")
        telemetry.end_turn()
        # end_of_turn 时本轮还没结算，前端那一刻拉 /metrics 会缺当前轮
        # （新会话甚至是空的）。回合真正结算后补推一次，前端据此刷新统计。
        await push_event(state, "metrics_update", {})
    return full


__all__ = ["FinalizeHooks", "finish_turn"]
