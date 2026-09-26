"""场景与情报揭示工具：update_scene、reveal_info。

从 `backend/engine/world_tools.py` 拆出。
"""
from __future__ import annotations

from backend.engine.session import GameSessionState, push_event


async def _exec_reveal_info(args: dict, state: GameSessionState) -> str:
    ws = getattr(state, 'world_state', None)
    if ws is None: return "无世界状态"
    target_type = args.get("target_type",""); target_name = args.get("target_name",""); field = args.get("field",""); trigger = args.get("trigger","")
    if target_type == "npc_field":
        npc = ws.get_npc(target_name)
        if npc and not npc.discovered:
            npc.discovered = True
        if ws.reveal_npc_field(target_name, field, "visible"):
            ws.save()
            await push_event(state, "game_event", {"type":"info_revealed","description":f"对{target_name}有了新的认识"})
            return f"✅ {target_name}.{field}揭示 ({trigger})"
        return f"⚠ NPC {target_name} 不存在"
    elif target_type == "npc_all":
        npc = ws.get_npc(target_name)
        if npc:
            npc.discovered = True
            npc.visibility = type(npc.visibility).full_reveal()
            ws.save()
            await push_event(state, "game_event", {"type":"info_revealed","description":f"{target_name}的真实面目完全揭露！"})
            return f"✅ {target_name}全部揭示"
    elif target_type == "flag":
        for f in ws.plot_flags:
            if f.key != target_name:
                continue
            f.visible = True
            ws.save()
            await push_event(state, "journal_update", ws.to_player_journal())
            return f"✅ 旗标公开: {target_name}"
        return f"⚠ 旗标 {target_name} 不存在"
    elif target_type == "location":
        for l in ws.locations:
            if l.name != target_name:
                continue
            if field == "secret" and l.secrets:
                l.secret_revealed = True
                ws.save()
                await push_event(state, "journal_update", ws.to_player_journal())
                return f"✅ {target_name}秘密揭示"
            l.discovered = True
            ws.save()
            return f"✅ {target_name}发现"
    elif target_type == "secret":
        if ws.reveal_npc_field(target_name, "secret", "visible"): return f"✅ {target_name}秘密揭示"
    return f"未知揭示类型: {target_type}"


async def _exec_update_scene(args: dict, state: GameSessionState) -> str:
    ws = getattr(state, 'world_state', None)
    if ws is None: return "无世界状态"
    # 默认"传空即忽略"，避免模型只写部分字段时把已有内容抹掉；但前端编辑面板要能清空字段
    # （"允许对所有内容增删改查"），所以支持显式 clear=["weather"] 列出要清空的字段。
    # light / light_source 一律可清空：空值 = 未设置 = 退回按时间推断。
    clearable = {"light", "light_source"} | {str(k) for k in (args.get("clear") or [])}
    updates = {k: args[k] for k in ["current_location","current_time","weather","atmosphere",
                                    "visible_npcs_here","light","light_source"]
               if k in args and (args[k] or k in clearable)}
    if updates:
        if "current_time" in updates:
            # 先把"旧时间"固化成权威时钟，再让 DM 改写叙述文字（否则差值算不出来）
            from backend.engine import time_rules
            time_rules.ensure_clock(state)
        # update_scene 内部完成字段清洗与地点建档，这里不再重复处理
        ws.update_scene(**updates)
        await push_event(state, "scene_update", {
            "location": ws.scene.current_location, "time": ws.scene.current_time or f"第{ws.scene.day_count}天",
            "weather": ws.scene.weather, "atmosphere": ws.scene.atmosphere, "npcs_here": ws.scene.visible_npcs_here,
            "light": ws.scene.light, "light_source": ws.scene.light_source,
        })
        try:
            await push_event(state, "journal_update", ws.to_player_journal())
        except Exception:
            pass
    text = "场景已更新"
    # 时间一致性：DM 常用 current_time 叙述时间；后端据此校准权威时钟与补给
    if "current_time" in updates:
        from backend.engine import time_rules
        synced = await time_rules.sync_scene_time(state, str(updates["current_time"]))
        if synced:
            text += f"\n{synced}"
    return text
