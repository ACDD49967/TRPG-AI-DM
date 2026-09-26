"""候选子 Agent 任务装配：按模块给出要跑的专业技能，并套上技能包。

从 `backend/engine/dm_brief.py` 拆出（`build_dm_brief_tasks` 是这里的主入口）。
"""
from __future__ import annotations

from backend.engine.dm_brief_context import (
    GRAPH_TEXT_BUDGET, MEMORY_TEXT_BUDGET, RECENT_TEXT_BUDGET, WORLD_COMPACT_BUDGET,
    WORLD_TEXT_BUDGET, _recent_text, _retrieved_text,
)
from backend.skills import get_agent_skill


_SKILL_FOR_TASK_KEY = {
    "rules": "rules-advisor",
    "combat": "combat-tactics",
    "world": "world-scene",
    "memory": "memory-continuity",
    "graph": "graph-advisor",
}


def skipped_agent_keys() -> set[str]:
    """`DND_SKIP_AGENTS=graph,memory` 用来做成本 A/B；默认空集（不改变行为）。

    深模式此前没有任何"少派一个子 Agent"的开关，只能改代码再回滚；
    这里留下一个显式实验入口，测完再决定要不要改默认编队。
    """
    import os

    raw = (os.environ.get("DND_SKIP_AGENTS") or "").strip()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


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
        f"世界状态完整摘要：\n{world_text[:WORLD_TEXT_BUDGET]}\n"
        f"世界状态精简：\n{world_compact[:WORLD_COMPACT_BUDGET]}"
    )
    memory_ctx = (
        f"玩家本轮行动：{player_input}\n"
        f"长期记忆/暗线/人物影响：\n{memory_text[:MEMORY_TEXT_BUDGET]}\n"
        f"最近对话：\n{recent_text[:RECENT_TEXT_BUDGET]}"
    )
    graph_ctx = (
        f"玩家本轮行动：{player_input}\n"
        f"图谱检索命中：\n{graph_text[:GRAPH_TEXT_BUDGET] or '（无图谱命中）'}"
    )
    # 精简模式**复用同一套模块化选人逻辑**，只是把预算调小。
    # 曾经精简模式硬编码成"world+memory"：结果战斗回合多派了 memory（深度模式特意去掉它，
    # 见下方 combat 分支的注释）、探索/社交回合又少派 graph，实测比深度模式贵 1.4 倍
    # （3 run 中位 119,618 vs 80,822）。选人逻辑只留一份，模式只影响预算。
    if module == "rules":
        tasks.extend([
            {
                "key": "rules", "role": "规则裁决顾问",
                "task": "先判断玩家本轮行动阶段：侦查/观察/确认状态→建议 search_npcs/search_bestiary/dice_roll(Perception或Insight等)；实际攻击→combat_round；施法→cast_spell。然后给出规则结论：技能名/属性/DC/加值依据。没有依据就写“需查询工具”，禁止未经判定直接要求攻击。不要写叙事正文。",
                "context": rules_ctx, "max_tokens": 700, "temperature": 0.1, "timeout": 25,
                # 结算型任务：写型工具跑完就直接用真实结果当结论，省掉一次复述往返
                "fast_settle": True,
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
                "fast_settle": True,
            },
            # 战斗回合只留两个子 Agent：
            # - "combat"（战斗战术顾问）已取消：它的全部工作是把后端算好的
            #   ### 战斗单位数值 名册复述一遍，而名册现在直接写进主 DM 提示词
            #   （见 dm_prompts.build_system_prompt）；
            # - "memory"（剧情连续性顾问）在战斗回合也取消：连续性事实本来就在
            #   主 DM 的提示词里（memory_context_override），而实测它是三个候选里
            #   最慢的一个（并发墙钟从 4.9 秒被它拖到 7.3 秒），分配器自己在三次
            #   实测中也没在战斗回合选过它。
            {
                "key": "world", "role": "世界/场景事实顾问",
                "task": "提取当前战斗场景的空间/时间/环境危险/在场NPC/旗标；隐藏信息标【仅DM可见】。只列事实。",
                "context": world_ctx, "max_tokens": 500, "temperature": 0.1, "timeout": 25,
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
    skip = skipped_agent_keys()
    if skip:
        kept = [t for t in tasks if str(t.get("key", "")).lower() not in skip]
        # 防御：实验开关不能把上下文清空——一个都不剩时保留优先级最高的那个
        tasks = kept or tasks[:1]
    if lite:
        # 精简模式：编队与深度模式**同一套逻辑**，但只保留优先级最高的前 N 个
        # （列表顺序就是优先级：战斗=rules>world，社交/探索=world>memory>graph），
        # 并把预算收小。N 默认 1，可用 DND_LITE_AGENTS 覆盖以便 A/B。
        try:
            import os
            keep = max(1, int(os.environ.get("DND_LITE_AGENTS") or 1))
        except (TypeError, ValueError):
            keep = 1
        tasks = tasks[:keep]
        for task in tasks:
            try:
                task["max_tokens"] = max(250, int(int(task.get("max_tokens") or 500) * 0.6))
            except (TypeError, ValueError):
                task["max_tokens"] = 300
            task["timeout"] = 20
    return _apply_skill_packs(tasks, module)
