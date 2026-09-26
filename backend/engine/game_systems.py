"""规则系统门面：经验/等级、5e/4e/COC 派生值、起始装备与系统元信息。

实现已按规则域拆到 rules_progress / rules_5e / rules_4e / rules_coc /
starter_kits / rules_system；这里再导出，既有 import 不变。
"""

from backend.engine.rules_progress import (  # noqa: E402
    DND4_XP_THRESHOLDS,
    DND5_STARTING_GOLD,
    DND5_XP_THRESHOLDS,
    get_level_from_xp,
    get_starting_gold,
    get_xp_progress,
    get_xp_table,
)
from backend.engine.rules_5e import (  # noqa: E402
    DND5_ASI_BY_CLASS,
    DND5_ASI_DEFAULT,
    DND5_CHANNEL_DIVINITY,
    DND5_CLASS_HD,
    DND5_CLASS_SAVES,
    DND5_RAGE_USES,
    _FULL_CASTER_SLOTS,
    _HALF_CASTER_SLOTS,
    _WARLOCK_PACT_LEVEL,
    _WARLOCK_SLOTS,
    get_dnd5_asi_levels,
    get_dnd5_class_resources,
    get_dnd5_derived,
    get_dnd5_proficiency_bonus,
    get_dnd5_saves,
    get_dnd5_spell_slots,
    get_passive_perception,
)
from backend.engine.rules_4e import (  # noqa: E402
    DND4_CLASS_HP,
    DND4_CLASS_SURGES,
    DND4_DEFENSE_BONUS,
    get_dnd4_defenses,
    get_dnd4_derived,
)
from backend.engine.rules_coc import (  # noqa: E402
    get_coc_derived,
    roll_coc_characteristics,
    roll_coc_luck,
)
from backend.engine.starter_kits import (  # noqa: E402
    COC_STARTER_KIT,
    DND5_STARTER_KITS,
    GENERIC_STARTER_KIT,
    get_starter_equipment,
)
from backend.engine.rules_system import (  # noqa: E402
    SYSTEM_TYPES,
    build_stat_glossary,
    build_system_rule_block,
    detect_game_system,
    get_style_directive,
    get_system,
)
