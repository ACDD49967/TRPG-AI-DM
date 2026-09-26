"""世界状态 / 场景 / NPC 类工具处理器。

按数据域拆成三段，这里只做再导出，`tool_executor` 与 `dm_agent` 的 import 面不变：
- `world_state_tools`：update_world_state / prune_world_state
- `world_scene_tools`：update_scene / reveal_info
- `world_npc_tools`：get_character_state / adjust_resource / search_npcs / adjust_npc /
  promote_npc / add_character_note
"""
from backend.engine.world_state_tools import (  # noqa: F401
    _exec_prune_world_state, _exec_update_world_state,
)
from backend.engine.world_scene_tools import (  # noqa: F401
    _exec_reveal_info, _exec_update_scene,
)
from backend.engine.world_npc_tools import (  # noqa: F401
    _exec_adjust_npc, _exec_adjust_resource, _exec_character_note,
    _exec_get_character_state, _exec_promote_npc, _exec_search_npcs,
)
