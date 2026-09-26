"""存档管理——用户记忆与游戏存档，租户隔离。

目录结构：
  saves/{username}/{save_id}.json

- auto 存档：同一 session 只保留最新一条
- manual 存档：每次手动保存都新增，不覆盖
"""

from __future__ import annotations

import json
import os
import uuid

from backend.logging_utils import get_logger
from backend.paths import safe_username
from datetime import datetime
from pathlib import Path

from backend.engine.session import GameSessionState

SAVE_ROOT = Path("saves")


def _user_dir(username: str) -> Path:
    return SAVE_ROOT / safe_username(username)


def _atomic_write_json(path: Path, payload: dict) -> None:
    """先写临时文件再原子替换，避免中断产生半截存档。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _save_path(username: str, save_id: str) -> Path:
    from backend.paths import validate_resource_id
    return _user_dir(username) / f"{validate_resource_id(save_id, '存档 ID')}.json"


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
            # 旧版本可能写入过响应缓存；回合行动不再读取它，避免旧缓存跳过结算。
            "response_cache": {},
            "opening_text": getattr(state, "opening_text", ""),
            "play_mode": state.character_info.get("play_mode", "deep"),
            "game_system": state.character_info.get("game_system", "dnd5e"),
            "scenario_id": state.character_info.get("scenario_id", ""),
            "custom_rules": state.character_info.get("custom_rules", ""),
            "extension_ids": state.character_info.get("extension_ids", []),
            "model_name": state.model_name,
            "base_url": state.base_url,
            # 安全：api_key 不落盘；读档时使用 .env / 前端当前配置或旧存档兼容值。
            "dynamic_state": _serialize_dynamic(state),
        },
    }
    path = _save_path(username, save_id)
    _atomic_write_json(path, payload)
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
        except Exception as e:
            get_logger("save_manager").warning("跳过损坏存档 %s: %s", p, e)
            continue
    saves.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return saves


def load_save(username: str, save_id: str) -> dict | None:
    path = _save_path(username, save_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        get_logger("save_manager").warning("读取存档失败 %s: %s", path, e)
        return None


def delete_save(username: str, save_id: str) -> bool:
    path = _save_path(username, save_id)
    if path.exists():
        path.unlink()
        return True
    return False


def rename_save(username: str, save_id: str, label: str) -> dict | None:
    """给存档改标签（存档文件名与 id 不变，只改展示名）。"""
    path = _save_path(username, save_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    # 存档标签存在顶层 "label"（create_save/list_saves 都读这里）
    data["label"] = str(label or "存档")[:60]
    _atomic_write_json(path, data)
    return {"id": save_id, "label": data["label"], "created_at": data.get("created_at", "")}


def auto_save_if_needed(state: GameSessionState):
    """每轮自动存档。"""
    try:
        create_save(state, label="自动存档", auto=True)
    except Exception as e:
        print(f"[SaveManager] 自动存档失败: {e}")


# 拆出的序列化 / 恢复在这里再导出，既有调用方（router、测试）不用改
from backend.save_serialize import (  # noqa: E402,F401
    _serialize_dynamic, _serialize_memory, _serialize_world_state,
)
from backend.save_restore import restore_state_from_save  # noqa: E402,F401
