"""TRPG 世界大纲生成——多步生成+迭代评分至90+

采用分层生成策略：
  Step 1: 世界观与冲突核心（500-800字）
  Step 2: 主线三幕结构（800-1200字）
  Step 3: NPC与支线网络（500-800字）
  Step 4: 遭遇表、关键物品与秘密（400-600字）
  Step 5: 合并、自评、迭代修订至90+
每个步骤独立调用LLM，质量更高。
"""

import json, re
from dataclasses import dataclass, field
from openai import AsyncOpenAI
from backend.config import settings
from backend.engine.world_state import NpcEntry, PlotFlag, LocationEntry, WorldState
from backend.engine.game_systems import build_system_rule_block, get_system
from backend.engine.llm_utils import strip_refusal as _strip_refusal
from backend.knowledge_base import get_knowledge_base


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

1. npcs: 所有具名NPC，每个包含 name, race, role, location, attitude(初始态度), importance("major"=重要NPC/完整角色卡, "minor"=简单NPC/简要卡), personality, motivation, secret(如有), relation_to_plot, level(1-20整数), ac(护甲等级), hp(生命值), max_hp(最大生命值), attributes(属性对象，如 {"str":10,"dex":14,"con":12,"int":11,"wis":13,"cha":9}，COC用 {"str":50,"con":60,"dex":40,"int":70,"pow":55,"cha":45,"siz":60,"edu":65}), skills(技能数组，如 ["侦查","潜行"]), traits(特性/动作数组，如 ["多才多艺","借机攻击"]), equipment(随身可见装备数组，如 ["皮甲","长剑","钱袋"]), appearance(外貌描述), related_locations(常去/所属地点名数组), related_npcs(认识/敌对/盟友NPC名数组), related_creatures(随从/宠物/宿敌生物名数组)。重要NPC必须填全 personality/motivation/secret/relation_to_plot/traits/attributes/equipment/appearance/related_*；简单NPC也必须包含 attributes/skills/traits/equipment/appearance/related_*（可简略但不可省略），personality/motivation/secret 可留空或最小化。
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

async def _llm(client: AsyncOpenAI, model: str, system: str, user: str,
               max_tokens: int = 4000, temp: float = 0.85, timeout: float = 90.0,
               thinking_strength: str = "medium", token_callback=None) -> str:
    """单次LLM调用，带超时保护与重试；第二次自动提高 max_tokens 以兼容推理模型。

    token_callback 不为 None 时使用流式输出，把每个增量文本实时回调给调用方。
    """
    import asyncio
    mult = 1.8 if thinking_strength == "high" else (0.6 if thinking_strength == "low" else 1.0)
    max_tokens = min(8000, int(max_tokens * mult))
    last_err = None
    for attempt in range(1, 3):
        current_max_tokens = max_tokens if attempt == 1 else min(max(max_tokens * 2, 8000), 8000)
        try:
            if token_callback is not None:
                stream = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=model,
                        messages=[{"role":"system","content":system},{"role":"user","content":user}],
                        max_tokens=current_max_tokens, temperature=temp, stream=True),
                    timeout=timeout,
                )
                content = ""
                last_chunk = None
                async for chunk in stream:
                    last_chunk = chunk
                    d = chunk.choices[0].delta if chunk.choices else None
                    if d and d.content:
                        content += d.content
                        token_callback(d.content)
                content = _strip_refusal(content)
                if content:
                    return content
                reasoning = ""
                if last_chunk is not None and last_chunk.choices:
                    delta = getattr(last_chunk.choices[0], "delta", None)
                    reasoning = getattr(delta, "reasoning_content", None) if delta is not None else None
                print(f"[WorldBuilder] LLM流式调用第{attempt}次空响应 (reasoning_len={len(reasoning or '')}, max_tokens={current_max_tokens})")
                raise RuntimeError("空响应")
            resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=[{"role":"system","content":system},{"role":"user","content":user}],
                    max_tokens=current_max_tokens, temperature=temp),
                timeout=timeout,
            )
            content = resp.choices[0].message.content
            content = _strip_refusal(content or "")
            if content:
                return content
            # DeepSeek 等推理模型可能把 token 全花在 reasoning_content 上，导致 content 为空
            reasoning = getattr(resp.choices[0].message, "reasoning_content", None)
            print(f"[WorldBuilder] LLM调用第{attempt}次空响应 (reasoning_len={len(reasoning or '')}, max_tokens={current_max_tokens})")
            raise RuntimeError("空响应")
        except asyncio.TimeoutError as e:
            last_err = f"超时({timeout}s)"
            print(f"[WorldBuilder] LLM调用第{attempt}次超时({timeout}s)")
        except Exception as e:
            last_err = str(e)
            print(f"[WorldBuilder] LLM调用第{attempt}次失败: {e}")
        await asyncio.sleep(1)
    print(f"[WorldBuilder] LLM调用最终失败: {last_err}，降级处理")
    return ""


def _with_knowledge(prompt: str, query: str, system: str, top_k: int = 3,
                    username: str | None = None) -> str:
    """从本地知识库检索相关规则/设定片段并附加到 Prompt（按用户名隔离）。"""
    try:
        results = get_knowledge_base().retrieve(query, system=system, top_k=top_k, username=username)
        if results:
            block = "\n\n## 可用规则/设定参考（来自知识库，按需采用）\n"
            block += "\n".join(f"- [{r.get('title','')}] {r.get('text','')[:300]}" for r in results)
            return prompt + block
    except Exception:
        pass
    return prompt


def _programmatic_score(outline: str, ws) -> int:
    """基于剧本结构完整性的程序化评分，避免 LLM 稳定输出同一分数。"""
    score = 0
    if len(outline) >= 1000:
        score += 10
    if len(outline) >= 3000:
        score += 10
    if len(outline) >= 5000:
        score += 5
    if re.search(r"第[一二三]幕|第一幕|第二幕|第三幕", outline):
        score += 20
    if re.search(r"^#|^##", outline, re.M):
        score += 5
    npc_count = len(ws.npcs)
    loc_count = len(ws.locations)
    flag_count = len(ws.plot_flags)
    score += min(npc_count, 5) * 3
    score += min(loc_count, 5) * 2
    score += min(flag_count, 5) * 2
    if ws.world_rules:
        score += 5
    if npc_count >= 3:
        score += 5
    if loc_count >= 3:
        score += 5
    if flag_count >= 5:
        score += 5
    return min(100, score)


def _dedupe_headings(text: str) -> str:
    """合并后处理：去除连续/重复出现的相同 Markdown 标题。"""
    seen: set[str] = set()
    out: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#") and stripped in seen:
            continue
        if stripped.startswith("#"):
            seen.add(stripped)
        out.append(line)
    return "\n".join(out)


def _extract_json(text: str) -> dict:
    """从可能含有markdown包裹的文本中提取JSON。"""
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        t = "\n".join(lines[1:])
        if t.endswith("```"): t = t[:-3]
        t = t.strip()
    # 尝试找到第一个{和最后一个}
    start = t.find("{")
    end = t.rfind("}")
    if start >= 0 and end > start:
        t = t[start:end+1]
    try:
        data = json.loads(t)
    except Exception:
        # LLM 输出 JSON 有轻微语法问题时，用 json_repair 自动修复
        try:
            from json_repair import repair_json
            t = repair_json(t, return_objects=False)
            data = json.loads(t)
        except Exception:
            raise
    if not isinstance(data, dict):
        raise json.JSONDecodeError("JSON must be an object", t, 0)
    return data


async def build_world(
    player_input: str,
    reference_script: str = "",
    api_key: str | None = None,
    model_name: str | None = None,
    base_url: str | None = None,
    target_score: int = 80,
    max_revisions: int = 2,
    game_system: str = "dnd5e",
    custom_rules: str = "",
    custom_classes: list[str] | None = None,
    custom_skills: list[str] | None = None,
    extra_attributes: dict | None = None,
    progress_callback=None,
    thinking_strength: str = "medium",
    username: str | None = None,
    token_callback=None,
) -> tuple[str, int, list, WorldState]:
    """多Agent分层生成世界大纲→自评→修订→提取世界状态。

    返回: (大纲文本, 最终分数, 评分历史, WorldState对象)
    """
    api_key = api_key or settings.LLM_API_KEY
    base_url = base_url or settings.LLM_BASE_URL
    model = model_name or settings.LLM_MODEL_NAME
    if not model:
        raise ValueError("请提供模型名称")
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    # P2修复：为世界生成增加宽松的评分基线，避免无限修订循环

    ref = f"\n## 参考剧本\n{reference_script}" if reference_script.strip() else ""
    pi = f"## 玩家设定\n{player_input}"
    if ref:
        pi += "\n\n## 改编约束（重要）\n- 必须保留参考剧本中的专有名词、核心反派、怪物、地点、关键事件与氛围。\n- 可以扩展细节和分支，但不得把原剧本的核心元素替换成其他作品/其他模组的元素。\n- 如果参考剧本信息不足，可以合理补全，但不能与原文明显冲突。"
    sys_cfg = get_system(game_system)
    system_block = build_system_rule_block(game_system, custom_rules)
    pi += f"\n\n## 规则系统\n- 类型: {sys_cfg['label']}\n- 说明: {sys_cfg['description']}\n{system_block[:1800]}"
    if custom_classes:
        pi += "\n\n## 剧本专属职业/身份（必须纳入设计）\n" + "、".join(custom_classes)
    if custom_skills:
        pi += "\n\n## 剧本专属技能（必须纳入设计）\n" + "、".join(custom_skills)
    if extra_attributes:
        pi += "\n\n## 额外属性/规则特色\n" + "\n".join(f"- {k}: {v}" for k, v in extra_attributes.items())

    style_directive = (
        f"【玩家基调/备注】\n{player_input}\n"
        f"【自定义规则/备注】\n{custom_rules or '无'}\n"
        f"【参考剧本节选】\n{reference_script[:2000] if reference_script.strip() else '无'}\n"
        "【内容安全】所有涉及亲密/成人内容的角色必须明确为18岁以上成年人；禁止未成年角色参与。"
    )

    # ── Step 1: 世界观与冲突核心 ──
    print("[WorldBuilder] Step 1/6: 世界观与冲突核心...")
    if progress_callback: progress_callback("构建世界观与冲突核心", 10, "正在生成世界观、冲突与阵营...")
    step1 = await _llm(client, model,
        "你是一位获奖奇幻小说家。创作深刻、独特的世界观。",
        _with_knowledge(STEP1_CONFLICT.format(style_directive=style_directive, player_input=pi, reference=ref), "世界观 冲突 势力 阵营 魔法 社会", game_system, 3, username),
        max_tokens=3000, temp=0.9, timeout=60, thinking_strength=thinking_strength, token_callback=token_callback)
    if not step1:
        raise RuntimeError("世界生成失败：模型调用多次超时，请检查模型/网络后重试")

    # ── Step 2: 主线三幕结构 ──
    print("[WorldBuilder] Step 2/6: 主线三幕结构...")
    if progress_callback: progress_callback("编织主线三幕结构", 25, "正在设计三幕剧情、转折与结局...")
    step2 = await _llm(client, model,
        "你是一位TRPG冒险设计师。设计引人入胜的三幕结构。",
        _with_knowledge(STEP2_PLOT.format(style_directive=style_directive, world_context=step1), "三幕结构 剧情节点 转折 结局", game_system, 3, username),
        max_tokens=4000, temp=0.85, timeout=90, thinking_strength=thinking_strength, token_callback=token_callback)
    if not step2:
        step2 = "主线采用经典三幕结构：第一幕引入冲突，第二幕遭遇转折与背叛，第三幕迎来高潮与结局。具体情节建议结合世界观继续细化。"

    # ── Step 3: NPC网络与支线 ──
    print("[WorldBuilder] Step 3/6: NPC网络与支线...")
    if progress_callback: progress_callback("塑造NPC与支线网络", 40, "正在塑造NPC、势力与支线任务...")
    step3 = await _llm(client, model,
        "你是一位角色设计大师。创造有深度的NPC网络。",
        _with_knowledge(STEP3_NPC.format(style_directive=style_directive, world_context=step1, plot_context=step2), "NPC 反派 动机 支线 关系", game_system, 3, username),
        max_tokens=3500, temp=0.9, timeout=90, thinking_strength=thinking_strength, token_callback=token_callback)
    if not step3:
        step3 = "关键NPC网络：围绕核心冲突设置至少五名角色，包含盟友、对手与隐藏敌意的中立者，并安排两条与主线隐性关联的支线。"

    # ── Step 4: 遭遇表 ──
    print("[WorldBuilder] Step 4/6: 遭遇表与隐藏内容...")
    if progress_callback: progress_callback("布置遭遇与隐藏内容", 55, "正在设计遭遇、陷阱、宝物与秘密...")
    step4 = await _llm(client, model,
        "你是一位TRPG遭遇设计师。设计挑战与秘密。",
        _with_knowledge(STEP4_ENCOUNTERS.format(style_directive=style_directive, world_context=step1, plot_context=step2, npc_context=step3), "遭遇 战斗 陷阱 魔法物品 秘密", game_system, 3, username),
        max_tokens=3500, temp=0.85, timeout=90, thinking_strength=thinking_strength, token_callback=token_callback)
    if not step4:
        step4 = "遭遇与隐藏内容：设计五场类型各异的遭遇（战斗、社交、探索、陷阱），三处秘密区域，以及一件带有背景故事的独特宝物。"

    # ── Step 5: 合并+评分 ──
    history = []
    print("[WorldBuilder] Step 5/6: 合并+自评...")
    if progress_callback: progress_callback("合并大纲并自评", 70, "评委正在审阅四个部分并合并...")
    merge_result = await _llm(client, model,
        "你是一位TRPG模组主编。诚实评分，合理打分，不要过分苛刻。",
        MERGE_PROMPT.format(style_directive=style_directive, step1=step1, step2=step2, step3=step3, step4=step4),
        max_tokens=5000, temp=0.4, timeout=90, thinking_strength=thinking_strength, token_callback=token_callback)

    try:
        scored = _extract_json(merge_result)
    except (json.JSONDecodeError, KeyError):
        m = re.search(r'"total_score"\s*:\s*(\d+)', merge_result)
        s = int(m.group(1)) if m else 75
        scored = {"total_score": s, "scores": {}, "issues": [], "suggestions": [],
                  "merged_outline": f"{step1}\n\n---\n\n{step2}\n\n---\n\n{step3}\n\n---\n\n{step4}"}

    score = scored.get("total_score", 75)
    outline = scored.get("merged_outline", "")
    # 健壮性：如果模型返回的 merged_outline 为空，则用四个分步结果拼接，避免生成空剧本
    if not outline or not outline.strip():
        outline = f"{step1}\n\n---\n\n{step2}\n\n---\n\n{step3}\n\n---\n\n{step4}"
    history.append({"iteration": 1, "score": score,
                    "issues": scored.get("issues", []),
                    "suggestions": scored.get("suggestions", [])})

    # ── 迭代修订 ──
    for rev in range(2, max_revisions + 2):
        if score >= target_score:
            break

        print(f"[WorldBuilder] 修订 {rev}/{max_revisions+1} (当前评分:{score})...")
        if progress_callback: progress_callback("评委正在修订问题", 78, "AI 正在根据建议修订大纲...")
        rev_result = await _llm(client, model,
            "你是一位严谨的TRPG模组编辑。按照建议修改，提高质量。",
            REVISE_PROMPT.format(
                current_score=score, outline=outline,
                issues_suggestions=json.dumps({
                    "issues": scored.get("issues", []),
                    "suggestions": scored.get("suggestions", []),
                }, ensure_ascii=False)),
            max_tokens=6000, temp=0.5, timeout=120, thinking_strength=thinking_strength, token_callback=token_callback)

        try:
            rev_data = _extract_json(rev_result)
        except json.JSONDecodeError:
            break

        new_outline = rev_data.get("revised_outline", outline)
        if new_outline and len(new_outline) > 500:
            outline = new_outline

        # 自评新版本——不要太严格，合理评价
        if progress_callback: progress_callback("评委正在复评", 82, "AI 正在对新版大纲进行复评...")
        rescore = await _llm(client, model,
            "你是一位公平的TRPG模组评委。诚实评价，不过分苛刻也不故意放水。",
            f"新大纲:\n{outline[:4000]}\n\n请输出JSON: {{\"total_score\":数字(0-100)}}",
            max_tokens=1200, temp=0.3, timeout=60, thinking_strength=thinking_strength, token_callback=token_callback)
        try:
            rescore_data = _extract_json(rescore)
            new_score = rescore_data.get("total_score", score)
            # 更新scored以反映最新的评估，避免下一轮用旧的issues
            if new_score >= score:
                score = new_score
                # 合并新评估的建议
                new_issues = rescore_data.get("issues", [])
                new_suggestions = rescore_data.get("suggestions", [])
                if new_issues or new_suggestions:
                    scored["issues"] = new_issues
                    scored["suggestions"] = new_suggestions
        except json.JSONDecodeError:
            m = re.search(r'"total_score"\s*:\s*(\d+)', rescore)
            new_score = int(m.group(1)) if m else score
            if new_score >= score:
                score = new_score

        # 如果分数没变，记录但不中断
        if new_score == score:
            print(f"[WorldBuilder] 评分未提升({score})，继续下一轮或结束")
        history.append({"iteration": rev, "score": score})

    # ── Step 6: 提取结构化世界状态 ──
    outline = _dedupe_headings(outline)
    print("[WorldBuilder] Step 6/6: 提取结构化世界状态...")
    if progress_callback: progress_callback("提取世界状态与NPC", 85, "正在提取NPC、旗标、地点与世界规则...")
    ws = WorldState(world_outline=outline)
    state_data: dict = {}
    try:
        extract_result = await _llm(client, model,
            "你是一位数据分析师。从文本中提取结构化信息。只返回JSON。",
            EXTRACT_STATE_PROMPT.format(outline=outline[:16000]),
            max_tokens=4000, temp=0.3, timeout=90, thinking_strength=thinking_strength, token_callback=token_callback)
        state_data = _extract_json(extract_result)
    except Exception as e:
        print(f"[WorldBuilder] 首次结构化提取失败，已降级继续: {e}")
        state_data = {}

    if not state_data or not (state_data.get("npcs") or state_data.get("locations") or state_data.get("plot_flags")):
        print("[WorldBuilder] 首次结构化提取为空/失败，启动二次专业化提取...")
        try:
            fallback_result = await _llm(client, model,
                "你是一位专门抽取TRPG角色、地点与剧情旗标的专家。只返回JSON。",
                EXTRACT_STATE_FALLBACK_PROMPT.format(outline=outline[:12000]),
                max_tokens=2500, temp=0.2, timeout=90, thinking_strength=thinking_strength, token_callback=token_callback)
            fallback_data = _extract_json(fallback_result)
            if fallback_data:
                state_data = fallback_data
                print(f"[WorldBuilder] 二次专业化提取成功: NPC={len(fallback_data.get('npcs', []))}, 地点={len(fallback_data.get('locations', []))}, 旗标={len(fallback_data.get('plot_flags', []))}")
        except Exception as e2:
            print(f"[WorldBuilder] 二次专业化提取失败: {e2}")

    # 应用提取结果
    if state_data:
        for n in state_data.get("npcs", []):
            ws.npcs.append(NpcEntry(
                name=n.get("name",""), race=n.get("race",""), role=n.get("role",""),
                location=n.get("location",""), attitude=n.get("attitude","中立"),
                personality=n.get("personality",""), motivation=n.get("motivation",""),
                secret=n.get("secret",""), relation_to_plot=n.get("relation_to_plot",""),
                level=int(n.get("level", 1) or 1), ac=int(n.get("ac", 10) or 10),
                hp=int(n.get("hp", 10) or 10), max_hp=int(n.get("max_hp", 10) or 10),
                attributes=n.get("attributes") or {}, skills=n.get("skills") or [],
                traits=n.get("traits") or [], equipment=n.get("equipment") or [],
                related_locations=n.get("related_locations", []),
                related_npcs=n.get("related_npcs", []),
                related_creatures=n.get("related_creatures", []),
                importance=n.get("importance", "minor"),
            ))
        for p in state_data.get("plot_flags", []):
            ws.plot_flags.append(PlotFlag(
                key=p.get("key",""), status=p.get("status","未触发"),
                description=p.get("description",""),
            ))
        for l in state_data.get("locations", []):
            ws.locations.append(LocationEntry(
                name=l.get("name",""), description=l.get("description",""),
                status=l.get("status","可访问"), type=l.get("type",""),
                culture=l.get("culture",""), notable_figures=l.get("notable_figures",""),
                dangers=l.get("dangers",""), secrets=l.get("secrets",""),
                related_locations=l.get("related_locations", []),
                related_npcs=l.get("related_npcs", []),
                related_creatures=l.get("related_creatures", []),
            ))
        ws.creatures = state_data.get("creatures", [])
        ws.spells = state_data.get("spells", [])
        ws.world_rules = state_data.get("world_rules", "")
    if not ws.npcs and not ws.locations:
        print("[WorldBuilder] 警告：最终结构化结果仍为空（npcs/locations 均为空）")

    # 程序化评分与 LLM 评分混合，避免“永远 88 分”的假象
    prog_score = _programmatic_score(outline, ws)
    final_score = round((score + prog_score) / 2)
    history.append({"iteration": "final", "score": final_score, "programmatic": prog_score})
    if progress_callback: progress_callback("生成完成", 100, "世界生成完成")
    return outline, final_score, history, ws
