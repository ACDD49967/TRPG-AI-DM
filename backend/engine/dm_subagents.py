"""子 Agent 调度：聚焦子 Agent 与行动建议生成。

从 backend.engine.dm_agent 拆出。
"""
from __future__ import annotations

import re
from typing import Any

from backend.engine.dm_runtime import _client, _model
from backend.engine.dm_prompts import build_character_info
from backend.engine.focused_subagents import get_skill_instruction, run_focused_agent
from backend.engine.session import GameSessionState





async def _run_focused_subagent(
    task: str,
    context: str,
    state: GameSessionState,
    max_tokens: int = 600,
    temperature: float = 0.2,
) -> str:
    """调用一个专注子 Agent，对长上下文做精简后返回结论。

    失败时返回空字符串，调用方回退到现有完整上下文，不阻塞主流程。
    """
    try:
        from backend.engine.focused_subagents import run_focused_agent
        result = await run_focused_agent(
            _client(state),
            _model(state),
            role="DM聚焦分析子Agent",
            task=task,
            context=context,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if result and not result.startswith("[子Agent失败]"):
            return result
    except Exception as e:
        print(f"[DMSubAgent] 失败: {e}")
    return ""





async def _generate_suggestions_subagent(
    state: GameSessionState,
    player_input: str,
    context_text: str = "",
) -> list[str]:
    """从 DM Agent 剥离建议生成：由独立子 Agent 强制产出 2-4 个行动建议。"""
    ws = getattr(state, "world_state", None)
    scene = ""
    if ws is not None and getattr(ws, "scene", None):
        scene = (f"当前位置: {ws.scene.current_location} | "
                 f"时间: {ws.scene.current_time or f'第{ws.scene.day_count}天'} | "
                 f"在场NPC: {', '.join(ws.scene.visible_npcs_here)}")
    context = (f"玩家行动：{player_input}\n"
               f"最近剧情：{(context_text or '')[-1500:]}\n"
               f"当前场景：{scene}\n"
               f"角色背景：{build_character_info(state)[:500]}")
    fallback_task = (
        "你是行动建议生成器。根据当前局面严格输出2-4个玩家可执行的行动选项，每个不超过25字。"
        "格式：每行一个选项，以“- ”开头。只输出选项本身，禁止任何解释、分析、自我对话，"
        "禁止出现“目标”“玩家行动”“应该怎么做”“别过度思考”等元描述。"
    )
    task = get_skill_instruction("suggestions", fallback_task)
    result = await _run_focused_subagent(task, context, state, max_tokens=250, temperature=0.2)
    meta_re = re.compile(r"目标|玩家行动|应该怎么做|建议如下|别过度|思考|选项|元描述|请根据|严格输出|掷骰|检定|先攻|骰子|系统")
    options: list[str] = []
    for line in (result or "").splitlines():
        line = line.strip()
        if line.startswith(("-", "*", "•")):
            opt = line.lstrip("-*•").strip().strip("\"'“”")
            opt = opt[:25]
            if opt and len(opt) >= 2 and not meta_re.search(opt):
                options.append(opt)
    if len(options) < 2:
        # 兼容纯文本输出，并丢弃元描述
        for part in re.split(r"[\n;；]+", result or ""):
            part = part.strip().strip("\"'“”")
            if part and len(part) <= 25 and not meta_re.search(part) and part not in options:
                options.append(part)
    if len(options) < 2:
        # 最后兜底：给不出好选项时提供安全、可执行的基础行动
        options = ["先观察再行动，寻找可利用的细节", "谨慎试探对方的反应", "继续推进当前目标，准备应对变化"]
    return options[:4]
