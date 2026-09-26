"""主 DM 的运行期工具：工具子集与流式循环（模型配置与叙事过滤已拆出）。

按职责分三段，这里只做装配与再导出，`dm_agent` / `dm_turn` 的 import 面不变：
- `dm_llm_config`：客户端、模型名、思考档位、规则系统
- `dm_narrative_filter`：反八股清洗与工具回声过滤
- 本模块：MODULE_TOOL_NAMES / _module_tools / _stream_with_tools
"""
from __future__ import annotations

import asyncio
import json
import random
import re
from typing import Any

from backend.config import settings
from backend.engine.session import GameSessionState, push_narrative_token
from backend.engine.tools import DM_TOOLS  # noqa: F401

from backend.engine.dm_llm_config import (  # noqa: F401
    _as_bool, _call_thinking_params, _client, _game_system, _model, _play_mode,
    _safe_error_text, _thinking_extra_body, _thinking_params, dm_think_mode,
)
from backend.engine.dm_narrative_filter import (  # noqa: F401
    CLICHE_PATTERNS, _META_LEAK_PATTERN, _TOOL_ECHO_PATTERN, _TOOL_ECHO_SIGNATURE,
    _dedupe_fragments, _is_player_visible_segment, sanitize_narrative,
)
from backend.engine.dm_tool_protocol import (  # noqa: F401
    repair_tool_message_pairs, unpaired_tool_calls,
)


MODULE_TOOL_NAMES = {
    "rules": ["dice_roll", "update_state", "get_character_state", "adjust_resource",
              "cast_spell", "search_spells", "search_knowledge", "update_world_state",
              "prune_world_state", "learn_spell", "forget_spell", "roll_treasure",
              "generate_name", "npc_quirk", "equip_item", "add_scenario_spell", "save_damage",
              "advance_time", "apply_hazard", "resolve_trap", "resolve_stealth",
              "resolve_contest", "apply_poison",
              "resolve_chase", "forget_memory",
              "suggest_choices"],
    "combat": ["combat_round", "enemy_attack", "death_saving_throw", "take_rest", "search_npcs",
               "search_bestiary", "update_state", "update_scene", "update_world_state",
               "get_bestiary_card", "add_scenario_bestiary", "adjust_bestiary",
               "prune_world_state", "equip_item", "roll_treasure", "save_damage",
               "set_tactical_state", "apply_hazard", "resolve_trap", "resolve_stealth",
               "resolve_contest", "apply_poison",
               "resolve_chase",
               "suggest_choices"],
    "scene": ["update_scene", "search_locations", "get_location_card",
              "reveal_info", "update_world_state", "prune_world_state",
               "add_scenario_map", "update_city_entry", "generate_name",
               "set_tactical_state", "advance_time", "apply_hazard", "resolve_trap",
               "resolve_stealth", "resolve_chase",
               "suggest_choices"],
    "social": ["search_npcs", "adjust_npc", "add_character_note",
               "update_knowledge_graph", "get_entity_graph", "update_world_state",
               "prune_world_state", "promote_npc", "update_bestiary_entry",
               "suggest_choices"],
    "memory": ["search_knowledge", "search_memory", "get_entity_graph", "get_graph_path",
               "add_memory", "forget_memory", "record_plot_memory", "update_world_state",
               "prune_world_state", "suggest_choices"],
    "graph": ["get_entity_graph", "get_graph_path", "update_knowledge_graph",
              "update_world_state", "prune_world_state", "suggest_choices"],
    # narrative 之前没有白名单，导致每回合把全部 41 个工具（19.2k 字符 schema）都发给模型。
    # 实测这是单回合 token 的最大来源，这里收窄到叙事回合真正会用到的能力；
    # 其余能力由调度器分流到 rules/combat/scene/social/memory/graph 模块。
    "narrative": ["dice_roll", "update_state", "combat_round", "enemy_attack",
                  "death_saving_throw", "take_rest", "equip_item", "cast_spell",
                  "update_scene", "update_world_state", "add_character_note",
                  "add_memory", "search_knowledge", "search_npcs", "search_bestiary", "save_damage",
                  "forget_memory",
                  "apply_hazard", "resolve_trap", "resolve_stealth",
                  "resolve_contest", "apply_poison",
                  "resolve_chase",
                  "suggest_choices"],
}




def _module_tools(module: str, all_tools: list) -> list:
    names = set(MODULE_TOOL_NAMES.get(module, []))
    if not names:
        picked = list(all_tools)
    else:
        picked = [t for t in all_tools if t.get("function", {}).get("name", "") in names]
    # 行动建议已完全剥离到后台子Agent：主DM永远看不到 suggest_choices 工具
    return [t for t in picked if t.get("function", {}).get("name", "") != "suggest_choices"]


# 部分 OpenAI 兼容网关不支持 stream_options.include_usage；按客户端记一次，避免每次重试。
_STREAM_USAGE_UNSUPPORTED: set[int] = set()


async def _stream_with_tools(client, model, messages, tools, state, max_tokens=2048, temperature: float | None = None, tool_choice: str | dict | None = "auto", thinking_mode: str = "auto"):
    # 协议不变量：assistant.tool_calls 后面必须有等量 tool 响应，否则本次调用直接 400。
    # 放在这里是因为它是主 DM 唯一的模型调用出口（含回合末补叙事）。
    repair_tool_message_pairs(messages)
    mult, tdelta = _call_thinking_params(state, thinking_mode)
    max_tokens = min(8000, int(max_tokens * mult))
    temp = (temperature if temperature is not None else settings.TEMPERATURE) + tdelta
    temp = max(0.0, min(1.5, temp))
    extra_body = _thinking_extra_body(state, thinking_mode)
    create_kwargs = dict(
        model=model, messages=messages,
        max_tokens=max_tokens, temperature=temp, stream=True,
    )
    # 让 OpenAI 兼容网关在流末尾返回 usage；不保存 prompt/正文，只采集 token 数。
    wants_usage = id(client) not in _STREAM_USAGE_UNSUPPORTED
    if wants_usage:
        create_kwargs["stream_options"] = {"include_usage": True}
    if tools:
        create_kwargs["tools"] = tools
        create_kwargs["tool_choice"] = tool_choice
    if extra_body:
        create_kwargs["extra_body"] = extra_body
    try:
        stream = await client.chat.completions.create(**create_kwargs)
    except Exception as exc:
        # 网关不认识该参数时降级重试一次，后续调用不再携带。
        message = str(exc).lower()
        if wants_usage and ("stream_options" in message or "include_usage" in message):
            _STREAM_USAGE_UNSUPPORTED.add(id(client))
            create_kwargs.pop("stream_options", None)
            stream = await client.chat.completions.create(**create_kwargs)
        else:
            raise
    content = ""; reasoning_content = ""; tc_map = {}
    had_tool_call = False  # P0-2修复：追踪工具调用边界

    # 句子级流式过滤：把“系统检定工具需要额外参数”等幕后台词拦截在推送之前
    pending = ""

    async def emit(part: str):
        nonlocal pending
        pending += part
        while True:
            m = re.search(r"[。！？!?\n]", pending)
            if not m:
                break
            idx = m.end()
            seg = pending[:idx]
            pending = pending[idx:]
            if _is_player_visible_segment(seg):
                await push_narrative_token(state, seg)

    async def flush_pending():
        nonlocal pending
        if pending.strip():
            if _is_player_visible_segment(pending):
                await push_narrative_token(state, pending)
        elif pending:
            await push_narrative_token(state, pending)
        pending = ""

    try:
        async for chunk in stream:
            if state.aborted: break
            d = chunk.choices[0].delta if chunk.choices else None
            if not d: continue
            if getattr(d, "reasoning_content", None):
                reasoning_content += d.reasoning_content
            if d.content:
                # P0-2修复：工具调用后新文本开始时，确保有换行分隔
                if had_tool_call and content and not content.endswith('\n'):
                    content += '\n'
                    await emit('\n')
                content += d.content
                await emit(d.content)
            if d.tool_calls:
                # P0-2修复：检测到工具调用——确保叙事文本以完整句子结尾
                had_tool_call = True
                await flush_pending()
                if content and not re.search(r'[。！？\n]\s*$', content):
                    content += '\n'
                    await push_narrative_token(state, '\n')
                for tc in d.tool_calls:
                    i = tc.index
                    if i not in tc_map: tc_map[i] = {"id":"","function":{"name":"","arguments":""}}
                    if tc.id: tc_map[i]["id"] = tc.id
                    if tc.function:
                        if tc.function.name: tc_map[i]["function"]["name"] = tc.function.name
                        if tc.function.arguments: tc_map[i]["function"]["arguments"] += tc.function.arguments
    finally:
        # 提前 break（中断/工具上限）时必须释放流，否则连接与响应对象会泄漏，
        # 退出时还会出现 "generator didn't stop after athrow()"。
        close = getattr(stream, "close", None)
        if close is not None:
            try:
                await close()
            except Exception:
                pass
    await flush_pending()
    # reasoning_content 是模型内部推理，绝不能作为玩家正文下发。
    # 若模型只返回 reasoning、没有正文也没有工具调用，返回空串，由上层追加一次系统重试。
    if not content.strip() and not tc_map and reasoning_content.strip():
        print("[DM] 模型只返回 reasoning_content，已拦截，不注入玩家叙事")
    return content, list(tc_map.values())
