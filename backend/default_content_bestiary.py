"""CLASSIC_BESTIARY（按规则系统拆分后的再导出门面）。"""

from backend.default_content_data.bestiary_dnd5e import BESTIARY_DND5E
from backend.default_content_data.bestiary_dnd4e import BESTIARY_DND4E
from backend.default_content_data.bestiary_coc import BESTIARY_COC

CLASSIC_BESTIARY = [*BESTIARY_DND5E, *BESTIARY_DND4E, *BESTIARY_COC]
