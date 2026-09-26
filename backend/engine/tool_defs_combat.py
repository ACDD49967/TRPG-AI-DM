"""战斗与回合工具：骰子、战斗结算、伤害、死亡豁免、休息与时间推进。

从 `backend/engine/tools.py` 拆出；那边只留 `DM_TOOLS` 装配与再导出。
`tests/test_module_layout.py` 的注册表一致性测试会核对 schema 与处理器一一对应。
"""
from backend.engine.tool_schemas import _tool
from backend.engine.combat_advantage import ENEMY_ATTACK_ADVANTAGE_SCHEMA, PLAYER_ATTACK_ADVANTAGE_SCHEMA
from backend.engine.recharge_rules import RECHARGE_ABILITY_SCHEMA, SAVE_DAMAGE_RECHARGE_SCHEMA


DICE_ROLL_TOOL = _tool("dice_roll",
    "D20技能检定。玩家有风险的行为时调用。modifier=对应属性调整值。DC:5极简10简15中20难25极难30传奇。"
    "自定义规则系统若规定了别的判定骰，用 dice 声明骰式（如 \"2d10\"/\"3d6\"），后端按 骰和+modifier vs dc 判定；"
    "5e/4e/COC 使用各自规范骰（d20/d100），不要传 dice。",
    {"skill_name": {"type":"string","description":"检定名"},
     "dc": {"type":"integer","description":"难度等级"},
     "modifier": {"type":"integer","description":"属性调整值，默认0"},
     "dice": {"type":"string","description":"自定义骰式（仅自定义规则系统），如 2d10、3d6；留空按系统默认"},
     "advantage": {"type":"string","enum":["normal","advantage","disadvantage"]}},
    ["skill_name","dc"])

COMBAT_ROUND_TOOL = _tool("combat_round",
    "【必须调用】结算一轮战斗。只传 player_action 与 enemy_name 即可：工具会自动从角色卡计算玩家攻击/伤害，并从 NPC 卡或生物图鉴卡取敌人 AC/HP/攻击，结算后自动把伤害写回该实体的 HP。若实体尚未入册，先调 update_world_state(add_npc) 或 add_scenario_bestiary。",
    {"player_action": {"type":"string", "description": "玩家本轮动作"},
     "player_attack_modifier": {"type":"integer", "description": "可选，缺省自动按角色卡属性+熟练计算"},
     "player_damage_dice": {"type":"string", "description": "可选，缺省自动取背包武器伤害"},
     "enemy_name": {"type":"string", "description": "必须与NPC卡/图鉴卡名称一致（本轮玩家实际攻击目标）"},
     "enemy_names": {"type":"array", "items":{"type":"string"}, "description": "可选，当前战斗中所有敌人名单；用于前端展示各敌人HP，玩家本轮实际攻击目标仍是 enemy_name"},
     "enemy_ac": {"type":"integer", "description": "可选，缺省取实体卡AC"},
     "enemy_attack_modifier": {"type":"integer", "description": "可选，缺省按实体卡属性计算"},
     "enemy_damage_dice": {"type":"string", "description": "可选，缺省从实体卡特性/动作解析"},
     "enemy_hp": {"type":"integer", "description": "可选，缺省取实体卡当前HP"},
     "enemy_can_act": {"type":"boolean", "description": "敌人本轮能否主动行动/反击。被绑、失去意识、跪地、无力、濒死等应为 false，避免待宰羔羊反杀"},
     "action_source": {"type":"string", "description": "可选。本次是合法额外行动时声明来源：multiattack(多段攻击)/extra_attack/two_weapon/bonus_action/action_surge/haste/legendary_action/lair_action/reaction/opportunity_attack/time_stop/action_point(D&D4e花1点行动点)。省略即为该单位本回合的主行动，每回合只能一次；不得为了重掷失败结果而声明。"},
     "attacks": {"type":"integer", "description": "可选，本次声明来源包含的攻击次数（如 multiattack 3 段、legendary_action 2 次），缺省按来源默认配额"},
     "power_attack": {"type":"boolean", "description": "可选：声明强力攻击（命中 -5、伤害 +10）。只有拥有「巨武器大师」（近战）或「神射手」（远程）特长时才会生效，否则被拒绝"},
     **PLAYER_ATTACK_ADVANTAGE_SCHEMA,
     "enemy_condition": {"type":"string", "description": "可选，敌人当前状态描述，用于判断能否行动"}},
    ["player_action", "enemy_name"])

ENEMY_ATTACK_TOOL = _tool("enemy_attack",
    "【敌人回合】在敌人自己的回合/剧情中主动攻击玩家。不要把它当作玩家攻击后的自动反伤；玩家攻击回合只调用 combat_round。",
    {"enemy_name": {"type":"string", "description": "敌人/NPC名称"},
     "enemy_attack_modifier": {"type":"integer", "description": "可选，缺省取实体卡"},
     "enemy_damage_dice": {"type":"string", "description": "可选，缺省从实体卡解析"},
     "player_ac": {"type":"integer", "description": "可选，缺省取玩家角色卡AC"},
     "damage_type": {"type":"string", "description": "可选。这次攻击的伤害类型（火焰/冷冻/闪电/强酸/毒素/雷鸣/光耀/黯蚀/心灵/力场/钝击/穿刺/挥砍）。填了才会套用玩家侧抗性/免疫/易伤；爪牙撕咬/长剑劈砍等请填 钝击/穿刺/挥砍"},
     "action_source": {"type":"string", "description": "可选。传奇动作/传奇抗性后的反击/加速术/借机攻击/时间暂停等额外行动需声明来源（legendary_action/reaction/opportunity_attack/haste/time_stop）；省略即该敌人本回合的主行动，每回合只能一次"},
     "enemy_action": {"type":"string", "description": "可选。敌人本次的动作/能力名（如 Fire Breath / 吐息），用于伤害类型、充能与优势推断"},
     **RECHARGE_ABILITY_SCHEMA,
     **ENEMY_ATTACK_ADVANTAGE_SCHEMA,
     "attacks": {"type":"integer", "description": "可选，该来源包含的攻击次数，缺省按来源默认配额"}},
    ["enemy_name"])

SAVE_DAMAGE_TOOL = _tool("save_damage",
    "【范围/豁免伤害】对若干目标各掷一次豁免（d20 + 该生物豁免加值 vs DC）：失败吃全额，成功默认减半"
    "（法术写“豁免成功不受伤害”时传 half_on_success=false）。工具会自动套用伤害类型的抗性/免疫/易伤，"
    "并把伤害写回每个目标的 HP，阵亡会自动结算经验。玩家施放范围法术（火球/燃烧之手/龙息等）、"
    "踩中陷阱或其它“过豁免”的效果时使用，不要手改 HP。",
    {"targets": {"type":"array","items":{"type":"string"},
                 "description":"受影响目标名列表（需与 NPC 卡/图鉴卡名称一致；玩家可写「你」或角色名，会走玩家侧豁免与抗性管线）"},
     "dc": {"type":"integer","description":"豁免 DC"},
     "ability": {"type":"string","enum":["str","dex","con","int","wis","cha"],
                 "description":"豁免属性，默认 dex"},
     "damage": {"type":"string","description":"伤害骰或固定值，如 8d6 / 22"},
     "damage_type": {"type":"string",
                     "description":"伤害类型：火焰/冷冻/闪电/强酸/毒素/雷鸣/光耀/黯蚀/心灵/力场/钝击/穿刺/挥砍"},
     "magic": {"type":"boolean", "description": "可选：本次效果是法术/魔法效果（如魔法飞弹、火球、魅惑）。带 Magic Resistance/魔法抗性的目标自动获得豁免优势"},
     "legendary_resistance": {"type":"boolean", "description": "可选：让带 Legendary Resistance/传奇抗性的目标消耗一次次数，把失败豁免改为成功"},
     **SAVE_DAMAGE_RECHARGE_SCHEMA,
     "half_on_success": {"type":"boolean","description":"豁免成功是否减半，默认 true"},
     "reason": {"type":"string","description":"法术/效果名称，用于日志"}},
    ["targets","dc","damage"])

SET_TACTICAL_STATE_TOOL = _tool("set_tactical_state",
    "【战场态势】登记距离档位与掩体，后端据此自动套用机械修正（掩体加 AC 与敏捷豁免、"
    "近战够不到要先接近、脱离缠斗会引发借机攻击）。战斗开始时登记一次即可，"
    "局势变化（有人躲进掩体/后撤/接近）再更新。band: engaged(缠斗)/near(约30尺)/far(约120尺)/out(脱离)；"
    "cover: none/half(+2)/three_quarters(+5)/full(无法被直接攻击)。",
    {"combatant": {"type":"string", "description":"要登记的单位名（玩家可写「你」或角色名）"},
     "band": {"type":"string", "enum":["engaged","near","far","out"],
              "description":"距离档位；省略表示不改动"},
     "cover": {"type":"string", "enum":["none","half","three_quarters","full"],
               "description":"掩体等级；省略表示不改动"},
     "note": {"type":"string", "description":"可选，简述位置（如“躲在货车残骸后”）"},
     "placements": {"type":"array", "description":"可选，一次登记多个单位",
                    "items":{"type":"object","properties":{
                        "combatant":{"type":"string"},"band":{"type":"string"},
                        "cover":{"type":"string"},"note":{"type":"string"}}}}},
    ["combatant"])

DEATH_SAVE_TOOL = _tool("death_saving_throw",
    "角色HP≤0时每回合必须掷死亡豁免。d20≥10=成功, 自然20=恢复1HP, 自然1=2次失败。累计3成功=稳定, 3失败=死亡。",
    {}, [])

REST_TOOL = _tool("take_rest",
    "短休(5e: 消耗生命骰恢复HP，并恢复气/引导神力/荒野形态/回气/动作如潮/奥术回想/契约法术位；"
    "4e: 消耗回复力，每次回复 surge_value 点 HP)或长休(HP/MP/法术位/职业资源/回复力全部恢复,行动点重置为1)。",
    {"rest_type": {"type":"string","enum":["short","long"]},
     "hit_dice": {"type":"integer","description":"5e 短休消耗的生命骰数量（默认最多 2，受剩余数限制）"}},
    ["rest_type"])

ADVANCE_TIME_TOOL = _tool("advance_time",
    "【时间推进】旅行、搜索、守夜、等待、休息的时间成本由后端记账：推进后会自动更新日数与时刻，"
    "跨天时消耗 1 份口粮 + 1 份饮水，缺补给则力竭 +1（5e：1 级检定劣势 / 3 级攻防劣势 / 6 级死亡）；"
    "夜间行动传 light_source（火把/提灯）会按 1 支/小时消耗。短休/长休用 take_rest，不必手填小时数。",
    {"minutes": {"type":"integer", "description":"推进的分钟数（与 hours/days 可叠加）"},
     "hours": {"type":"integer", "description":"推进的小时数，如赶路 4 小时"},
     "days": {"type":"integer", "description":"推进的天数，如长途旅行"},
     "reason": {"type":"string", "description":"推进原因（赶路/搜索/守夜…），用于日志"},
     "light_source": {"type":"string", "description":"可选：本次照明手段（火把/提灯），后端会扣数量"},
     "pace": {"type":"string", "enum":["fast","normal","slow"],
              "description":"可选。本次是旅行时声明节奏：fast 被动察觉 −5、slow 可隐蔽行进；每天超过 8 小时后每多 1 小时掷体质豁免（DC 10+超出小时数），失败力竭 +1"}},
    [])

EQUIP_ITEM_TOOL = _tool("equip_item",
    "装备或卸下背包中的一件物品，并实时影响角色数值（如护甲AC）。玩家或DM均可使用。",
    {"name": {"type": "string", "description": "物品名称"},
     "equipped": {"type": "boolean", "description": "true=装备, false=卸下"}},
    ["name", "equipped"])
