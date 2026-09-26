"""开场白生成：新局/读档后的开场场景与地点登记。

从 backend.engine.dm_agent 拆出。
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

from backend.engine.dm_prompts import (
    COC_OPENING_PROMPT, OPENING_PROMPT, _extract_outline, _mode_instructions,
    build_character_info,
)
from backend.engine.dm_runtime import (
    _call_thinking_params, _client, _game_system, _model, _play_mode,
    _stream_with_tools, sanitize_narrative,
)
from backend.engine.dm_subagents import _generate_suggestions_subagent
from backend.engine.game_systems import build_system_rule_block
from backend.engine.session import GameSessionState, push_event, push_narrative_token
from backend.engine.world_state import LocationEntry, WorldState
from backend.skills import get_skill





async def generate_opening_scene(state: GameSessionState) -> str:
    lite = _play_mode(state) == "lite"
    client = _client(state); model = _model(state)
    ci = build_character_info(state)
    bs = state.character_info.get("backstory", "")
    wc = state.character_info.get("world_outline", "")
    scenario_summary = state.character_info.get("scenario_summary", "")
    if not wc and getattr(state, "world_state", None) is not None:
        ws_open = state.world_state
        if getattr(ws_open, "world_outline", ""):
            wc = ws_open.world_outline
        else:
            wc = "## 当前世界状态\n" + ws_open.to_context_string()[:1800]
    skill = get_skill(_game_system(state))
    summary_limit = 300 if lite else skill.summary_limit
    outline_limit = 800 if lite else skill.outline_limit
    if scenario_summary:
        outline_part = _extract_outline(wc, max_chars=1200) if lite else wc[:outline_limit]
        wc = f"## 剧本总结\n{scenario_summary[:summary_limit]}\n\n## 冒险大纲\n{outline_part}" if wc else f"## 剧本总结\n{scenario_summary[:summary_limit]}"
    opening_template = COC_OPENING_PROMPT if _game_system(state) == "coc" else OPENING_PROMPT
    prompt = opening_template.format(character_info=ci, backstory=(bs or "暂无")[:200 if lite else 500], world_context=wc[:2000] if wc else "暂无")
    prompt += _mode_instructions(state)
    prompt += build_system_rule_block(_game_system(state), state.character_info.get("custom_rules", ""))
    prompt += "\n\n【输出硬性要求】直接输出开场白正文。禁止输出任何思考过程、规划、分析、角色属性复述、内部独白；不要出现“好的，我现在要扮演...”等前置语句。"
    system_role = "你是克苏鲁的呼唤守密人（Keeper），负责营造神秘、恐怖与调查氛围。" if _game_system(state) == "coc" else "你是世界级D&D地下城主。"
    # 开场白：降低思考/温度以提速，但必须给足最终正文 token，不能只生成 reasoning
    mult, tdelta = _call_thinking_params(state, "low")
    max_tokens = 4000 if lite else 6000
    max_tokens = min(8000, max_tokens)
    temp = max(0.0, min(1.5, skill.temperature + tdelta))
    full = ""
    streamed = False
    last_err = None
    for attempt in range(1, 3):
        current_max_tokens = max_tokens if attempt == 1 else min(max_tokens * 2, 5000)
        try:
            if attempt == 1:
                # 第一次流式，带 60s 空闲超时，防止卡死
                stream = await client.chat.completions.create(
                    model=model, messages=[{"role":"system","content":system_role},{"role":"user","content":prompt}],
                    max_tokens=current_max_tokens, temperature=temp, stream=True,
                    extra_body={"thinking": {"type": "disabled"}},
                )
                full = ""
                while True:
                    try:
                        chunk = await asyncio.wait_for(stream.__anext__(), timeout=60)
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError:
                        print(f"[Opening] 第{attempt}次流式空闲超时(60s无新数据)")
                        raise RuntimeError("流式响应空闲超时")
                    if state.aborted:
                        await stream.close()
                        break
                    d = chunk.choices[0].delta if chunk.choices else None
                    # 只收集正文；绝不把 reasoning_content 当作玩家可见文案
                    if d and d.content:
                        full += d.content
                        streamed = True
                        await push_narrative_token(state, d.content)
            else:
                # 第二次非流式：只接受正文 content，不把 reasoning_content 当作叙事
                resp = await client.chat.completions.create(
                    model=model, messages=[{"role":"system","content":system_role},{"role":"user","content":prompt}],
                    max_tokens=current_max_tokens, temperature=temp,
                    extra_body={"thinking": {"type": "disabled"}},
                )
                msg = resp.choices[0].message
                full = msg.content or ""

            full = sanitize_narrative(full)
            if full:
                break
            # stream 响应没有 reasoning_content 汇总；这里仅打印空响应便于排查
            print(f"[Opening] 第{attempt}次空响应 (max_tokens={current_max_tokens})")
            raise RuntimeError("空响应")
        except Exception as e:
            last_err = e
            print(f"[Opening] 第{attempt}次失败: {e}")
            if attempt == 1:
                await asyncio.sleep(1)

    if not full:
        # 第三次兜底：极简短 prompt，尽量仍生成真实开场而不是模板
        try:
            minimal_prompt = (
                f"请为角色「{state.character_name}」写一段150字左右的冒险开场白。"
                f"直接输出正文，不要输出思考过程、分析、角色信息复述或内部独白。"
                f"第二人称，从动作中间开始，包含环境细节与一个即将发生的悬念。"
                f"角色背景：{(bs or '')[:300]}"
            )
            resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": system_role},
                              {"role": "user", "content": minimal_prompt}],
                    max_tokens=1200,
                    temperature=0.4,
                    extra_body={"thinking": {"type": "disabled"}},
                ),
                timeout=30,
            )
            msg = resp.choices[0].message
            full = msg.content or ""
            full = sanitize_narrative(full)
        except Exception as e:
            last_err = e
            print(f"[Opening] 极简短兜底失败: {e}")

    if full and not streamed:
        await push_narrative_token(state, full)

    if not full:
        print(f"[Opening] 三次生成均失败，最后错误: {last_err}")
        full = f"欢迎，{state.character_name}。"
        await push_narrative_token(state, full)

    # 从开场叙事中提取场景信息并写入WorldState，确保Journal立即可用
    ws = getattr(state, 'world_state', None)
    if ws:
        scene_match = re.search(r'\*\*当前场景\*\*[：:]\s*(.+?)(?:\n|$)', full)
        if scene_match:
            parts = [p.strip() for p in scene_match.group(1).split('·')]
            if len(parts) >= 1 and parts[0]:
                ws.scene.current_location = parts[0]
            if len(parts) >= 4:
                # 兼容模型把时间写成“第1天·晨”这类带分隔符的情况：
                # 结构应为 地点 · 时间 · 天气 · 在场NPC
                ws.scene.current_time = "·".join(parts[1:-2]) if len(parts) > 4 else parts[1]
                ws.scene.weather = parts[-2]
                npc_part = parts[-1]
                ws.scene.visible_npcs_here = (
                    [n.strip() for n in npc_part.split('、') if n.strip()]
                    if npc_part and not npc_part.startswith("无NPC") else []
                )
            else:
                if len(parts) >= 2 and parts[1]:
                    ws.scene.current_time = parts[1]
                if len(parts) >= 3 and parts[2]:
                    ws.scene.weather = parts[2]
            # 世界初始化：确保当前地点存在且已发现，避免开场后 Journal/图谱全空
            if not ws.scene.current_location:
                ws.scene.current_location = "冒险的起点"
            if ws.get_location(ws.scene.current_location) is None:
                from backend.engine.world_state import LocationEntry
                ws.add_location(LocationEntry(
                    name=ws.scene.current_location,
                    description="当前冒险场景（由开场自动初始化）",
                    discovered=True,
                ))
            # 通过 update_scene 统一发现当前地点/在场NPC，避免初始全部隐藏
            ws.update_scene()
            print(f"[Opening] 场景已写入: {ws.scene.current_location}")

    # 开场行动建议也走独立子Agent，不由主DM在叙事正文里夹带
    try:
        opening_choices = await _generate_suggestions_subagent(state, "游戏开场", full)
        if opening_choices:
            await push_event(state, "choices", {"options": opening_choices})
    except Exception as e:
        print(f"[OpeningChoices] 开场建议生成失败: {e}")

    # 保存开场白，读档时恢复
    state.opening_text = full
    return full
