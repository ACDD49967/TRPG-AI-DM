"""主 DM 的模型配置：客户端、模型名、思考档位与规则系统。

从 `backend/engine/dm_runtime.py` 拆出；dm_runtime 再导出，
`dm_turn` 那句 `from backend.engine.dm_runtime import _client, _model, ...` 不用改。
"""
from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from backend.config import ensure_valid_api_key, settings
from backend.telemetry import InstrumentedAsyncOpenAI
from backend.engine.session import GameSessionState


def _safe_error_text(e: Exception) -> str:
    """返回适合回传给LLM的安全错误信息（不含堆栈/文件路径）。"""
    return f"{type(e).__name__}: {str(e)[:120]}"




def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y", "是", "真")
    return bool(value)




# ═══════════════════════════════════════════════════════════════
# LLM 调用
# ═══════════════════════════════════════════════════════════════

def _client(s: GameSessionState) -> AsyncOpenAI:
    raw = AsyncOpenAI(
        api_key=ensure_valid_api_key(s.api_key),
        base_url=getattr(s, 'base_url', None) or settings.LLM_BASE_URL,
    )
    telemetry = getattr(s, "telemetry", None)
    if telemetry is None:
        return raw
    return InstrumentedAsyncOpenAI(raw, telemetry, lambda: telemetry.current_phase)



def _model(s: GameSessionState) -> str:
    return s.model_name or settings.LLM_MODEL_NAME




def _play_mode(s: GameSessionState) -> str:
    """返回当前游玩模式：lite=精简模式，deep=深度模式。"""
    mode = (s.character_info or {}).get("play_mode", "deep")
    return mode if mode in ("lite", "deep") else "deep"




def _thinking_extra_body(s: GameSessionState, mode: str = "auto") -> dict:
    """把思维强度映射到 API 的 thinking 参数。

    - 快速任务（fixed/low 或玩家选 low）：直接禁用思考，提速且保证有 content；
    - 普通任务：不传，使用服务端默认行为；
    - 高强度创作：显式 enabled。
    """
    ts = getattr(s, "thinking_strength", "medium")
    if mode in ("fixed", "low") or ts == "low":
        return {"thinking": {"type": "disabled"}}
    if mode == "high" or ts == "high":
        return {"thinking": {"type": "enabled"}}
    return {}




def _thinking_params(s: GameSessionState) -> tuple[float, float]:
    """返回 (max_tokens倍率, 温度修正)，用于“思维强度”调节。"""
    ts = getattr(s, "thinking_strength", "medium")
    if ts == "low":
        return 0.6, -0.15
    if ts == "high":
        return 1.8, 0.08
    return 1.0, 0.0




def dm_think_mode(state: GameSessionState, module: str) -> str:
    """主 DM 的思考档位：规则/战斗/图谱/记忆固定快速，其余跟随玩家选择。

    修复前这里写的是「low → low，其余（含 medium）→ high」，
    玩家在开局页选「中」实际跑的是「高」，界面在骗人。
    """
    if module in ("rules", "combat", "graph", "memory"):
        return "fixed"
    strength = str(getattr(state, "thinking_strength", "high") or "high")
    if strength == "low":
        return "low"
    if strength == "medium":
        return "auto"
    return "high"




def _call_thinking_params(s: GameSessionState, mode: str = "auto") -> tuple[float, float]:
    """按任务类型限制思考/温度：
    - auto: 跟随玩家思维强度
    - low:  快速执行/规则/战斗，降低思考与温度
    - fixed: 固定内容/工具选择，最低思考与低温度
    - high: 创作/复杂叙事
    """
    if mode == "fixed":
        return 0.3, -0.25
    if mode == "low":
        return 0.5, -0.15
    if mode == "high":
        return 1.5, 0.05
    return _thinking_params(s)




def _game_system(s: GameSessionState) -> str:
    """返回当前规则系统：dnd5e / dnd4e / coc / custom。"""
    system = (s.character_info or {}).get("game_system", "dnd5e")
    return system if system in ("dnd5e", "dnd4e", "coc", "custom") else "dnd5e"
