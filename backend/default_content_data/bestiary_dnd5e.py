"""内置bestiary数据：dnd5e 规则系统。

22 个怪物按**原条目顺序**拆到 part1-4（每片 5-6 条、约 200 行），这里只做拼接：
- part1: 地精、兽人、骷髅、僵尸、红龙雏龙、眼魔
- part2: 狗头人、巨魔、幽影、狮鹫、狼、巨鼠
- part3: 巨蜘蛛、强盗、食人魔、狼人、吸血鬼衍体
- part4: 幽灵、熊地精、鹰马、火元素、石魔像
拼接结果是同一个 `BESTIARY_DND5E`（内容与顺序都不变），调用方不用改。
"""
from backend.default_content_data.bestiary_dnd5e_part1 import BESTIARY_DND5E_PART1
from backend.default_content_data.bestiary_dnd5e_part2 import BESTIARY_DND5E_PART2
from backend.default_content_data.bestiary_dnd5e_part3 import BESTIARY_DND5E_PART3
from backend.default_content_data.bestiary_dnd5e_part4 import BESTIARY_DND5E_PART4

BESTIARY_DND5E = [
    *BESTIARY_DND5E_PART1,
    *BESTIARY_DND5E_PART2,
    *BESTIARY_DND5E_PART3,
    *BESTIARY_DND5E_PART4,
]
