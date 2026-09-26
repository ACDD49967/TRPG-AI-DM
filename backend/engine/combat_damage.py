"""伤害结算门面：范围豁免伤害 → `combat_save_damage`，敌人主动攻击 → `combat_enemy_attack`。

两个处理器原本都在本文件（363 行）。按结算类型拆开后，这里只留补丁契约与再导出，
`combat.py` / `dm_agent` / `tool_executor` 的 import 面不变。

**补丁契约**：

- 测试用 `patch.object(combat_damage.random, "randint")` 控制骰值。`patch.object` 改的是
  `random` 模块自身的属性，所以子模块里的 `random.randint` 同样会被替换；但本模块必须
  保留 `import random`，否则这个 patch 目标会消失（AttributeError）。
- `_roll_damage_simple` / `_persist_combat_damage` / `combat_attack_roll` 由子模块经各自的
  `_combat()` 在调用时取 `combat` 模块属性，不绑定函数对象，patch 依然生效。
"""
from __future__ import annotations

import random  # noqa: F401  仅作为测试 patch 的入口，本模块不再直接掷骰

from backend.engine.combat_enemy_attack import _exec_enemy_attack  # noqa: E402,F401
from backend.engine.combat_save_damage import _exec_save_damage  # noqa: E402,F401
