# -*- coding: utf-8 -*-
"""DM 主 Agent 的“专业子 Agent 委派”层。

设计目标：
- 主 DM 只负责角色扮演、故事生成与世界操控；
- 规则裁决、场景事实、记忆连续性、关系图谱、战斗战术等专业判断，
  交给多个专业子 Agent **并发**完成；
- 子 Agent 返回“结论/事实/工具建议”，主 DM 把它们当作参谋简报采纳，
  不再把完整规则表、完整世界状态全部塞进主提示词。
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from backend.engine.prompt_guard import extract_json_object, sanitize_user_text
from backend.engine.tools import DM_TOOLS
from backend.skills import get_agent_skill


# ── 基础调用 ────────────────────────────────────────────────

def _compact_prompt(role: str, task: str, context: str, output_hint: str = "只输出结论，不要解释过程。") -> str:
    return (
        f"你是子Agent，角色：{role}。\n"
        f"任务：{task}\n"
        f"可用上下文：\n{context}\n\n"
        f"输出要求：{output_hint}\n"
        "不要输出 Markdown 代码块，不要输出与任务无关的内容，不要输出隐藏信息给玩家——仅供主DM决策。"
    )


async def run_focused_agent(
    client: Any,
    model: str,
    role: str,
    task: str,
    context: str,
    max_tokens: int = 600,
    temperature: float = 0.2,
    timeout: float = 40,
) -> str:
    """调用一个专注 LLM 子 Agent，返回精简结论。"""
    content = _compact_prompt(role, task, sanitize_user_text(context)[:10000])
    try:
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是高效、克制、只输出事实与结论的专业子Agent。不要即兴创作，不要写叙事正文，不要输出隐藏信息给玩家。"},
                    {"role": "user", "content": content},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                extra_body={"thinking": {"type": "disabled"}},
            ),
            timeout=timeout,
        )
        msg = resp.choices[0].message
        return (msg.content or getattr(msg, "reasoning_content", "") or "").strip()
    except Exception as e:
        return f"[子Agent失败] {type(e).__name__}: {e}"


async def run_parallel_subagents(
    client: Any,
    model: str,
    tasks: list[dict],
    timeout: float = 30,
) -> dict[str, str]:
    """并发运行多个专业子 Agent。

    - 单个 Agent 失败/超时只丢弃该 Agent 的结果，不阻塞主流程；
    - 所有 Agent 共享同一超时窗口，总耗时约等于最慢的一个 Agent；
    - 结果按 task["key"] 返回，供 format_dm_brief() 聚合。
    """
    async def _one(task: dict) -> tuple[str, str]:
        key = str(task.get("key", ""))
        try:
            result = await run_focused_agent(
                client,
                model,
                role=str(task.get("role", "专业子Agent")),
                task=str(task.get("task", "")),
                context=str(task.get("context", "")),
                max_tokens=int(task.get("max_tokens", 500)),
                temperature=float(task.get("temperature", 0.2)),
                timeout=float(task.get("timeout", timeout)),
            )
        except Exception as e:  # pragma: no cover - 保险
            return key, f"[子Agent失败] {type(e).__name__}: {e}"
        return key, result

    try:
        raw = await asyncio.gather(*(_one(t) for t in tasks), return_exceptions=True)
    except asyncio.CancelledError:
        return {}
    out: dict[str, str] = {}
    for item in raw:
        if isinstance(item, tuple) and len(item) == 2:
            key, value = item
            out[str(key)] = str(value or "")
        elif isinstance(item, Exception):
            continue
    return out


# ── 可调用工具的子 Agent（DeepSeek harness 风格）────────────────

def _allowed_tool_schemas(pack: Any) -> list[dict]:
    """按 SKILL.md 的 allowed-tools 元数据过滤该子 Agent 可用的工具。"""
    allowed = pack.metadata.get("allowed-tools") or []
    if isinstance(allowed, str):
        allowed = [x.strip() for x in allowed.split(",") if x.strip()]
    allowed_set = {str(x).strip() for x in allowed if str(x).strip()}
    if not allowed_set:
        return []
    return [
        t for t in DM_TOOLS
        if str(t.get("function", {}).get("name", "")) in allowed_set
    ]


async def run_tool_subagent(
    client: Any,
    model: str,
    task: dict,
    state: Any,
    max_iterations: int = 4,
    timeout: float = 60,
) -> str:
    """运行一个带工具权限的专业子 Agent，返回给主 DM 的简报。

    - 技能包 `allowed-tools` 决定该子 Agent 能调用哪些工具；
    - 工具调用结果由子 Agent 自行总结成简报，玩家只看到工具本身推送的事件；
    - 子 Agent 的推理、工具选择和简报都不直接展示给玩家。
    """
    skill_name = str(task.get("skill") or "")
    pack = get_agent_skill(skill_name) if skill_name else None
    if pack is None:
        return await run_focused_agent(
            client, model,
            role=str(task.get("role") or "专业子Agent"),
            task=str(task.get("task") or ""),
            context=str(task.get("context") or ""),
            max_tokens=600,
            temperature=0.1,
            timeout=timeout,
        )

    tools = _allowed_tool_schemas(pack)
    system_prompt = (
        f"你是专业子Agent：{pack.name}。\n"
        f"技能说明：{pack.description}\n\n"
        f"{pack.content}\n\n"
        "你可以调用提供的工具来完成任务；工具执行结果会以内部观察返回给你。"
        "你的最终输出是给主 DM 的结论简报：只写事实、已执行的工具、关键数值与结果，"
        "不要写玩家可见的叙事正文，不要提及子Agent/后台/简报，不要泄露隐藏信息给玩家。"
    )
    user_prompt = (
        "请按系统说明完成本轮专业任务，并输出给主 DM 的结论简报。\n\n"
        f"本轮上下文：\n{sanitize_user_text(str(task.get('context') or ''))[:9000]}"
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    observations: list[str] = []

    async def _run() -> str:
        from backend.engine.dm_agent import execute_tool

        for _ in range(max_iterations):
            kwargs: dict[str, Any] = dict(
                model=model,
                messages=messages,
                max_tokens=900,
                temperature=0.1,
                extra_body={"thinking": {"type": "disabled"}},
            )
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            resp = await client.chat.completions.create(**kwargs)
            msg = resp.choices[0].message
            tool_calls = getattr(msg, "tool_calls", None) or []
            if not tool_calls:
                content = str(msg.content or "").strip()
                if content:
                    return content
                break

            messages.append({
                "role": "assistant",
                "content": msg.content or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    }
                    for tc in tool_calls
                ],
            })
            for tc in tool_calls[:4]:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}
                try:
                    result = await execute_tool(name, args, state)
                except Exception as e:  # 工具失败回传给子 Agent，让它自行调整
                    result = f"[工具执行失败] {type(e).__name__}: {e}"
                observations.append(f"{name}: {result}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
        return "\n".join(observations) or "[子Agent未返回结论]"

    try:
        return await asyncio.wait_for(_run(), timeout=timeout)
    except asyncio.TimeoutError:
        return "[子Agent超时]"
    except Exception as e:
        return f"[子Agent失败] {type(e).__name__}: {e}"


async def run_tool_subagents(
    client: Any,
    model: str,
    tasks: list[dict],
    state: Any,
    max_concurrency: int = 4,
    timeout: float = 60,
) -> dict[str, str]:
    """并发运行一组可调用工具的专业子 Agent，按 task key 返回简报。"""
    tasks = list(tasks or [])[:MAX_DELEGATED_TASKS]
    sem = asyncio.Semaphore(max(1, int(max_concurrency)))

    async def _one(task: dict) -> tuple[str, str]:
        key = str(task.get("key", ""))
        async with sem:
            try:
                value = await run_tool_subagent(client, model, task, state, timeout=timeout)
            except Exception as e:  # pragma: no cover - 保险
                value = f"[子Agent失败] {type(e).__name__}: {e}"
        return key, value

    raw = await asyncio.gather(*(_one(t) for t in tasks), return_exceptions=True)
    out: dict[str, str] = {}
    for item in raw:
        if isinstance(item, tuple) and len(item) == 2:
            out[str(item[0])] = str(item[1] or "")
    return out


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


# ── 专业子 Agent 任务编排 ─────────────────────────────────────

_SKILL_FOR_TASK_KEY = {
    "rules": "rules-advisor",
    "combat": "combat-tactics",
    "world": "world-scene",
    "memory": "memory-continuity",
    "graph": "graph-advisor",
}


def get_skill_instruction(name: str, fallback: str = "") -> str:
    """按需加载一个 SKILL.md 技能包正文；缺失时回退调用方默认说明。"""
    pack = get_agent_skill(name)
    if pack is not None and pack.content.strip():
        return pack.content.strip()
    return fallback


def _apply_skill_packs(tasks: list[dict], module: str) -> list[dict]:
    """用 SKILL.md 技能包覆盖子 Agent 的 role/task，保留 Python 侧兜底文本。"""
    for task in tasks:
        key = str(task.get("key", ""))
        skill_name = _SKILL_FOR_TASK_KEY.get(key)
        if key == "rules" and module == "combat":
            skill_name = "combat-rules-advisor"
        if not skill_name:
            continue
        pack = get_agent_skill(skill_name)
        if pack is None:
            continue
        role = str(pack.metadata.get("role") or "").strip()
        if role:
            task["role"] = role
        task["skill"] = skill_name
        if pack.content.strip():
            task["task"] = pack.content.strip()
    return tasks


def _retrieved_text(retrieved: list) -> str:
    lines = []
    for r in (retrieved or [])[:5]:
        if not isinstance(r, dict):
            continue
        title = str(r.get("title", "") or "")
        text = str(r.get("text", "") or "")[:600]
        source = str(r.get("source", "") or "")
        if title or text:
            lines.append(f"- [{title}]({source}) {text}")
    return "\n".join(lines) or "（无检索结果）"


def _recent_text(turns: list) -> str:
    lines = []
    for t in (turns or [])[-4:]:
        pi = str(getattr(t, "player_input", "") or "")
        dm = str(getattr(t, "dm_response", "") or "")[:240]
        if pi or dm:
            lines.append(f"- 玩家: {pi}\n- DM: {dm}")
    return "\n".join(lines) or "（无近期对话）"


def build_dm_brief_tasks(
    *,
    player_input: str,
    module: str,
    lite: bool,
    system: str,
    char_info: str,
    retrieved: list,
    memory_text: str,
    recent_text: str,
    world_text: str,
    world_compact: str,
    graph_text: str,
) -> list[dict]:
    """根据当前模块挑选专业子 Agent，并组装各自的紧凑上下文。

    精简模式也保持 2 个并发子 Agent（世界+记忆），深度模式 3-4 个。
    每个任务都要求“只输出结论”，主 DM 才能低负担地采纳。
    """
    tasks: list[dict] = []

    rules_ctx = (
        f"规则系统：{system}\n"
        f"玩家本轮行动：{player_input}\n"
        f"角色关键数值：\n{char_info[:1600]}\n"
        f"检索到的规则片段：\n{_retrieved_text(retrieved)}"
    )
    world_ctx = (
        f"玩家本轮行动：{player_input}\n"
        f"当前模块：{module}\n"
        f"世界状态完整摘要：\n{world_text[:6500]}\n"
        f"世界状态精简：\n{world_compact[:1800]}"
    )
    memory_ctx = (
        f"玩家本轮行动：{player_input}\n"
        f"长期记忆/暗线/人物影响：\n{memory_text[:4500]}\n"
        f"最近对话：\n{recent_text[:2600]}"
    )
    graph_ctx = (
        f"玩家本轮行动：{player_input}\n"
        f"图谱检索命中：\n{graph_text[:2500] or '（无图谱命中）'}"
    )
    combat_ctx = (
        f"玩家本轮行动：{player_input}\n"
        f"角色关键数值：\n{char_info[:1400]}\n"
        f"世界状态（含NPC/敌人，数值字段在###战斗单位数值中）：\n{world_compact[:3000]}\n"
        f"检索到的规则/图鉴：\n{_retrieved_text(retrieved)}"
    )

    if lite:
        tasks.extend([
            {
                "key": "world", "role": "世界/场景事实顾问",
                "task": "提取当前场景与本回合直接相关的地点、在场NPC、旗标和剧本约束。只列事实，标注【仅DM可见】的隐藏信息。",
                "context": world_ctx, "max_tokens": 400, "temperature": 0.1, "timeout": 20,
            },
            {
                "key": "memory", "role": "剧情连续性顾问",
                "task": "从记忆和最近对话中提取本回合必须遵守的既有事实、上一轮结局与不可矛盾点。只列条款，不要写叙事。",
                "context": memory_ctx, "max_tokens": 400, "temperature": 0.1, "timeout": 20,
            },
        ])
        return _apply_skill_packs(tasks, module)

    if module == "rules":
        tasks.extend([
            {
                "key": "rules", "role": "规则裁决顾问",
                "task": "先判断玩家本轮行动阶段：侦查/观察/确认状态→建议 search_npcs/search_bestiary/dice_roll(Perception或Insight等)；实际攻击→combat_round；施法→cast_spell。然后给出规则结论：技能名/属性/DC/加值依据。没有依据就写“需查询工具”，禁止未经判定直接要求攻击。不要写叙事正文。",
                "context": rules_ctx, "max_tokens": 700, "temperature": 0.1, "timeout": 25,
            },
            {
                "key": "world", "role": "世界/场景事实顾问",
                "task": "提取当前场景与本回合相关的地点、NPC、旗标、剧本约束；隐藏信息标【仅DM可见】。只列事实。",
                "context": world_ctx, "max_tokens": 600, "temperature": 0.1, "timeout": 25,
            },
            {
                "key": "memory", "role": "剧情连续性顾问",
                "task": "提取本回合必须遵守的既有事实、上一轮结局、未完成任务/暗线。只列条款。",
                "context": memory_ctx, "max_tokens": 500, "temperature": 0.1, "timeout": 25,
            },
        ])
    elif module == "combat":
        tasks.extend([
            {
                "key": "rules", "role": "战斗规则顾问",
                "task": "先判断玩家本轮是侦查/移动/施法还是实际攻击：实际攻击才用 combat_round，侦查/观察用 search_npcs/search_bestiary/dice_roll。再给出目标/技能/加值/DC依据；敌人回合用 enemy_attack。不要替玩家决定动作，不要写叙事正文。",
                "context": rules_ctx, "max_tokens": 650, "temperature": 0.1, "timeout": 25,
            },
            {
                "key": "combat", "role": "战斗战术顾问",
                "task": "列出当前战斗中所有战斗单位：名称/HP(含max_hp)/AC/位置/态度/能否行动（被绑、昏迷、濒死等不能行动）。数值优先引用“###战斗单位数值”，没有才写“需 search_npcs/search_bestiary 查询”。不要替玩家选择攻击目标，不要写叙事。",
                "context": combat_ctx, "max_tokens": 650, "temperature": 0.1, "timeout": 25,
            },
            {
                "key": "world", "role": "世界/场景事实顾问",
                "task": "提取当前战斗场景的空间/时间/环境危险/在场NPC/旗标；隐藏信息标【仅DM可见】。只列事实。",
                "context": world_ctx, "max_tokens": 500, "temperature": 0.1, "timeout": 25,
            },
            {
                "key": "memory", "role": "剧情连续性顾问",
                "task": "提取本场战斗前因后果、已造成伤害/伤亡、盟友目标、不可矛盾点。只列条款。",
                "context": memory_ctx, "max_tokens": 450, "temperature": 0.1, "timeout": 25,
            },
        ])
    elif module == "scene":
        tasks.extend([
            {
                "key": "world", "role": "世界/场景事实顾问",
                "task": "提取当前地点、可前往地点、天气/时间、在场NPC、环境线索与旗标；隐藏信息标【仅DM可见】。只列事实。",
                "context": world_ctx, "max_tokens": 700, "temperature": 0.1, "timeout": 25,
            },
            {
                "key": "memory", "role": "剧情连续性顾问",
                "task": "提取与本次探索/移动相关的既有事实、未完成线索、上一轮结局。只列条款。",
                "context": memory_ctx, "max_tokens": 500, "temperature": 0.1, "timeout": 25,
            },
            {
                "key": "graph", "role": "关系图谱顾问",
                "task": "从图谱命中中提取与本次行动直接相关的实体关系/线索链，供主DM推进剧情。只列关系。",
                "context": graph_ctx, "max_tokens": 400, "temperature": 0.1, "timeout": 25,
            },
        ])
    elif module == "social":
        tasks.extend([
            {
                "key": "world", "role": "社交事实顾问",
                "task": "提取对话对象与相关NPC的可见信息、态度、动机、秘密（隐藏信息标【仅DM可见】），以及当前位置/旗标。只列事实，不要替玩家说话。",
                "context": world_ctx, "max_tokens": 650, "temperature": 0.1, "timeout": 25,
            },
            {
                "key": "memory", "role": "剧情连续性顾问",
                "task": "提取与该NPC/事件相关的既有承诺、恩怨、线索与上一轮互动结果。只列条款。",
                "context": memory_ctx, "max_tokens": 500, "temperature": 0.1, "timeout": 25,
            },
            {
                "key": "graph", "role": "关系图谱顾问",
                "task": "提取对话对象及其关联人物的关系强弱/信任度/冲突点，供主DM把握分寸。只列关系。",
                "context": graph_ctx, "max_tokens": 450, "temperature": 0.1, "timeout": 25,
            },
        ])
    elif module == "memory":
        tasks.extend([
            {
                "key": "memory", "role": "剧情连续性顾问",
                "task": "回答玩家涉及“之前/记得/线索”等问题：从记忆与暗线中提取最相关事实；不记得就写“记忆中没有，引导玩家检定或探索”。只列条款。",
                "context": memory_ctx, "max_tokens": 700, "temperature": 0.1, "timeout": 25,
            },
            {
                "key": "world", "role": "世界/场景事实顾问",
                "task": "提取与回忆内容相关的当前世界事实与剧本约束。只列事实。",
                "context": world_ctx, "max_tokens": 500, "temperature": 0.1, "timeout": 25,
            },
            {
                "key": "graph", "role": "关系图谱顾问",
                "task": "提取与回忆对象相关的实体关系。只列关系。",
                "context": graph_ctx, "max_tokens": 400, "temperature": 0.1, "timeout": 25,
            },
        ])
    elif module == "graph":
        tasks.extend([
            {
                "key": "graph", "role": "关系图谱顾问",
                "task": "整理与玩家行动最相关的实体关系、路径、信任/敌对变化依据。只列关系与结论。",
                "context": graph_ctx, "max_tokens": 650, "temperature": 0.1, "timeout": 25,
            },
            {
                "key": "memory", "role": "剧情连续性顾问",
                "task": "提取支持这些关系的对话/事件依据与不可矛盾点。只列条款。",
                "context": memory_ctx, "max_tokens": 450, "temperature": 0.1, "timeout": 25,
            },
            {
                "key": "world", "role": "世界/场景事实顾问",
                "task": "提取相关NPC/地点当前状态。只列事实。",
                "context": world_ctx, "max_tokens": 450, "temperature": 0.1, "timeout": 25,
            },
        ])
    else:  # narrative：主DM自由度最高，但仍要有世界/记忆/图谱事实兜底
        tasks.extend([
            {
                "key": "world", "role": "世界/场景事实顾问",
                "task": "提取当前场景、在场NPC、旗标与最近剧情钩子；隐藏信息标【仅DM可见】。只列事实。",
                "context": world_ctx, "max_tokens": 650, "temperature": 0.15, "timeout": 25,
            },
            {
                "key": "memory", "role": "剧情连续性顾问",
                "task": "提取最近剧情的关键事实、玩家选择后果与不可矛盾点。只列条款。",
                "context": memory_ctx, "max_tokens": 550, "temperature": 0.15, "timeout": 25,
            },
            {
                "key": "graph", "role": "关系图谱顾问",
                "task": "提取与当前剧情最相关的实体关系。只列关系。",
                "context": graph_ctx, "max_tokens": 350, "temperature": 0.15, "timeout": 25,
            },
        ])
    return _apply_skill_packs(tasks, module)


_SECTION_TITLES = {
    "rules": "规则顾问结论",
    "combat": "战斗战术顾问结论",
    "world": "世界/场景顾问结论",
    "memory": "剧情连续性顾问结论",
    "graph": "关系图谱顾问结论",
}


def format_dm_brief(results: dict[str, str]) -> str:
    """把并发子 Agent 结果聚合为主 DM 可快速阅读的专家简报。"""
    order = ["rules", "combat", "world", "memory", "graph"]
    parts: list[str] = []
    for key in order:
        value = str(results.get(key, "") or "").strip()
        if not value or value.startswith(("[子Agent失败]", "[子Agent超时]")):
            continue
        title = _SECTION_TITLES.get(key, key)
        parts.append(f"### {title}\n{value[:900]}")
    return "\n\n".join(parts)


# ── 旧接口兼容 ───────────────────────────────────────────────

async def summarize_rules_for_player(
    client: Any,
    model: str,
    query: str,
    retrieved_text: str,
) -> str:
    """规则/战斗模块子 Agent：把检索到的规则片段整理成简洁可执行的规则结论。"""
    return await run_focused_agent(
        client, model,
        role="规则整理者",
        task="根据检索到的规则片段，整理玩家本次行动需要的规则结论。",
        context=retrieved_text,
        max_tokens=800,
        temperature=0.1,
    )


async def summarize_world_for_player(
    client: Any,
    model: str,
    query: str,
    world_context: str,
) -> str:
    """场景/社交模块子 Agent：把冗长世界背景压缩为当前场景可用的信息。"""
    return await run_focused_agent(
        client, model,
        role="世界背景整理者",
        task=f"根据当前玩家问题「{query}」，从世界背景中提取当前场景最相关的事实。",
        context=world_context,
        max_tokens=700,
        temperature=0.2,
    )
