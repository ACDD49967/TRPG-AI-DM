"""存档管理——用户记忆与游戏存档，租户隔离。

目录结构：
  saves/{username}/{save_id}.json

- auto 存档：同一 session 只保留最新一条
- manual 存档：每次手动保存都新增，不覆盖
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.engine.session import GameSessionState
from backend.engine.world_state import WorldState

SAVE_ROOT = Path("saves")


def _user_dir(username: str) -> Path:
    safe = "".join(c for c in (username or "default") if c.isalnum() or c in "._-") or "default"
    return SAVE_ROOT / safe


def _save_path(username: str, save_id: str) -> Path:
    return _user_dir(username) / f"{save_id}.json"


def _serialize_memory(state: GameSessionState) -> dict:
    mem = state.memory
    return {
        "turns": [
            {"player_input": t.player_input, "dm_response": t.dm_response, "events": t.events}
            for t in mem.turns
        ],
        "summary": mem.summary,
        "world_facts": mem.world_facts,
        "max_active_turns": mem.max_active_turns,
        "summary_trigger": mem.summary_trigger,
    }


def _serialize_world_state(state: GameSessionState) -> dict | None:
    ws = getattr(state, "world_state", None)
    if ws is None:
        return None
    # 临时写入到独立路径，读取其 JSON
    temp_path = Path("world_states") / f"{state.session_id}.json"
    if temp_path.exists():
        try:
            return json.loads(temp_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    # 如果内存中的 world_state 未落盘，则直接使用其 save 方法写入再读取
    try:
        ws.save()
        if temp_path.exists():
            return json.loads(temp_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def create_save(state: GameSessionState, label: str = "手动存档", auto: bool = False) -> dict:
    """创建存档。auto=True 时同一 session 覆盖旧 auto 存档。"""
    username = state.username or "default"
    user_dir = _user_dir(username)
    user_dir.mkdir(parents=True, exist_ok=True)

    if auto:
        # 查找该 session 的旧 auto 存档，覆盖之
        old_auto = None
        for p in user_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if data.get("auto") and data.get("session_id") == state.session_id:
                    old_auto = p
                    break
            except Exception:
                continue
        save_id = old_auto.stem if old_auto else uuid.uuid4().hex[:16]
    else:
        save_id = uuid.uuid4().hex[:16]

    payload = {
        "id": save_id,
        "username": username,
        "label": label,
        "auto": auto,
        "session_id": state.session_id,
        "created_at": datetime.now().isoformat(),
        "session": {
            "character_id": state.character_id,
            "character_name": state.character_name,
            "character_info": state.character_info,
            "memory": _serialize_memory(state),
            "world_state": _serialize_world_state(state),
            "response_cache": dict(state.response_cache),
            "play_mode": state.character_info.get("play_mode", "deep"),
            "game_system": state.character_info.get("game_system", "dnd5e"),
            "scenario_id": state.character_info.get("scenario_id", ""),
            "custom_rules": state.character_info.get("custom_rules", ""),
            "extension_ids": state.character_info.get("extension_ids", []),
            "api_key": state.api_key,
            "model_name": state.model_name,
            "base_url": state.base_url,
        },
    }
    path = _save_path(username, save_id)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def list_saves(username: str) -> list[dict]:
    user_dir = _user_dir(username)
    if not user_dir.exists():
        return []
    saves = []
    for p in user_dir.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            saves.append({
                "id": data.get("id", p.stem),
                "label": data.get("label", "存档"),
                "auto": data.get("auto", False),
                "session_id": data.get("session_id", ""),
                "created_at": data.get("created_at", ""),
                "character_name": data.get("session", {}).get("character_name", ""),
                "game_system": data.get("session", {}).get("game_system", ""),
            })
        except Exception:
            continue
    saves.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return saves


def load_save(username: str, save_id: str) -> dict | None:
    path = _save_path(username, save_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def delete_save(username: str, save_id: str) -> bool:
    path = _save_path(username, save_id)
    if path.exists():
        path.unlink()
        return True
    return False


def restore_state_from_save(save_data: dict) -> tuple[GameSessionState, dict]:
    """从存档数据恢复一个内存会话（不写数据库）。"""
    session = save_data.get("session", {})
    session_id = uuid.uuid4().hex[:16]
    character_id = session.get("character_id", uuid.uuid4().hex[:12])
    character_name = session.get("character_name", "冒险者")
    character_info = dict(session.get("character_info", {}))
    character_info["play_mode"] = session.get("play_mode", "deep")
    character_info["game_system"] = session.get("game_system", "dnd5e")
    character_info["scenario_id"] = session.get("scenario_id", "")
    character_info["custom_rules"] = session.get("custom_rules", "")
    character_info["extension_ids"] = session.get("extension_ids", [])

    from backend.engine.session import GameSessionState
    from backend.engine.memory import MemorySystem, DialogueTurn

    state = GameSessionState(
        session_id=session_id,
        character_id=character_id,
        character_name=character_name,
        character_info=character_info,
        username=save_data.get("username", "default"),
    )
    state.response_cache = dict(session.get("response_cache", {}))
    state.api_key = session.get("api_key")
    state.model_name = session.get("model_name")
    state.base_url = session.get("base_url")

    mem = MemorySystem()
    mem_data = session.get("memory", {})
    mem.turns = [DialogueTurn(**t) for t in mem_data.get("turns", [])]
    mem.summary = mem_data.get("summary", "")
    mem.world_facts = list(mem_data.get("world_facts", []))
    mem.max_active_turns = mem_data.get("max_active_turns", 10)
    mem.summary_trigger = mem_data.get("summary_trigger", mem.max_active_turns + 1)
    state.memory = mem

    ws_data = session.get("world_state")
    if ws_data:
        # 写入新 session 的 world_state 文件
        from backend.engine.world_state import WorldState
        ws_dir = Path("world_states")
        ws_dir.mkdir(exist_ok=True)
        (ws_dir / f"{session_id}.json").write_text(
            json.dumps(ws_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        state.world_state = WorldState.load(session_id)

    return state, session_id


def auto_save_if_needed(state: GameSessionState):
    """每轮自动存档。"""
    try:
        create_save(state, label="自动存档", auto=True)
    except Exception as e:
        print(f"[SaveManager] 自动存档失败: {e}")
