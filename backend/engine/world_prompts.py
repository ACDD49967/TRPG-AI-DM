"""世界生成各步骤的提示词常量（世界观/三幕/ NPC 网络/遭遇表/合并/修订/结构化提取）。

从 backend.engine.world_builder 拆出。
"""
from __future__ import annotations



# ═══════════════════════════════════════════════════════════════
# 分步生成 Prompt
# ═══════════════════════════════════════════════════════════════

STEP1_CONFLICT = """你是一位风格多变的TRPG模组设计师。请根据基调、备注与参考剧本，为以下设定创作**世界观与核心驱动**。

{style_directive}

{player_input}
{reference}

要求：
- 500-800字，风格必须严格贴合基调、备注与参考剧本：可以是史诗奇幻、轻松冒险、日常喜剧、浪漫、恐怖、悬疑、黑色幽默、现代怪谈等，不要默认苦大仇深
- 写出世界的"核心驱动/张力"（不一定是战争或灾难）：可以是秘密、欲望、误会、传统、诅咒、阴谋、庆典危机、家庭纠葛等
- 如果基调需要反派，则动机可信；如果基调轻松，冲突可以是喜剧性误会或滑稽对手
- 至少2个阵营/势力/群体，各有独立目标（轻松向也可以是家庭、社团、小镇派系）
- 世界观要有贴合风格的独特细节：地名、历史事件、特殊规则、生活气息
- 参考剧本如果已给出明确风格与人设，必须优先贴合参考剧本，而不是改写成千篇一律的暗黑奇幻

输出格式：直接输出Markdown文本，不要JSON包裹。"""


STEP2_PLOT = """你是一位资深TRPG模组设计师。基于以下世界观与风格基调，创作**结构完整的主线剧情**。

{style_directive}

{world_context}

要求：
- 800-1200字
- 风格与节奏必须贴合基调：轻松喜剧、日常、浪漫、恐怖、悬疑、史诗等各有对应的叙事方式，不要默认"苦大仇深"
- 结构完整：第一幕(开端)如何卷入/初始事件；第二幕(发展)至少3个关键节点与一个转折；第三幕(高潮与结局)至少2种结局路径，写明达成条件
- 高潮与结局符合基调：不一定是生死决战，可以是真相揭露、关系确立、盛大演出、比赛夺冠、婚礼、救出某人、化解误会等
- 每一幕结尾设置"剧情钩子"
- 完整性优先：所有重要铺垫必须在结局前回收，或明确留作续集钩子；避免烂尾和逻辑断裂
- 难度曲线合理：从简单事件逐步升级，但升级方向符合基调

输出格式：直接输出Markdown文本。"""


STEP3_NPC = """你是一位角色设计大师。基于以下世界观、剧情与风格基调，创作**关键NPC网络与支线**。

{style_directive}

{world_context}
{plot_context}

要求：
- 至少5个关键NPC（可根据剧本规模调整），每个NPC要有完整弧光：欲望、缺陷、变化
- **对手/反派塑造按基调灵活处理**：
  * 黑暗向：可以有不可原谅的恶人，动机可信，不强行洗白
  * 轻松/喜剧向：可以是有缺点的可爱对手、误会型反派、嘴硬心软的死对头
  * 浪漫/日常向：冲突可以来自关系误解、家庭压力、社会规则，而不是杀人放火
- NPC之间有关联网络：谁爱谁、谁恨谁、谁欠谁的、谁在偷偷帮谁
- 至少2个支线/副线，每个都与主线有隐性关联
- 隐藏敌意、秘密、背叛按基调可选，不要强制每局都苦大仇深
- 所有重要NPC都应能推动故事完整性，避免工具人
- **世界独立性**：NPC、势力、地点与生物应作为世界的一部分独立存在，拥有自己的目标、生活、历史与计划；玩家是进入这个世界的参与者，而不是所有事件围绕其旋转的绝对中心。
- 不要为了突出玩家而让所有NPC、敌人、事件都只针对玩家；应留有NPC之间、势力之间自然发生的冲突与推进。

输出格式：直接输出Markdown文本。"""


STEP4_ENCOUNTERS = """你是一位TRPG遭遇/事件设计师。为以下冒险设计**事件表与隐藏内容**。

{style_directive}

{world_context}
{plot_context}
{npc_context}

要求：
- 至少5场事件/遭遇（战斗、社交、探索、解谜、日常、追逐、陷阱等按基调混合）
- 每场事件含：适合当前等级与基调的风险等级、关键NPC/敌人数据、环境因素、可能奖励
- 至少3个隐藏内容/秘密/彩蛋，玩家可能发现也可能错过
- 至少1件独特物品/道具/信物（有名称、背景故事、效果）
- 高风险时刻按基调设置：黑暗向可以致命，轻松向可以是有惊无险的麻烦，不要默认死亡
- 完整性优先：事件必须推动主线或支线，不能是填充内容

输出格式：直接输出Markdown文本。"""



# ═══════════════════════════════════════════════════════════════
# 合并+评分 Prompt
# ═══════════════════════════════════════════════════════════════

MERGE_PROMPT = """你是一位TRPG模组主编。请根据风格基调，将以下四个部分合并为一份完整、自洽的冒险大纲，然后自评。

{style_directive}

## 第一部分 - 世界观
{step1}

## 第二部分 - 主线剧情
{step2}

## 第三部分 - NPC与支线
{step3}

## 第四部分 - 遭遇与隐藏内容
{step4}

## 合并要求
- 整合为结构清晰、层次分明的完整Markdown文档（2500-5000字）
- 去重、补漏、统一文风，并严格保持基调一致
- 确保数据一致（NPC名字、地点名称等）
- 完整性优先：开头钩子、过程推进、高潮、结局、支线回收、伏笔闭合、NPC弧光完整
- 参考剧本/备注有明确风格时，必须优先贴合参考风格，不要擅自改回千篇一律的暗黑奇幻
- **冒险独立性**：世界应有自身的运转逻辑，NPC/势力/生物有独立目标与行动；玩家参与并影响冒险，而不是冒险完全围绕玩家展开。

## 评分标准（满分100）
1. 完整性与结构(20分)：是否有完整的开端、发展、高潮、结局，伏笔是否回收
2. 基调一致性(10分)：是否严格贴合玩家给定的基调、备注与参考剧本
3. 世界观深度(15分)：设定是否独特、有层次且贴合风格
4. 剧情张力(15分)：三幕结构是否引人入胜、转折有力
5. NPC丰富度(15分)：角色是否有深度、动机、关联与弧光
6. 可玩性与分支(15分)：是否有有意义的选择和多种结局
7. 规则合规(10分)：DC/CR/风险是否合理

输出JSON（只输出JSON对象，不要Markdown代码块，不要任何解释文字）：
{{
  "total_score": 数字,
  "scores": {{"完整性":n,"基调一致性":n,"世界观深度":n,"剧情张力":n,"NPC丰富度":n,"可玩性":n,"规则合规":n}},
  "issues": ["问题"],
  "suggestions": ["改进建议"],
  "merged_outline": "合并后的完整大纲(Markdown)"
}}

如果 total_score >= 90，merged_outline 可以保持不变。
如果 total_score < 90，必须根据suggestions实质修改后再放入merged_outline。"""



REVISE_PROMPT = """当前大纲评分 {current_score}/100，未达90分。请根据以下建议修改大纲。

## 当前大纲
{outline}

## 问题与建议
{issues_suggestions}

请输出修改后的完整大纲（只输出JSON对象，不要Markdown代码块，不要解释文字）：
{{"revised_outline": "完整的修改后大纲(Markdown)", "changes_summary": "修改摘要"}}"""



# ═══════════════════════════════════════════════════════════════
# 从大纲提取世界状态（NPC、旗标等）
# ═══════════════════════════════════════════════════════════════

EXTRACT_STATE_PROMPT = """请从以下TRPG冒险大纲中提取关键的结构化信息。

## 大纲
{outline}

## 要求
提取以下JSON结构：

1. npcs: 所有具名NPC，每个包含 name, race, role, location, attitude(初始态度), importance("major"=重要NPC/完整角色卡, "minor"=简单NPC/简要卡), personality, motivation, secret(如有), relation_to_plot, level(1-20整数), ac(护甲等级), hp(生命值), max_hp(最大生命值), attributes(属性对象，如 {{"str":10,"dex":14,"con":12,"int":11,"wis":13,"cha":9}}，COC用 {{"str":50,"con":60,"dex":40,"int":70,"pow":55,"cha":45,"siz":60,"edu":65}}), skills(技能数组，如 ["侦查","潜行"]), traits(特性/动作数组，如 ["多才多艺","借机攻击"]), equipment(随身可见装备数组，如 ["皮甲","长剑","钱袋"]), appearance(外貌描述), related_locations(常去/所属地点名数组), related_npcs(认识/敌对/盟友NPC名数组), related_creatures(随从/宠物/宿敌生物名数组)。重要NPC必须填全 personality/motivation/secret/relation_to_plot/traits/attributes/equipment/appearance/related_*；简单NPC也必须包含 attributes/skills/traits/equipment/appearance/related_*（可简略但不可省略），personality/motivation/secret 可留空或最小化。
2. plot_flags: 关键剧情节点，每个包含 key(旗标名), status(默认"未触发"), description
3. locations: 关键地点，每个包含 name, description, status, type(城市/地城/森林等), culture(文化/势力), notable_figures(知名人物), dangers(危险), secrets(如有), related_locations(相邻/关联地点名数组), related_npcs(常驻/关联NPC名数组), related_creatures(出没生物名数组)。重要地点必须填全以上字段；普通地点至少填 description/status/type。
4. world_rules: 这个世界独特的规则（魔法限制、社会规则等）
5. creatures: 剧本中出现的关键生物/怪物，每个包含 name, description, stats(对象，必须含 HP/AC/速度/六维(力量/敏捷/体质/智力/感知/魅力)/技能/特性/动作), tags(数组), related_locations(出没地点名数组), related_npcs(相关NPC名数组)
6. spells: 剧本中涉及的重要法术/仪式，每个包含 name, level, school, ritual, casting_time, range, components, duration, description, classes(数组)

## 严格输出格式（必须遵守）
- 只输出一个 JSON 对象，不要 Markdown 代码块（不要 ```json），不要任何解释、前后缀或注释。
- 所有键名严格使用英文小写 snake_case。
- 数组为空时输出 []，字符串为空时输出 ""。

输出纯JSON：
{{"npcs":[...],"plot_flags":[...],"locations":[...],"creatures":[...],"spells":[...],"world_rules":"..."}}"""



EXTRACT_STATE_FALLBACK_PROMPT = """你是专门从TRPG冒险大纲中抽取“角色、地点、剧情旗标”的专家。第一次宽泛提取失败，请改用更聚焦的方式重新提取。

## 大纲
{outline}

## 任务
只提取大纲中明确出现的具名内容，宁缺毋滥，但不要漏掉重要角色与地点。

输出严格 JSON 对象（不要 Markdown 代码块，不要解释）：
{{
  "npcs": [
    {{"name":"角色名","race":"种族或未知","role":"身份/职业","location":"所在地点","attitude":"友善/中立/敌对/忠诚等","importance":"major或minor","personality":"性格","motivation":"动机","secret":"秘密或空","relation_to_plot":"剧情关联","level":1,"ac":10,"hp":10,"max_hp":10,"attributes":{{"str":10,"dex":10,"con":10,"int":10,"wis":10,"cha":10}},"skills":[],"traits":[],"equipment":[],"appearance":"外貌"}}
  ],
  "locations": [
    {{"name":"地点名","description":"描述","status":"可访问","type":"城市/地城/森林等","culture":"","notable_figures":"","dangers":"","secrets":"","related_locations":[],"related_npcs":[],"related_creatures":[]}}
  ],
  "plot_flags": [
    {{"key":"旗标名","status":"未触发","description":"描述"}}
  ]
}}
如果某类确实没有，返回空数组 []。
"""



# ═══════════════════════════════════════════════════════════════
# 核心函数
# ═══════════════════════════════════════════════════════════════

PLOT_FLAGS_ONLY_PROMPT = """请从以下 TRPG 冒险大纲中**只提取剧情旗标**（关键剧情节点、待触发事件、伏笔与条件）。

## 大纲
{outline}

## 输出格式（严格遵守）
只输出一个 JSON 对象，不要 Markdown 代码块、不要任何解释：
{{"plot_flags": [{{"key": "旗标名", "status": "未触发", "description": "触发条件与后果"}}]}}
status 只能是「未触发 / 进行中 / 已完成 / 已失败」之一；若大纲确实没有剧情节点，输出 {{"plot_flags": []}}。"""
