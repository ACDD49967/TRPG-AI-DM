"""COMMON_CITIES（按规则系统拆分后的再导出门面）。"""

from backend.default_content_data.cities_dnd5e import CITIES_DND5E
from backend.default_content_data.cities_dnd4e import CITIES_DND4E
from backend.default_content_data.cities_coc import CITIES_COC

COMMON_CITIES = [*CITIES_DND5E, *CITIES_DND4E, *CITIES_COC]
