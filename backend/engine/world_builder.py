import json, re

from dataclasses import dataclass, field

from openai import AsyncOpenAI

from backend.config import settings

from backend.engine.world_state import NpcEntry, PlotFlag, LocationEntry, WorldState

from backend.engine.game_systems import build_system_rule_block, get_system

from backend.engine.llm_utils import strip_refusal as _strip_refusal

from backend.engine.prompt_guard import extract_json_object, sanitize_user_text

from backend.engine.agent_graph import run_extraction_agent

from backend.knowledge_base import get_knowledge_base



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

    # 提示注入防护：清洗所有用户可控文本后再送入 LLM
    player_input = sanitize_user_text(player_input)
    reference_script = sanitize_user_text(reference_script)
    custom_rules = sanitize_user_text(custom_rules)
    custom_classes = [sanitize_user_text(x) for x in (custom_classes or []) if sanitize_user_text(x)]
    custom_skills = [sanitize_user_text(x) for x in (custom_skills or []) if sanitize_user_text(x)]
    if extra_attributes:
        extra_attributes = {str(k): sanitize_user_text(str(v)) for k, v in extra_attributes.items()}

    # LLM 出错时把原因回传给上层（前端可显示）
    def _llm_error(msg: str):
        if progress_callback is not None:
            progress_callback("LLM警告", 0, f"LLM出错: {msg}")

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
        await _with_knowledge_async(STEP1_CONFLICT.format(style_directive=style_directive, player_input=pi, reference=ref), "世界观 冲突 势力 阵营 魔法 社会", game_system, 3, username),
        max_tokens=6000, temp=0.9, timeout=180, thinking_strength=thinking_strength, token_callback=token_callback, error_callback=_llm_error)
    if not step1:
        raise RuntimeError("世界生成失败：模型调用多次超时，请检查模型/网络后重试")

    # ── Step 2: 主线三幕结构 ──
    print("[WorldBuilder] Step 2/6: 主线三幕结构...")
    if progress_callback: progress_callback("编织主线三幕结构", 25, "正在设计三幕剧情、转折与结局...")
    step2 = await _llm(client, model,
        "你是一位TRPG冒险设计师。设计引人入胜的三幕结构。",
        await _with_knowledge_async(STEP2_PLOT.format(style_directive=style_directive, world_context=step1), "三幕结构 剧情节点 转折 结局", game_system, 3, username),
        max_tokens=9000, temp=0.85, timeout=180, thinking_strength=thinking_strength, token_callback=token_callback, error_callback=_llm_error)
    if not step2:
        step2 = "主线采用经典三幕结构：第一幕引入冲突，第二幕遭遇转折与背叛，第三幕迎来高潮与结局。具体情节建议结合世界观继续细化。"

    # ── Step 3: NPC网络与支线 ──
    print("[WorldBuilder] Step 3/6: NPC网络与支线...")
    if progress_callback: progress_callback("塑造NPC与支线网络", 40, "正在塑造NPC、势力与支线任务...")
    step3 = await _llm(client, model,
        "你是一位角色设计大师。创造有深度的NPC网络。",
        await _with_knowledge_async(STEP3_NPC.format(style_directive=style_directive, world_context=step1, plot_context=step2), "NPC 反派 动机 支线 关系", game_system, 3, username),
        max_tokens=9000, temp=0.9, timeout=180, thinking_strength=thinking_strength, token_callback=token_callback, error_callback=_llm_error)
    if not step3:
        step3 = "关键NPC网络：围绕核心冲突设置至少五名角色，包含盟友、对手与隐藏敌意的中立者，并安排两条与主线隐性关联的支线。"

    # ── Step 4: 遭遇表 ──
    print("[WorldBuilder] Step 4/6: 遭遇表与隐藏内容...")
    if progress_callback: progress_callback("布置遭遇与隐藏内容", 55, "正在设计遭遇、陷阱、宝物与秘密...")
    step4 = await _llm(client, model,
        "你是一位TRPG遭遇设计师。设计挑战与秘密。",
        await _with_knowledge_async(STEP4_ENCOUNTERS.format(style_directive=style_directive, world_context=step1, plot_context=step2, npc_context=step3), "遭遇 战斗 陷阱 魔法物品 秘密", game_system, 3, username),
        max_tokens=9000, temp=0.85, timeout=180, thinking_strength=thinking_strength, token_callback=token_callback, error_callback=_llm_error)
    if not step4:
        step4 = "遭遇与隐藏内容：设计五场类型各异的遭遇（战斗、社交、探索、陷阱），三处秘密区域，以及一件带有背景故事的独特宝物。"

    # ── Step 5: 合并+评分 ──
    history = []
    print("[WorldBuilder] Step 5/6: 合并+自评...")
    if progress_callback: progress_callback("合并大纲并自评", 70, "评委正在审阅四个部分并合并...")
    merge_result = await _llm(client, model,
        "你是一位TRPG模组主编。诚实评分，合理打分，不要过分苛刻。",
        MERGE_PROMPT.format(style_directive=style_directive, step1=step1, step2=step2, step3=step3, step4=step4),
        max_tokens=16000, temp=0.4, timeout=180, thinking_strength=thinking_strength, token_callback=token_callback, error_callback=_llm_error,
        disable_thinking=True)

    try:
        scored = _extract_json(merge_result)
    except (json.JSONDecodeError, KeyError):
        print("[WorldBuilder] 合并+自评输出无法解析（多因输出被上限截断），改用四步结果拼接大纲")
        m = re.search(r'"total_score"\s*:\s*(\d+)', merge_result)
        s = int(m.group(1)) if m else 75
        scored = {"total_score": s, "scores": {}, "issues": [], "suggestions": [],
                  "merged_outline": f"{step1}\n\n---\n\n{step2}\n\n---\n\n{step3}\n\n---\n\n{step4}"}

    score = scored.get("total_score", 75)
    outline = scored.get("merged_outline", "")
    # 健壮性：如果模型返回的 merged_outline 为空，则用四个分步结果拼接，避免生成空剧本
    if not outline or not outline.strip():
        print("[WorldBuilder] 合并结果缺少 merged_outline，改用四步结果拼接大纲")
        outline = f"{step1}\n\n---\n\n{step2}\n\n---\n\n{step3}\n\n---\n\n{step4}"
    else:
        print(f"[WorldBuilder] 合并大纲成功: {len(outline)}字（四步原始合计 {len(step1)+len(step2)+len(step3)+len(step4)}字）")
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
            max_tokens=16000, temp=0.5, timeout=180, thinking_strength=thinking_strength, token_callback=token_callback, error_callback=_llm_error)

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
            max_tokens=4000, temp=0.3, timeout=180, thinking_strength=thinking_strength, token_callback=token_callback, error_callback=_llm_error,
            disable_thinking=True)
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
    # 使用 LangGraph 编排专业AGENT：提取 -> 严格校验 -> 错误回传修正
    async def extract_fn():
        result = await _llm(client, model,
            "你是一位专门抽取TRPG角色、地点与剧情旗标的专家。只返回JSON。",
            EXTRACT_STATE_FALLBACK_PROMPT.format(outline=outline[:20000]),
            max_tokens=16000, temp=0.2, timeout=180, thinking_strength=thinking_strength, token_callback=token_callback, error_callback=_llm_error,
            disable_thinking=True)
        if not result:
            return {"npcs": [], "locations": [], "plot_flags": [], "world_rules": ""}
        try:
            data = _extract_json(result)
        except Exception:
            return {"npcs": [], "locations": [], "plot_flags": [], "world_rules": ""}
        # 截断兜底：JSON 输出被输出上限截断时，排在最后的 plot_flags 会整段丢失；
        # 而“空数组”能通过字段校验，不会触发修正循环，因此这里主动补提取一次。
        if _needs_plot_flag_backfill(data):
            extra_flags = await _extract_plot_flags(
                client, model, outline, thinking_strength, token_callback, _llm_error)
            if extra_flags:
                data["plot_flags"] = extra_flags
                print(f"[WorldBuilder] 剧情旗标疑似被输出截断，已补提取 {len(extra_flags)} 条")
            else:
                print("[WorldBuilder] 警告：提取结果没有任何剧情旗标，请检查大纲或输出预算")
        return data

    async def fix_fn(data: dict, errors: list[str]) -> dict:
        fix_prompt = (
            EXTRACT_STATE_FALLBACK_PROMPT.format(outline=outline[:20000])
            + "\n\n## 上次输出\n"
            + json.dumps(data, ensure_ascii=False)[:4000]
            + "\n\n## 校验错误\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\n\n请输出修正后的完整JSON。"
        )
        result = await _llm(client, model,
            "你是专业TRPG字段校验员。根据错误修正JSON。只输出修正后的完整JSON。",
            fix_prompt,
            max_tokens=16000, temp=0.1, timeout=180, thinking_strength=thinking_strength, token_callback=token_callback, error_callback=_llm_error,
            disable_thinking=True)
        if not result:
            return data
        try:
            fixed = _extract_json(result)
        except Exception:
            return data
        return fixed if fixed else data

    try:
        graph_result = await run_extraction_agent(
            extract_fn=extract_fn,
            validate_fn=_validate_extracted_state,
            fix_fn=fix_fn,
            max_retries=2,
        )
        state_data = graph_result.get("state_data", {})
        errors = graph_result.get("errors", [])
        if errors:
            print(f"[WorldBuilder] 专业AGENT最终仍有校验错误: {errors}")
    except Exception as e:
        print(f"[WorldBuilder] 专业AGENT流程异常: {e}")
        state_data = {}

    if state_data:
        print(f"[WorldBuilder] 专业AGENT提取完成: NPC={len(state_data.get('npcs', []))}, 地点={len(state_data.get('locations', []))}, 旗标={len(state_data.get('plot_flags', []))}")

    # 应用提取结果
    if state_data:
        for n in state_data.get("npcs", []):
            level, ac, hp, max_hp = _derive_npc_stats(n)
            ws.npcs.append(NpcEntry(
                name=n.get("name",""), race=n.get("race",""), role=n.get("role",""),
                location=n.get("location",""), attitude=n.get("attitude","中立"),
                personality=n.get("personality",""), motivation=n.get("motivation",""),
                secret=n.get("secret",""), relation_to_plot=n.get("relation_to_plot",""),
                level=level, ac=ac, hp=hp, max_hp=max_hp,
                attributes=n.get("attributes") or {}, skills=n.get("skills") or [],
                traits=n.get("traits") or [], equipment=n.get("equipment") or [],
                related_locations=n.get("related_locations", []),
                related_npcs=n.get("related_npcs", []),
                related_creatures=n.get("related_creatures", []),
                importance=n.get("importance", "minor"),
                discovered=False,
            ))
        for p in state_data.get("plot_flags", []):
            ws.plot_flags.append(PlotFlag(
                key=p.get("key",""), status=p.get("status","未触发"),
                description=p.get("description",""),
                visible=False,
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
                discovered=False,
            ))
        ws.creatures = []
        bestiary_ref = []
        try:
            from backend.media_manager import list_bestiary
            bestiary_ref = list_bestiary(username) or []
        except Exception:
            bestiary_ref = []
        for ci, c in enumerate(state_data.get("creatures", [])):
            c = _enrich_creature_from_bestiary(c or {}, bestiary_ref)
            ws.creatures.extend(_normalize_creature(c, ci))
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


# ── 再导出：既有调用方（世界/图鉴/测试）保持不变 ──
from backend.config import settings  # noqa: E402

# ── 输出预算自适应状态（进程级，唯一一份）──────────────────
# 默认取 settings.LLM_MAX_OUTPUT_TOKENS（实测 DeepSeek 端点接受 65536）；
# 不同 OpenAI 兼容网关上限不同，被拒绝时自动降级到 FALLBACK 并记住，避免每次都撞 400。
# 放在编排模块里：world_llm._llm 惰性读写，测试/外部也能直接复位。
_DEFAULT_OUTPUT_CAP = int(getattr(settings, "LLM_MAX_OUTPUT_TOKENS", 32768) or 32768)
_OUTPUT_CAP_FALLBACK = int(getattr(settings, "LLM_MAX_OUTPUT_TOKENS_FALLBACK", 8192) or 8192)
_output_cap = _DEFAULT_OUTPUT_CAP


def _current_output_cap() -> int:
    return _output_cap


from backend.engine.world_creatures import (  # noqa: E402
    _CN_NUM,
    _derive_npc_stats,
    _enrich_creature_from_bestiary,
    _normalize_creature,
    _parse_creature_count,
)
from backend.engine.world_prompts import (  # noqa: E402
    EXTRACT_STATE_FALLBACK_PROMPT,
    EXTRACT_STATE_PROMPT,
    MERGE_PROMPT,
    PLOT_FLAGS_ONLY_PROMPT,
    REVISE_PROMPT,
    STEP1_CONFLICT,
    STEP2_PLOT,
    STEP3_NPC,
    STEP4_ENCOUNTERS,
)
from backend.engine.world_llm import (  # noqa: E402
    _is_max_tokens_limit_error,
    _llm,
    _thinking_extra_body,
    _with_knowledge,
    _with_knowledge_async,
)
from backend.engine.world_state_extract import (  # noqa: E402
    _dedupe_headings,
    _extract_json,
    _extract_plot_flags,
    _needs_plot_flag_backfill,
    _programmatic_score,
    _validate_extracted_state,
)
