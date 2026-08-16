"""D&D 5e 特长系统——玩家每2级选择一项特长"""

FEATS_LIST = [
    {
        "name": "警觉", "id": "alert",
        "desc": "你的感官异常敏锐。先攻+5，你不会被突袭，隐藏的敌人对你没有优势。",
        "effect": {"initiative_bonus": 5, "cannot_be_surprised": True},
    },
    {
        "name": "运动员", "id": "athlete",
        "desc": "你的身体能力超越常人。力量或敏捷+1（上限20），倒地后只需5尺移动即可起立，攀爬不消耗额外移动。",
        "effect": {"attr_choice": ["str", "dex"], "attr_bonus": 1, "climb_no_penalty": True, "stand_up_5ft": True},
    },
    {
        "name": "强弩专家", "id": "crossbow_expert",
        "desc": "你对弩的使用出神入化。近战中使用弩不会获得劣势，你每回合可以用附赠动作进行一次手弩攻击。",
        "effect": {"crossbow_no_disadvantage_melee": True, "hand_crossbow_bonus_action": True},
    },
    {
        "name": "双持客", "id": "dual_wielder",
        "desc": "你掌握了双武器战斗的精髓。双持时AC+1，可以使用非轻型武器双持，拔出或收起双武器仅需一个物件交互。",
        "effect": {"ac_bonus_dual_wield": 1, "dual_wield_non_light": True},
    },
    {
        "name": "地城探索者", "id": "dungeon_delver",
        "desc": "你对地城的危险了如指掌。侦测密门和陷阱时感知检定优势，陷阱伤害的豁免检定优势，搜索密门时能以快步移动。",
        "effect": {"trap_detection_advantage": True, "trap_save_advantage": True},
    },
    {
        "name": "坚毅", "id": "durable",
        "desc": "你的生命力超乎常人。体质+1（上限20），休息恢复生命时每个生命骰至少恢复相当于体质调整值×2的点数。",
        "effect": {"attr_choice": ["con"], "attr_bonus": 1, "min_hit_die_heal": "con_mod*2"},
    },
    {
        "name": "元素导师", "id": "elemental_adept",
        "desc": "你对一种元素的掌控已臻化境。选择一种伤害类型（酸/冷/火/电/雷），你的法术无视该类型的抗性，伤害骰中的1视为2。",
        "effect": {"ignore_element_resistance": True, "damage_1_as_2": True},
    },
    {
        "name": "擒抱专家", "id": "grappler",
        "desc": "你擅长压制对手。对被擒抱生物的攻击有优势，可耗动作尝试压制被擒抱生物（双方均受束缚直到擒抱结束）。",
        "effect": {"advantage_vs_grappled": True, "pin_action": True},
    },
    {
        "name": "巨武器大师", "id": "great_weapon_master",
        "desc": "你的重击势大力沉。近战重击或杀敌后可额外攻击一次。可用-5命中换+10伤害（需用重型双手武器）。",
        "effect": {"bonus_attack_on_crit_kill": True, "power_attack_minus5_plus10": True},
    },
    {
        "name": "治疗师", "id": "healer",
        "desc": "你的治疗技艺精湛。使用医疗包稳定濒死生物可让其恢复1HP。短休治疗每个生物时额外恢复1d6+4+目标等级HP。",
        "effect": {"stabilize_restores_1hp": True, "short_rest_heal_bonus": "1d6+4+level"},
    },
    {
        "name": "重甲大师", "id": "heavy_armor_master",
        "desc": "重甲是你的钢铁堡垒。力量+1（上限20），穿着重甲时非魔法钝/刺/挥砍伤害减少3点。",
        "effect": {"attr_choice": ["str"], "attr_bonus": 1, "heavy_armor_dr_3": True},
    },
    {
        "name": "鼓舞领袖", "id": "inspiring_leader",
        "desc": "你的话语能点燃战友的斗志。短休时花费10分钟演讲，给予最多6个友方生物临时HP=你的等级+魅力调整值。",
        "effect": {"inspiring_speech_temp_hp": "level+cha_mod"},
    },
    {
        "name": "敏锐", "id": "keen_mind",
        "desc": "你的头脑如精密的时钟。智力+1（上限20），你总是知道北方在哪、离日出日落还有多久，可准确回忆一个月内的任何见闻。",
        "effect": {"attr_choice": ["int"], "attr_bonus": 1, "always_know_north": True, "perfect_recall_month": True},
    },
    {
        "name": "轻灵移动", "id": "mobile",
        "desc": "你在战场上如风般穿梭。移速+10尺，撤离时在困难地形中不会减速，近战攻击后不受借机攻击。",
        "effect": {"speed_bonus": 10, "difficult_terrain_dash_ok": True, "no_ao_on_melee": True},
    },
    {
        "name": "长柄武器大师", "id": "polearm_master",
        "desc": "长柄武器在你手中如臂使指。持用长棍/矛/戟时可用附赠动作以d4攻击。敌人进入你的触及范围时可借机攻击。",
        "effect": {"polearm_bonus_d4_attack": True, "polearm_opportunity_on_enter": True},
    },
    {
        "name": "仪式施法者", "id": "ritual_caster",
        "desc": "你学会了以仪式方式施法。选择法师/牧师/德鲁伊/诗人/术士/邪术师之一的仪式法术列表，获得仪式书，可抄录该职业的仪式法术。",
        "effect": {"ritual_spell_access": True},
    },
    {
        "name": "哨兵", "id": "sentinel",
        "desc": "你是防线的铁壁。借机攻击命中时目标速度变为0。即使目标撤离心动作也能借机攻击。附近敌人攻击友方时你可用反应攻击。",
        "effect": {"opportunity_stops_movement": True, "ignore_disengage": True, "reaction_attack_on_ally_targeted": True},
    },
    {
        "name": "神射手", "id": "sharpshooter",
        "desc": "你的远程射击堪称艺术。远程攻击无视半掩体和四分之三掩体，远距射击无劣势。可用-5命中换+10伤害。",
        "effect": {"ignore_cover": True, "long_range_no_disadvantage": True, "power_shot_minus5_plus10": True},
    },
    {
        "name": "盾牌大师", "id": "shield_master",
        "desc": "盾牌是你的第二武器。攻击后可用附赠动作推撞，可将盾牌AC加值用于敏捷豁免，成功豁免时可用反应完全免伤。",
        "effect": {"shield_shove_bonus_action": True, "shield_ac_to_dex_save": True, "evasion_reaction": True},
    },
    {
        "name": "魔法学徒", "id": "magic_initiate",
        "desc": "你窥见了魔法的门径。选择法师/牧师/德鲁伊/诗人/术士/邪术师之一，获得该职业2个戏法和1个1环法术（每日1次）。",
        "effect": {"two_cantrips": True, "one_1st_level_spell_daily": True},
    },
    {
        "name": "凶蛮打击", "id": "savage_attacker",
        "desc": "你的每一下攻击都直击要害。每回合一次，近战武器伤害骰可重掷一次并取较高结果。",
        "effect": {"reroll_melee_damage_once_per_turn": True},
    },
    {
        "name": "巧手专家", "id": "skilled",
        "desc": "你通过刻苦训练掌握了更多技艺。获得任意三项技能或工具的熟练项。",
        "effect": {"gain_three_proficiencies": True},
    },
    {
        "name": "幸运", "id": "lucky",
        "desc": "命运对你格外眷顾。你获得3点幸运点。每次长休重置。可在攻击/属性检定/豁免时消耗1点额外掷d20选用其中任一结果。",
        "effect": {"luck_points": 3, "per_long_rest": True},
    },
    {
        "name": "健壮", "id": "tough",
        "desc": "你的生命力如巨熊般顽强。HP上限增加相当于等级×2。此后每次升级额外+2HP。",
        "effect": {"hp_bonus": "level*2", "future_level_hp_bonus": 2},
    },
    {
        "name": "战地施法者", "id": "war_caster",
        "desc": "你在枪林弹雨中仍能专注施法。受伤时专注豁免优势，持武器和盾牌时仍可施法，借机攻击可改用施法代替。",
        "effect": {"concentration_advantage": True, "somatic_with_weapons": True, "spell_as_opportunity_attack": True},
    },
]

SKILLS_LIST = [
    {"name": "运动", "attr": "str", "desc": "攀爬、跳跃、游泳"},
    {"name": "特技", "attr": "dex", "desc": "平衡、翻滚、闪避"},
    {"name": "巧手", "attr": "dex", "desc": "扒窃、开锁、手部戏法"},
    {"name": "潜行", "attr": "dex", "desc": "隐匿移动、不被发现"},
    {"name": "奥秘", "attr": "int", "desc": "魔法知识、符文、外层位面"},
    {"name": "历史", "attr": "int", "desc": "往昔事件、古文明、战争"},
    {"name": "调查", "attr": "int", "desc": "搜索、推理、发现线索"},
    {"name": "自然", "attr": "int", "desc": "动植物、地理、天候"},
    {"name": "宗教", "attr": "int", "desc": "神祇、仪式、圣典"},
    {"name": "洞悉", "attr": "wis", "desc": "辨别谎言、揣摩意图"},
    {"name": "医药", "attr": "wis", "desc": "诊断伤病、稳定伤势"},
    {"name": "察觉", "attr": "wis", "desc": "发现细节、听到动静"},
    {"name": "生存", "attr": "wis", "desc": "追踪、觅食、导航"},
    {"name": "欺瞒", "attr": "cha", "desc": "说谎、伪装、误导"},
    {"name": "威吓", "attr": "cha", "desc": "胁迫、恐吓、施压"},
    {"name": "表演", "attr": "cha", "desc": "演出、演说、乐器"},
    {"name": "游说", "attr": "cha", "desc": "谈判、交涉、说服"},
]
