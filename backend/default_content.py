"""内置内容数据（门面）。

数据表本身已按类型拆到 `default_content_bestiary` / `default_content_cities`；
这里继续再导出，保证 `from backend.default_content import CLASSIC_BESTIARY` 等既有 import 不变。
"""
from backend.default_content_bestiary import CLASSIC_BESTIARY  # noqa: F401
from backend.default_content_cities import COMMON_CITIES  # noqa: F401

__all__ = ["CLASSIC_BESTIARY", "COMMON_CITIES"]
