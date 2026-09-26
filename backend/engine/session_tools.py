"""会话与规则裁决类工具：骰子、记忆、装备、休息、死亡豁免、行动建议。

从 backend.engine.dm_agent 拆出；dm_agent 反向再导出，保持既有调用方不变。
少数通用工具（_game_system/_as_bool/_safe_error_text/_client/_model）通过惰性 shim 调用，
避免与 dm_agent 形成循环导入。
"""
from __future__ import annotations

import asyncio
import random
import re

from backend.engine.character_state import _exec_update_state
from backend.engine.rules import (
    AdvantageMode, DeathSaves, ability_mod_for_skill, roll_death_save, short_rest, skill_check,
)
# 骰子裁判（含自定义骰式）拆到 dice_tools，这里再导出保持既有调用面
from backend.engine.dice_tools import (  # noqa: F401
    _exec_dice_roll, dice_from_custom_rules,
)
from backend.engine.session import (
    GameSessionState, push_event, push_narrative_token,
)
from backend.engine.tool_shims import _game_system, _as_bool, _safe_error_text
# 休息工具（5e 生命骰 / 4e 回复力）拆到 rest_tools，这里再导出保持既有调用面
from backend.engine.rest_tools import (  # noqa: F401
    SHORT_REST_RESOURCE_KEYS, _exec_rest,
)


async def _exec_add_memory(args: dict, state: GameSessionState) -> str:
    fact = args.get("memory_text", "").strip()
    if not fact:
        return "未记录（空内容）"
    state.memory.add_world_fact(fact)
    ws = getattr(state, "world_state", None)
    turn = ws.turn_count if ws is not None else 0
    try:
        from backend.long_term_memory import store_memory
        store_memory(
            state.username, fact,
            memory_type="semantic",
            importance=0.65, confidence=0.8,
            session_id=state.session_id, turn=turn,
            source="add_memory", tags=["world_fact"],
        )
    except Exception:
        pass
    return f"已记录: {fact}"


async def _exec_forget_memory(args: dict, state: GameSessionState) -> str:
    """删掉一条记错的长期记忆（按 id，或按正文片段匹配）。

    长期记忆原先只能创建与检索：删改没有任何工具入口，DM 记错一件事就只能让它一直错下去。
    这里与 `/api/memories` 走同一个存储层，SQLite 索引、Markdown 页面与语义事实一起清。
    """
    from backend.memory_retrieve import load_recent_memories
    from backend.memory_manage import delete_memory, load_memory

    username = state.username or "default"
    mem_id = str(args.get("memory_id") or "").strip()
    content = str(args.get("content") or args.get("memory_text") or "").strip()
    if not mem_id and not content:
        return "⚠ forget_memory 需要 memory_id 或 content（要删掉的记忆正文片段）"
    if not mem_id:
        for item in load_recent_memories(username, limit=200):
            if content and content in str(item.get("content") or ""):
                mem_id = str(item.get("id") or "")
                break
        if not mem_id:
            return f"⚠ 没有找到包含「{content}」的记忆"
    memory = load_memory(username, mem_id)
    if memory is None:
        return f"⚠ 记忆 {mem_id} 不存在（可能已经删过）"
    if not delete_memory(username, mem_id):
        return f"⚠ 删除失败：{mem_id}"
    return f"🗑 已删除记忆：{str(memory.get('content'))[:60]}"


async def _exec_search_memory(args: dict, state: GameSessionState) -> str:
    """检索 EverOS 长期记忆库，返回可引用的记忆条目。"""
    query = str(args.get("query") or "").strip()
    if not query:
        return "⚠ 需要 query"
    memory_types = [str(x) for x in (args.get("memory_types") or []) if str(x).strip()]
    try:
        top_k = max(1, min(10, int(args.get("top_k", 5) or 5)))
    except (TypeError, ValueError):
        top_k = 5
    try:
        from backend.long_term_memory import retrieve_memories
        results = await asyncio.to_thread(
            retrieve_memories,
            state.username, query,
            entities=[], memory_types=memory_types, top_k=top_k,
        )
    except Exception as e:
        return f"❌ 长期记忆检索失败: {_safe_error_text(e)}"
    if not results:
        return "未找到相关长期记忆。"
    lines = ["## 长期记忆检索结果（EverOS Markdown 记忆库）"]
    for r in results:
        text = str(r.get("summary") or r.get("content") or "")
        if len(text) > 220:
            text = text[:220] + "…"
        lines.append(
            f"- [{r.get('memory_type', 'semantic')} 重要度{r.get('importance', 0.5):.2f} "
            f"相关度{r.get('score', 0):.2f}] {text}"
        )
        if r.get("vault_path"):
            lines.append(f"  Markdown: {r['vault_path']}")
    return "\n".join(lines)


async def _exec_record_plot_memory(args: dict, state: GameSessionState) -> str:
    kind = str(args.get("kind") or "").strip()
    title = str(args.get("title") or "").strip()
    desc = str(args.get("description") or "").strip()
    impact = str(args.get("impact") or "").strip()
    status = str(args.get("status") or "未触发").strip()
    if status not in ("未触发", "进行中", "已完成", "已失败"):
        status = "未触发"
    npcs = [str(x).strip() for x in (args.get("related_npcs") or []) if str(x).strip()]
    locs = [str(x).strip() for x in (args.get("related_locations") or []) if str(x).strip()]
    strength = args.get("strength")
    confidence = args.get("confidence")
    visible = _as_bool(args.get("visible_to_players", False))
    ws = getattr(state, "world_state", None)
    turn = ws.turn_count if ws is not None else 0

    def update_relations(anchor: str, relation: str):
        if ws is None or not anchor:
            return
        for npc in npcs:
            ws.add_or_update_relation(anchor, npc, relation=relation,
                                      strength=strength, confidence=confidence,
                                      notes=desc or impact or title)
        for loc in locs:
            ws.add_or_update_relation(anchor, loc, relation=relation,
                                      strength=strength, confidence=confidence,
                                      notes=desc or impact or title)
        # 相关NPC之间也建立弱关联（共同卷入同一事件/暗线）
        for i in range(len(npcs)):
            for j in range(i + 1, len(npcs)):
                ws.add_or_update_relation(npcs[i], npcs[j], relation="co_involved",
                                          strength=strength if strength is not None else 40.0,
                                          confidence=confidence if confidence is not None else 0.4,
                                          notes=f"共同关联: {title}")

    if kind == "major_event":
        if not title:
            return "未记录（缺少title）"
        state.memory.add_major_event(title=title, description=desc, impact=impact, turn=turn, npcs=npcs, locations=locs)
        update_relations(title, "plot_link")
        try:
            from backend.long_term_memory import store_memory
            store_memory(
                state.username, f"{title}: {desc} {impact}".strip(),
                memory_type="episodic", summary=title,
                entities=npcs + locs, tags=["major_event"],
                importance=0.85, confidence=0.9,
                session_id=state.session_id, turn=turn, source="record_plot_memory",
            )
        except Exception:
            pass
        return f"已记录大事件: {title}"
    if kind == "hidden_thread":
        if not title:
            return "未记录（缺少title）"
        state.memory.add_hidden_thread(key=title, description=desc, status=status, related_npcs=npcs, related_locations=locs, turn=turn)
        if ws is not None:
            ws.set_flag(key=title, status=status, description=desc or title, consequence=impact, visible=visible)
            update_relations(title, "thread_link")
        try:
            from backend.long_term_memory import store_memory
            store_memory(
                state.username, f"{title} [{status}]: {desc} {impact}".strip(),
                memory_type="thread", summary=title,
                entities=npcs + locs, tags=["hidden_thread", status],
                importance=0.8, confidence=0.85,
                session_id=state.session_id, turn=turn, source="record_plot_memory",
            )
        except Exception:
            pass
        return f"已记录暗线: {title} [{status}]"
    if kind == "character_impact":
        if not title or not impact:
            return "未记录（需要title人物名和impact影响）"
        state.memory.add_character_impact(name=title, impact=impact, event=desc, turn=turn)
        update_relations(title, "impact_link")
        try:
            from backend.long_term_memory import store_memory
            store_memory(
                state.username, f"{title}: {impact} {desc}".strip(),
                memory_type="reflection", summary=title,
                entities=[title] + npcs + locs, tags=["character_impact"],
                importance=0.75, confidence=0.8,
                session_id=state.session_id, turn=turn, source="record_plot_memory",
            )
        except Exception:
            pass
        return f"已记录人物影响: {title}"
    return "未知类型: " + kind


async def _exec_equip_item(args: dict, state: GameSessionState) -> str:
    name = str(args.get("name") or "").strip()
    equipped = _as_bool(args.get("equipped", True))
    if not name:
        return "未指定物品"
    changes = {"inventory_equip" if equipped else "inventory_unequip": name}
    return await _exec_update_state({"changes": changes, "reason": "装备操作"}, state)


async def _exec_death_save(args: dict, state: GameSessionState) -> str:
    if _game_system(state) == "coc":
        desc = "💀 COC 没有 D&D 式死亡豁免：HP 降至 0 时角色重伤昏迷，由 AI 根据伤害来源决定是否濒死或死亡。"
        await push_narrative_token(state, f"\n{desc}\n")
        return desc

    ds = getattr(state, '_death_saves', DeathSaves())
    result = roll_death_save(ds)
    state._death_saves = ds
    ws = getattr(state, "world_state", None)
    state._death_save_turn = int(getattr(ws, "turn_count", 0) or 0)
    display_result = "大成功" if result["result"] == "复活" else (
        "大失败" if result["result"] == "两次失败" else result["result"])
    await push_event(state, "dice_roll", {
        "skill": "死亡豁免", "dc": 10,
        "roll": result["roll"], "modifier": 0, "result": display_result,
    })
    desc = f"💀 死亡豁免: d20={result['roll']}→{result['result']} [成功{result['successes']}/3 失败{result['failures']}/3]"
    if result.get("hp_restored"):
        desc += "\n自然20！你咳出一口血，睁开了眼睛。"
        await _exec_update_state({"changes": {"hp": 1}, "reason": "自然20恢复意识"}, state)
    elif result.get("dead"):
        desc += "\n☠️ 呼吸停止了。冒险到此为止。"
        state.character_info["hp"] = 0
        state.dying = False
        state.character_dead = True
        await push_event(state, "game_event", {"type": "player_death", "description": "角色死亡。可以创建新角色继续这个世界的冒险。"})
    elif result.get("stable"):
        desc += "\n你不再流血，但仍在黑暗中漂浮。"
        state.dying = False  # 已稳定，不再需要每回合掷豁免
        state.pending_system_hints = [
            hint for hint in state.pending_system_hints if not hint.startswith("[系统强制-濒死]")
        ]
    # P1-3: 死亡豁免结果强制内联
    await push_narrative_token(state, f"\n{desc}\n")
    return desc


async def _exec_suggest_choices(args: dict, state: GameSessionState) -> str:
    """加强建议格式：清洗 Markdown/编号/换行，强制 2-4 个纯文本短选项。"""
    import re
    raw = args.get("options", [])
    if isinstance(raw, str):
        raw = [raw]
    cleaned: list[str] = []
    for o in raw:
        s = str(o or "").strip()
        s = re.sub(r'^[-*•]\s*', '', s)
        s = re.sub(r'^\d+[\.\)、]\s*', '', s)
        s = s.replace('**', '').replace('`', '').replace('*', '')
        s = re.sub(r'\s+', ' ', s).strip(' "\'“”‘’')
        if len(s) > 25:
            s = s[:24].rstrip() + '…'
        if s and s not in cleaned:
            cleaned.append(s)
    if len(cleaned) < 2:
        return "[suggest_choices 格式错误] 请提供2-4个纯文本选项，每个不超过25字，不要使用Markdown、编号或换行。"
    cleaned = cleaned[:4]
    await push_event(state, "choices", {"options": cleaned})
    return f"建议: {', '.join(cleaned)}"
