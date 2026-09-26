"""子 Agent 任务分配：让主 DM 从候选专业技能里挑本回合要跑的几个。

从 `backend/engine/focused_subagents.py` 拆出；失败时回退前 N 个候选，保证主流程不中断。
"""
from __future__ import annotations

import asyncio
from typing import Any

from backend.engine.prompt_guard import extract_json_object
from backend.skills import get_agent_skill


MAX_DELEGATED_TASKS = 3


async def plan_task_keys(
    client: Any,
    model: str,
    player_input: str,
    module: str,
    candidate_tasks: list[dict],
    lite: bool = False,
    timeout: float = 20,
) -> list[str]:
    """让主 DM 担任任务分配器，从候选专业子 Agent 中选择本回合要运行的技能。

    失败/解析异常时回退为全部候选任务，保证主流程不中断。
    """
    keys = [str(t.get("key", "")) for t in candidate_tasks if t.get("key")]
    if lite or len(keys) <= 1:
        return keys

    catalog: list[str] = []
    for task in candidate_tasks:
        key = str(task.get("key", ""))
        pack = get_agent_skill(str(task.get("skill") or ""))
        desc = pack.description if pack is not None else str(task.get("role") or "")
        catalog.append(f"- {key}: {desc[:140]}")

    prompt = (
        "你是 DM 主 Agent 的任务分配器。根据玩家行动，从候选专业子Agent中选择本回合需要运行的子Agent。\n"
        "候选：\n" + "\n".join(catalog) + "\n\n"
        "输出 JSON：{\"tasks\":[\"key1\",\"key2\"]}\n"
        "规则：\n"
        "- 只选真正需要的，1-" + str(len(keys)) + " 个；\n"
        "- 必须包含能完成玩家行动结算的规则/战斗子Agent；\n"
        "- 不确定时全选；\n"
        "- 只输出 JSON，不要解释。\n\n"
        f"玩家行动：{player_input}\n"
        f"当前模块：{module}"
    )
    try:
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是任务分配器，只输出合法 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=200,
                temperature=0.1,
                extra_body={"thinking": {"type": "disabled"}},
            ),
            timeout=timeout,
        )
        content = str(resp.choices[0].message.content or "")
        data = extract_json_object(content)
        selected = data.get("tasks") or data.get("keys") or []
        if isinstance(selected, str):
            selected = [selected]
        valid = {k for k in keys}
        picked: list[str] = []
        for item in selected if isinstance(selected, list) else []:
            k = str(item)
            if k in valid and k not in picked:
                picked.append(k)
        if picked:
            return picked[:MAX_DELEGATED_TASKS]
    except Exception as e:
        print(f"[DMPlanner] 任务分配失败，回退前 {MAX_DELEGATED_TASKS} 个候选: {e}")
    return keys[:MAX_DELEGATED_TASKS]
