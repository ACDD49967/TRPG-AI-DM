"""D&D 世界大纲生成——Agent1: 剧本写作（多步生成+迭代评分至90+）

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


# ═══════════════════════════════════════════════════════════════
# 分步生成 Prompt
# ═══════════════════════════════════════════════════════════════

STEP1_CONFLICT = """你是一位获奖奇幻小说家兼D&D模组设计师。请为以下设定创作**世界观与冲突核心**。

{player_input}
{reference}

要求：
- 500-800字，史诗感与戏剧张力并重
- 写出世界的"伤口"——这个世界有什么根本性的问题或冲突？为什么现在必须解决？
- 反派（如果有）的动机必须真实可信但不洗白——他们是恶人，有合理的恶的理由
- 至少2个阵营/势力，各有独立目标，彼此冲突
- 世界观要有独特的魔法/社会/历史设定，不能是泛泛的中世纪模板
- 用具体细节让世界鲜活：地名、历史事件名称、特殊规则

输出格式：直接输出Markdown文本，不要JSON包裹。"""

STEP2_PLOT = """你是一位资深D&D模组设计师。基于以下世界观，创作**主线三幕结构**。

{world_context}

要求：
- 800-1200字
- 第一幕(开端)：玩家如何被卷入？初始冲突是什么？必须有"不归点"——玩家无法回头的那一刻
- 第二幕(发展)：至少3个关键剧情节点，包括一个重大转折（背叛、发现真相、盟友阵亡等）
- 第三幕(高潮与结局)：至少2种结局路径（成功/失败/牺牲），每种结局的具体达成条件
- 每一幕结尾设置一个"剧情钩子"——让玩家迫不及待想继续
- 难度曲线合理：从简单遭遇逐步升级到生死决战
- DC和敌人CR符合冒险等级

输出格式：直接输出Markdown文本。"""

STEP3_NPC = """你是一位角色设计大师。基于以下世界观和剧情，创作**关键NPC网络与支线任务**。

{world_context}
{plot_context}

要求：
- 至少5个关键NPC，每个NPC详细描述
- **反派的塑造规则（极其重要）**：
  * 反派有清晰的邪恶动机——贪婪、权力欲、复仇、疯狂、信仰扭曲等
  * 除非剧本明确要求，否则**禁止**在后期洗白反派或让他们"其实是为你好"
  * 反派可以有令人同情的历史，但他们的**当前行为是不可原谅的**
  * 玩家战胜反派不需要感到内疚
- NPC之间有关联网络：谁爱谁、谁恨谁、谁欠谁的
- 至少2个支线任务，每个都与主线有隐性关联
- 至少1个NPC对玩家有隐藏的敌意（即使表面友好）
- 世界不会对玩家手下留情：如果设定中某个角色是冷酷杀手，他就真的会杀人

输出格式：直接输出Markdown文本。"""

STEP4_ENCOUNTERS = """你是一位D&D遭遇设计师。为以下冒险设计**遭遇表与隐藏内容**。

{world_context}
{plot_context}
{npc_context}

要求：
- 至少5场遭遇（战斗+社交+探索+陷阱混合）
- 每场遭遇含：CR等级、敌人数据（AC/HP/攻击方式）、环境因素、战利品
- 至少3个隐藏区域/秘密，玩家可能发现也可能错过
- 至少1件独特的魔法物品（有名称、背景故事、机械效果）
- 至少1个致命陷阱——不够小心就会死
- 标注"高风险时刻"：玩家在此处如果连续骰子失败可能导致角色死亡

输出格式：直接输出Markdown文本。"""


# ═══════════════════════════════════════════════════════════════
# 合并+评分 Prompt
# ═══════════════════════════════════════════════════════════════

MERGE_PROMPT = """你是一位D&D模组主编。请将以下四个部分合并为一份完整的冒险大纲，然后自评。

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
- 去重、补漏、统一文风
- 确保数据一致（NPC名字、地点名称等）
- 保持戏剧张力和史诗感

## 评分标准（满分100）
1. 完整性与结构(15分)：大纲结构是否完整清晰
2. 世界观深度(15分)：设定是否独特、有层次
3. 剧情张力(20分)：三幕结构是否引人入胜、转折有力
4. NPC丰富度(15分)：角色是否有深度、动机、关联
5. 可玩性与分支(15分)：是否有有意义的选择和多种结局
6. 规则合规(10分)：DC/CR是否合理
7. 史诗感与D&D风味(10分)：是否读起来像真正的D&D模组

输出JSON：
{{
  "total_score": 数字,
  "scores": {{"完整性":n,"世界观深度":n,"剧情张力":n,"NPC丰富度":n,"可玩性":n,"规则合规":n,"史诗感":n}},
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

请输出修改后的完整大纲（JSON格式）：
{{"revised_outline": "完整的修改后大纲(Markdown)", "changes_summary": "修改摘要"}}"""


# ═══════════════════════════════════════════════════════════════
# 从大纲提取世界状态（NPC、旗标等）
# ═══════════════════════════════════════════════════════════════

EXTRACT_STATE_PROMPT = """请从以下D&D冒险大纲中提取关键的结构化信息。

## 大纲
{outline}

## 要求
提取以下JSON结构：

1. npcs: 所有具名NPC，每个包含 name, race, role, location, attitude(初始态度), personality, motivation, secret(如有), relation_to_plot
2. plot_flags: 关键剧情节点，每个包含 key(旗标名), status(默认"未触发"), description
3. locations: 关键地点，每个包含 name, description, secrets(如有)
4. world_rules: 这个世界独特的规则（魔法限制、社会规则等）

输出纯JSON：
{{"npcs":[...],"plot_flags":[...],"locations":[...],"world_rules":"..."}}"""


# ═══════════════════════════════════════════════════════════════
# 核心函数
# ═══════════════════════════════════════════════════════════════

async def _llm(client: AsyncOpenAI, model: str, system: str, user: str,
               max_tokens: int = 4000, temp: float = 0.85, timeout: float = 90.0) -> str:
    """单次LLM调用，带超时保护。超时时返回空字符串由调用方降级处理。"""
    import asyncio
    try:
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[{"role":"system","content":system},{"role":"user","content":user}],
                max_tokens=max_tokens, temperature=temp),
            timeout=timeout,
        )
        return resp.choices[0].message.content.strip()
    except asyncio.TimeoutError:
        print(f"[WorldBuilder] LLM调用超时({timeout}s)，降级处理")
        return ""
    except Exception as e:
        print(f"[WorldBuilder] LLM调用失败: {e}")
        return ""


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
    return json.loads(t)


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
) -> tuple[str, int, list, WorldState]:
    """多Agent分层生成世界大纲→自评→修订→提取世界状态。

    返回: (大纲文本, 最终分数, 评分历史, WorldState对象)
    """
    api_key = api_key or settings.LLM_API_KEY
    base_url = base_url or settings.LLM_BASE_URL
    model = model_name or settings.LLM_MODEL_NAME
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    # P2修复：为世界生成增加宽松的评分基线，避免无限修订循环

    ref = f"\n## 参考剧本\n{reference_script}" if reference_script.strip() else ""
    pi = f"## 玩家设定\n{player_input}"
    sys_cfg = get_system(game_system)
    system_block = build_system_rule_block(game_system, custom_rules)
    pi += f"\n\n## 规则系统\n- 类型: {sys_cfg['label']}\n- 说明: {sys_cfg['description']}\n{system_block[:1800]}"

    # ── Step 1: 世界观与冲突核心 ──
    print("[WorldBuilder] Step 1/6: 世界观与冲突核心...")
    step1 = await _llm(client, model,
        "你是一位获奖奇幻小说家。创作深刻、独特的世界观。",
        STEP1_CONFLICT.format(player_input=pi, reference=ref), max_tokens=2000, temp=0.9, timeout=60)
    if not step1:
        return "世界生成超时——请重试或使用手动上下文。", 0, [], WorldState()

    # ── Step 2: 主线三幕结构 ──
    print("[WorldBuilder] Step 2/6: 主线三幕结构...")
    step2 = await _llm(client, model,
        "你是一位D&D冒险设计师。设计引人入胜的三幕结构。",
        STEP2_PLOT.format(world_context=step1), max_tokens=3000, temp=0.85, timeout=90)
    if not step2:
        step2 = f"(生成超时) 基于世界观的默认三幕结构。"

    # ── Step 3: NPC网络与支线 ──
    print("[WorldBuilder] Step 3/6: NPC网络与支线...")
    step3 = await _llm(client, model,
        "你是一位角色设计大师。创造有深度的NPC网络。",
        STEP3_NPC.format(world_context=step1, plot_context=step2), max_tokens=2500, temp=0.9, timeout=90)
    if not step3:
        step3 = f"(生成超时) 默认NPC配置。"

    # ── Step 4: 遭遇表 ──
    print("[WorldBuilder] Step 4/6: 遭遇表与隐藏内容...")
    step4 = await _llm(client, model,
        "你是一位D&D遭遇设计师。设计挑战与秘密。",
        STEP4_ENCOUNTERS.format(world_context=step1, plot_context=step2, npc_context=step3),
        max_tokens=2500, temp=0.85, timeout=90)
    if not step4:
        step4 = f"(生成超时) 默认遭遇配置。"

    # ── Step 5: 合并+评分 ──
    history = []
    print("[WorldBuilder] Step 5/6: 合并+自评...")
    merge_result = await _llm(client, model,
        "你是一位D&D模组主编。诚实评分，合理打分，不要过分苛刻。",
        MERGE_PROMPT.format(step1=step1, step2=step2, step3=step3, step4=step4),
        max_tokens=6000, temp=0.4, timeout=120)

    try:
        scored = _extract_json(merge_result)
    except (json.JSONDecodeError, KeyError):
        m = re.search(r'"total_score"\s*:\s*(\d+)', merge_result)
        s = int(m.group(1)) if m else 75
        scored = {"total_score": s, "scores": {}, "issues": [], "suggestions": [],
                  "merged_outline": f"{step1}\n\n---\n\n{step2}\n\n---\n\n{step3}\n\n---\n\n{step4}"}

    score = scored.get("total_score", 75)
    outline = scored.get("merged_outline", "")
    history.append({"iteration": 1, "score": score,
                    "issues": scored.get("issues", []),
                    "suggestions": scored.get("suggestions", [])})

    # ── 迭代修订 ──
    for rev in range(2, max_revisions + 2):
        if score >= target_score:
            break

        print(f"[WorldBuilder] 修订 {rev}/{max_revisions+1} (当前评分:{score})...")
        rev_result = await _llm(client, model,
            "你是一位严谨的D&D模组编辑。按照建议修改，提高质量。",
            REVISE_PROMPT.format(
                current_score=score, outline=outline,
                issues_suggestions=json.dumps({
                    "issues": scored.get("issues", []),
                    "suggestions": scored.get("suggestions", []),
                }, ensure_ascii=False)),
            max_tokens=6000, temp=0.5, timeout=120)

        try:
            rev_data = _extract_json(rev_result)
        except json.JSONDecodeError:
            break

        new_outline = rev_data.get("revised_outline", outline)
        if new_outline and len(new_outline) > 500:
            outline = new_outline

        # 自评新版本——不要太严格，合理评价
        rescore = await _llm(client, model,
            "你是一位公平的D&D模组评委。诚实评价，不过分苛刻也不故意放水。",
            f"新大纲:\n{outline[:4000]}\n\n请输出JSON: {{\"total_score\":数字(0-100)}}",
            max_tokens=500, temp=0.3, timeout=60)
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
    print("[WorldBuilder] Step 6/6: 提取结构化世界状态...")
    ws = WorldState(world_outline=outline)
    try:
        extract_result = await _llm(client, model,
            "你是一位数据分析师。从文本中提取结构化信息。只返回JSON。",
            EXTRACT_STATE_PROMPT.format(outline=outline[:8000]),
            max_tokens=4000, temp=0.3, timeout=90)
        state_data = _extract_json(extract_result)

        for n in state_data.get("npcs", []):
            ws.npcs.append(NpcEntry(
                name=n.get("name",""), race=n.get("race",""), role=n.get("role",""),
                location=n.get("location",""), attitude=n.get("attitude","中立"),
                personality=n.get("personality",""), motivation=n.get("motivation",""),
                secret=n.get("secret",""), relation_to_plot=n.get("relation_to_plot",""),
            ))
        for p in state_data.get("plot_flags", []):
            ws.plot_flags.append(PlotFlag(
                key=p.get("key",""), status=p.get("status","未触发"),
                description=p.get("description",""),
            ))
        for l in state_data.get("locations", []):
            ws.locations.append(LocationEntry(
                name=l.get("name",""), description=l.get("description",""),
                secrets=l.get("secrets",""),
            ))
        ws.world_rules = state_data.get("world_rules", "")
    except Exception:
        pass  # 提取失败不影响核心流程

    return outline, score, history, ws
