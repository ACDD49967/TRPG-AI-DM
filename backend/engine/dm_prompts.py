"""DM 提示词：角色信息块 + 系统提示装配。

按职责拆成两个模块，这里只做再导出，既有 `from backend.engine.dm_prompts import ...` 全部照旧：
- `dm_character_info`：`build_character_info`（角色卡摘要，每轮都进 prompt）
- `dm_system_prompt`：`build_system_prompt` / `_mode_instructions` / `_extract_outline`
- 静态提示词常量仍在 `prompt_texts` / `prompt_system`，这里继续一并再导出
"""
from __future__ import annotations

import re

from typing import Any

from backend.config import settings

from backend.engine.game_systems import (
    build_stat_glossary, build_system_rule_block, get_system,
)
from backend.engine.session import GameSessionState

from backend.skills.prompts import (
    COC_DECISION_PROMPT, COC_SYSTEM_PROMPT, CUSTOM_DECISION_PROMPT, CUSTOM_SYSTEM_PROMPT,
    DND4E_DECISION_PROMPT, DND4E_SYSTEM_PROMPT,
)

from backend.engine.dm_character_info import (  # noqa: E402,F401
    _play_mode, build_character_info,
)
from backend.engine.dm_system_prompt import (  # noqa: E402,F401
    _extract_outline, _mode_instructions, build_system_prompt,
)

from backend.engine.prompt_texts import (  # noqa: E402,F401
    SYSTEM_PROMPT,
    DM_DECISION_PROMPT,
    COMPACT_DM_PROMPT,
    COMPACT_DM_DECISION_PROMPT,
    OPENING_PROMPT,
    COC_OPENING_PROMPT,
)
