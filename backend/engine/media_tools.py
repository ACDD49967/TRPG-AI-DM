"""内容库类工具门面：图鉴/地图/地点的检索、登记与卡片渲染。

原本都在本文件（325 行），按用途拆成三个模块：

- `media_tools_write`：update_bestiary_entry / update_city_entry /
  add_scenario_bestiary / add_scenario_map；
- `media_tools_search`：search_bestiary / search_locations / adjust_bestiary；
- `media_tools_cards`：get_bestiary_card / get_location_card 与卡片格式化。

`dm_agent` / `tool_executor` 仍按 `media_tools.<name>` 引用，这里全部再导出；
法术类工具（`spell_tools`）同样在此再导出，既有 import 面不变。
"""
from __future__ import annotations

from backend.engine.media_tools_cards import (  # noqa: E402,F401
    _exec_get_bestiary_card,
    _exec_get_location_card,
    _format_bestiary_card,
    _format_location_card,
)
from backend.engine.media_tools_search import (  # noqa: E402,F401
    _exec_adjust_bestiary,
    _exec_search_bestiary,
    _exec_search_locations,
)
from backend.engine.media_tools_write import (  # noqa: E402,F401
    _exec_add_scenario_bestiary,
    _exec_add_scenario_map,
    _exec_update_bestiary,
    _exec_update_city,
)

# 再导出：`dm_agent` / `tool_executor` 仍按 media_tools.<name> 引用这些法术工具
from backend.engine.spell_tools import (  # noqa: E402,F401
    _apply_time_stop,
    _exec_add_scenario_spell,
    _exec_cast_spell,
    _exec_forget_spell,
    _exec_learn_spell,
    _exec_search_spells,
    _search_spell_for_entity,
)
