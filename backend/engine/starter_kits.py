"""起始装备：5e / COC / 通用套装与取装函数。

从 backend.engine.game_systems 拆出。
"""
from __future__ import annotations

import random
import re
from typing import Any



DND5_STARTER_KITS = {
    "战士": [{"name": "长剑", "type": "weapon", "quantity": 1, "description": "1d8 挥砍，通用"},
             {"name": "盾牌", "type": "armor", "quantity": 1, "description": "AC +2"},
             {"name": "鳞甲", "type": "armor", "quantity": 1, "description": "AC 14 + 敏捷调整（上限 2）"},
             {"name": "冒险者套件", "type": "kit", "quantity": 1, "description": "背包、睡袋、火绒盒、10 支火把、10 日口粮、水袋、50 尺麻绳"}],
    "法师": [{"name": "法杖", "type": "focus", "quantity": 1, "description": "奥术法器"},
             {"name": "法术书", "type": "gear", "quantity": 1, "description": "记录已准备法术"},
             {"name": "冒险者套件", "type": "kit", "quantity": 1, "description": "背包、睡袋、火绒盒、10 支火把、10 日口粮、水袋、50 尺麻绳"}],
    "游荡者": [{"name": "短剑", "type": "weapon", "quantity": 1, "description": "1d6 穿刺，灵巧，轻型"},
               {"name": "短弓", "type": "weapon", "quantity": 1, "description": "1d6 穿刺，弹药 20"},
               {"name": "皮甲", "type": "armor", "quantity": 1, "description": "AC 11 + 敏捷调整"},
               {"name": "盗贼工具", "type": "tool", "quantity": 1, "description": "开锁与解除陷阱检定可用"}],
    "牧师": [{"name": "硬头锤", "type": "weapon", "quantity": 1, "description": "1d6 钝击"},
             {"name": "盾牌", "type": "armor", "quantity": 1, "description": "AC +2"},
             {"name": "鳞甲", "type": "armor", "quantity": 1, "description": "AC 14 + 敏捷调整（上限 2）"},
             {"name": "圣徽", "type": "focus", "quantity": 1, "description": "神术法器"},
             {"name": "冒险者套件", "type": "kit", "quantity": 1, "description": "背包、睡袋、火绒盒、10 支火把、10 日口粮、水袋、50 尺麻绳"}],
    "游侠": [{"name": "长剑", "type": "weapon", "quantity": 1, "description": "1d8 挥砍，通用"},
             {"name": "长弓", "type": "weapon", "quantity": 1, "description": "1d8 穿刺，弹药 20"},
             {"name": "皮甲", "type": "armor", "quantity": 1, "description": "AC 11 + 敏捷调整"},
             {"name": "探险套件", "type": "kit", "quantity": 1, "description": "背包、铺盖、炊具、火绒盒、10 支火把、10 日口粮、水袋、50 尺麻绳"}],
    "吟游诗人": [{"name": "细剑", "type": "weapon", "quantity": 1, "description": "1d8 穿刺，灵巧"},
                 {"name": "鲁特琴", "type": "focus", "quantity": 1, "description": "乐器法器"},
                 {"name": "皮甲", "type": "armor", "quantity": 1, "description": "AC 11 + 敏捷调整"},
                 {"name": "冒险者套件", "type": "kit", "quantity": 1, "description": "背包、睡袋、火绒盒、10 支火把、10 日口粮、水袋、50 尺麻绳"}],
    "武僧": [{"name": "短棍", "type": "weapon", "quantity": 1, "description": "1d6 钝击，武僧武器"},
             {"name": "飞镖", "type": "weapon", "quantity": 10, "description": "1d4 穿刺，灵巧，投掷（20/60）"},
             {"name": "探险套件", "type": "kit", "quantity": 1, "description": "背包、铺盖、炊具、火绒盒、10 支火把、10 日口粮、水袋、50 尺麻绳"}],
    "德鲁伊": [{"name": "短弯刀", "type": "weapon", "quantity": 1, "description": "1d6 挥砍，灵巧，轻型"},
               {"name": "木盾", "type": "armor", "quantity": 1, "description": "AC +2"},
               {"name": "皮甲", "type": "armor", "quantity": 1, "description": "AC 11 + 敏捷调整"},
               {"name": "德鲁伊法器", "type": "focus", "quantity": 1, "description": "槲寄生枝"},
               {"name": "探险套件", "type": "kit", "quantity": 1, "description": "背包、铺盖、炊具、火绒盒、10 支火把、10 日口粮、水袋、50 尺麻绳"}],
    "圣武士": [{"name": "长剑", "type": "weapon", "quantity": 1, "description": "1d8 挥砍，通用"},
               {"name": "盾牌", "type": "armor", "quantity": 1, "description": "AC +2"},
               {"name": "链甲", "type": "armor", "quantity": 1, "description": "AC 16，力量 13 方可穿着"},
               {"name": "圣徽", "type": "focus", "quantity": 1, "description": "神术法器"},
               {"name": "冒险者套件", "type": "kit", "quantity": 1, "description": "背包、睡袋、火绒盒、10 支火把、10 日口粮、水袋、50 尺麻绳"}],
    "术士": [{"name": "轻弩", "type": "weapon", "quantity": 1, "description": "1d8 穿刺，弹药 20"},
             {"name": "奥术法器", "type": "focus", "quantity": 1, "description": "龙晶/法珠任选"},
             {"name": "冒险者套件", "type": "kit", "quantity": 1, "description": "背包、睡袋、火绒盒、10 支火把、10 日口粮、水袋、50 尺麻绳"}],
    "野蛮人": [{"name": "巨斧", "type": "weapon", "quantity": 1, "description": "1d12 挥砍，重型，双手"},
               {"name": "手斧", "type": "weapon", "quantity": 2, "description": "1d6 挥砍，轻型，投掷（20/60）"},
               {"name": "探险套件", "type": "kit", "quantity": 1, "description": "背包、铺盖、炊具、火绒盒、10 支火把、10 日口粮、水袋、50 尺麻绳"}],
    "邪术师": [{"name": "轻弩", "type": "weapon", "quantity": 1, "description": "1d8 穿刺，弹药 20"},
               {"name": "奥术法器", "type": "focus", "quantity": 1, "description": "秘术法器"},
               {"name": "皮甲", "type": "armor", "quantity": 1, "description": "AC 11 + 敏捷调整"},
               {"name": "冒险者套件", "type": "kit", "quantity": 1, "description": "背包、睡袋、火绒盒、10 支火把、10 日口粮、水袋、50 尺麻绳"}],
}

COC_STARTER_KIT = [
    {"name": "笔记本", "type": "gear", "quantity": 1, "description": "记录线索与见闻"},
    {"name": "钢笔", "type": "gear", "quantity": 1, "description": "书写工具"},
    {"name": "手电筒", "type": "gear", "quantity": 1, "description": "照明，电池驱动"},
    {"name": "小刀", "type": "weapon", "quantity": 1, "description": "1d4 穿刺，格斗（小刀）"},
    {"name": "火柴", "type": "gear", "quantity": 1, "description": "一盒火柴"},
    {"name": "现金", "type": "gear", "quantity": 1, "description": "相当于角色年收入的零用现金"},
]

GENERIC_STARTER_KIT = [
    {"name": "小刀", "type": "weapon", "quantity": 1, "description": "1d4 穿刺"},
    {"name": "背包", "type": "gear", "quantity": 1, "description": "容纳随身物品"},
    {"name": "绳索（50尺）", "type": "gear", "quantity": 1, "description": "攀爬与捆绑"},
    {"name": "火把", "type": "gear", "quantity": 3, "description": "照明 1 小时"},
    {"name": "口粮（1日）", "type": "gear", "quantity": 3, "description": "干粮与水"},
]



def get_starter_equipment(game_system: str, char_class: str) -> list[dict]:
    """按规则系统与职业返回初始白板装备（仅用于空背包开局）。"""
    if game_system == "coc":
        return [dict(item) for item in COC_STARTER_KIT]
    if game_system == "custom":
        return [dict(item) for item in GENERIC_STARTER_KIT]
    return [dict(item) for item in DND5_STARTER_KITS.get(char_class, GENERIC_STARTER_KIT)]
