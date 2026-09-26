"""系统提示装配：规则块、世界/记忆上下文、模块指令与压缩模式。

从 `backend/engine/dm_prompts.py` 拆出。这里只做「拼接」，不调模型、不写状态；
角色卡摘要来自 dm_character_info，父模块 dm_prompts 只做再导出。
"""
from __future__ import annotations

import re

from backend.engine.dm_character_info import _play_mode, build_character_info
from backend.engine.game_systems import build_stat_glossary, build_system_rule_block
from backend.engine.prompt_texts import (
    COMPACT_DM_DECISION_PROMPT, COMPACT_DM_PROMPT, DM_DECISION_PROMPT, SYSTEM_PROMPT,
)
from backend.engine.session import GameSessionState
from backend.engine.tool_shims import _game_system
from backend.skills import get_skill
from backend.skills.prompts import (
    COC_DECISION_PROMPT, COC_SYSTEM_PROMPT, CUSTOM_DECISION_PROMPT, CUSTOM_SYSTEM_PROMPT,
    DND4E_DECISION_PROMPT, DND4E_SYSTEM_PROMPT,
)


def _extract_outline(text: str, max_chars: int = 1200) -> str:
    """将完整剧本/世界大纲压缩为 Markdown 大纲，保留章节结构完整性。"""
    lines = text.split("\n")
    out: list[str] = []
    current_len = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        is_heading = stripped.startswith("#")
        is_bullet = stripped.startswith("-") or stripped.startswith("*") or re.match(r"^\d+[.、)]", stripped)
        # 标题/要点/关键行优先保留；普通长段落只取首句
        if is_heading or is_bullet:
            line_out = stripped
        else:
            first_sentence = re.split(r"(?<=[。！？!?；;])", stripped)[0]
            line_out = first_sentence[:120]
        if current_len + len(line_out) + 1 > max_chars:
            if is_heading:
                out.append(line_out[: max_chars - current_len])
            break
        out.append(line_out)
        current_len += len(line_out) + 1
    return "\n".join(out)


def build_system_prompt(state: GameSessionState, retrieved_chunks: list | None = None,
                         dispatch_plan: dict | None = None,
                         subagent_brief: str = "",
                         memory_context_override: str | None = None) -> str:
    lite = _play_mode(state) == "lite"
    plan = dispatch_plan or {}
    focus_context = str(plan.get("focus_context", "") or "")
    tool_hint = str(plan.get("tool_hint", "") or "")
    omit_full_world = bool(plan.get("omit_full_world", False))
    module = str(plan.get("module", "narrative") or "narrative")
    focused = module != "narrative"
    char_info = build_character_info(state)
    # 记忆保护：focused 模块保留核心记忆（摘要/大事件/暗线/人物影响/世界事实），
    # 只去掉与 messages 重复的“最近发生的事”，避免剧情记忆缺失。
    if memory_context_override is not None:
        # 优先使用 LangGraph 短期记忆图 + EverOS 长期记忆检索的结果
        mem = memory_context_override
    elif not focused or module == "memory":
        mem = state.memory.build_context()
    else:
        mem = state.memory.build_essential_context()
    ws = getattr(state, 'world_state', None)
    world_state_text = ws.to_context_string() if ws else ""

    outline = state.character_info.get("world_outline", "")
    world = state.character_info.get("world_context", "")
    scenario_summary = state.character_info.get("scenario_summary", "")
    skill = get_skill(_game_system(state))
    # 精简模式只压缩"静态提示词 + 子 Agent 数"，**不再额外砍动态上下文**：
    # 实测（3 run × 3 回合重复测量）精简模式比深度模式贵 1.71 倍、慢 1.49 倍，
    # 根因正是砍掉动态上下文后主 DM 自己反复查工具——每多一轮就是一次全 schema 往返
    # （10k+ tokens），远比省下的那点上下文字符贵。
    summary_limit = skill.summary_limit
    outline_limit = min(1400, skill.outline_limit)
    world_state_limits = {
        "combat": 3000, "rules": 2400, "scene": 3200,
        "social": 2800, "memory": 2800, "graph": 1800,
    }
    world_state_limit = (
        world_state_limits.get(module, 2400) if omit_full_world else 3500
    )

    summary_block = f"## 剧本总结\n{scenario_summary[:summary_limit]}" if scenario_summary else ""
    if world_state_text:
        wc = f"{summary_block}\n## 世界状态\n{world_state_text[:world_state_limit]}" if summary_block else f"## 世界状态\n{world_state_text[:world_state_limit]}"
    elif outline:
        outline_block = outline[:outline_limit]
        wc = f"{summary_block}\n## 冒险大纲\n{outline_block}" if summary_block else f"## 冒险大纲\n{outline_block}"
    elif world:
        wc = f"{summary_block}\n## 剧本\n{world[:outline_limit]}" if summary_block else f"## 剧本\n{world[:outline_limit]}"
    else:
        wc = summary_block

    wsc = ws.to_context_compact() if ws else ""
    if omit_full_world:
        wsc = wsc[:1000]
    # 战斗名册由后端算出后直接给主 DM：准确数值不必再经"战斗战术顾问"子 Agent 复述
    if ws is not None and (module == "combat" or getattr(state, "in_combat", False)):
        from backend.engine.dm_brief import combat_roster_text
        roster = combat_roster_text(ws)
        if roster:
            wsc = f"{wsc}\n{roster}" if wsc else roster

    # 角色背景——用于AI生成符合角色身份的决策建议
    backstory = state.character_info.get("backstory", "")
    backstory_block = ""
    if backstory:
        backstory_block = f"\n## 角色背景（决策建议须参考此背景——建议的行动应符合角色的出身、性格和动机）\n{backstory[:200 if lite else 350]}"

    # 使用规则系统技能包：非 DND5e 使用紧凑提示词，避免发送 DND5e 巨型规则
    skill = get_skill(_game_system(state))
    if skill.system_prompt is None:
        base_prompt = (
            COMPACT_DM_PROMPT if focused else SYSTEM_PROMPT.format(
                character_info="",
                memory_context="",
                world_context="",
                world_state_compact="",
            )
        )
    elif skill.system_prompt == "DND4E":
        base_prompt = DND4E_SYSTEM_PROMPT
    elif skill.system_prompt == "COC":
        base_prompt = COC_SYSTEM_PROMPT
    else:
        base_prompt = CUSTOM_SYSTEM_PROMPT

    # 固定规则前缀：所有静态规则放在前面，动态上下文统一追加到末尾，
    # 这样同一会话/模式的 system prompt 前缀保持稳定，更容易命中 LLM prompt cache。
    sp = base_prompt
    skill_instructions = getattr(skill, "instructions", "")
    if skill_instructions:
        sp += f"\n\n## 规则系统技能包（{skill.name}）\n{skill_instructions[:1200]}"
    if focused:
        # 模块化回合不需要完整 5e/4e/COC 决策检查表，用紧凑版替代
        sp += COMPACT_DM_DECISION_PROMPT
    elif skill.system_prompt is None:
        sp += DM_DECISION_PROMPT
    elif skill.system_prompt == "DND4E":
        sp += DND4E_DECISION_PROMPT
    elif skill.system_prompt == "COC":
        sp += COC_DECISION_PROMPT
    else:
        sp += CUSTOM_DECISION_PROMPT
    sp += _mode_instructions(state, focused)
    # 解离详细规则：只有规则/战斗模块才携带完整规则与数值表，其它模块用精简提示并依赖工具查询
    module_needs_full_rules = focused and module in ("rules", "combat")
    if module_needs_full_rules:
        sp += build_system_rule_block(
            _game_system(state),
            state.character_info.get("custom_rules", ""),
        )
    else:
        sp += """
## 规则速查（精简）
- 本回合不携带完整规则表；需要具体规则/数值/DC 时，使用游戏规则或骰子工具查询后按结果执行。
"""
    sp += """
## DM 权限与职责（你是主持人，不是旁观者）
- 你拥有主持权限：可以新增/修改 NPC、地点、生物、地图、世界状态、旗标和玩家状态。
- 使用这些权限前必须先通过工具调用，并在 reason 中说明原因。
- 新增内容必须符合当前规则系统、剧本设定与数值合理性。
- 不要滥用权限替玩家做决定；不要暴露 DM 后台信息给玩家。
- 每次修改后通过 update_scene / journal_update 保持玩家可见信息同步。

## 主 DM 的核心使命
- 你的核心产出永远是：角色扮演、生动的故事、真实的世界反应。数值与规则是支撑，不是主角。
- 每轮至少给出一个具体可感的动作/感官细节，并让世界对玩家行动产生后果。
- 规则、检索、记忆核对以专家简报和工具结果为准；你不再需要自己做长文分析。
"""
    sp += """
## 玩家可见文本硬性规则
- 禁止输出主持人内心独白或幕后说明，例如：“我先调出战力卡”“我先确认”“让我先看看”“我来结算这轮”等。
- 禁止在正文中直接判定命中/伤害/成功/失败。所有战斗攻击、伤害、属性检定、DC 等必须通过 dice_roll / combat_round 等工具产生数值，并把骰子/加减值/AC/DC/HP变化写入结果。
- 工具/数值结算以事件化、叙事化的方式呈现；不要向玩家解释“我正在调用工具”。
- 不要跳过战斗过程直接给出“成功/失败”结论。
- 每次 dice_roll / combat_round 等工具调用后，必须继续输出对应剧情叙事：动作、反应、环境、后果；不能只停留在数值或事件摘要。
- 战斗工具分工：combat_round 只结算玩家行动；敌人进攻使用 enemy_attack 工具在敌人回合单独结算，不要写成“玩家受击立刻反伤”的自动反击。
- 多敌战斗：每次 combat_round 的 enemy_names 传入当前全部敌人名单（含未攻击者），enemy_name 为本次实际目标；敌人回合逐个调用 enemy_attack。
- 先攻提示：后端在战斗开始时推送 `[系统-先攻]`（先攻顺序 / 当前该谁 / 谁还没动 / 第几轮）。
  以它为准安排叙事顺序；提示里说某单位"本轮回合用尽"时，不要再让它行动，
  也不要为了重掷失败结果而声明额外行动——合法的多段攻击/动作如潮/传奇动作/时间暂停
  请用 action_source 声明来源，由后端账本判定；突袭时在首次攻击工具传 surprise=true（后端锁对方首轮行动，警觉/免疫者除外）。
- 伤害类型与抗性（后端算，不要自己算）：敌人攻击请传 damage_type（爪牙撕咬/短剑=穿刺，
  爪击/钝器=钝击，刀剑=挥砍，法术按元素名）；范围伤害（吐息/火球/陷阱）用 save_damage，
  玩家可写进 targets（"你"或角色名），后端会掷玩家豁免并套用抗性/免疫/易伤与临时生命值。
- 毒素/毒药（毒酒、毒气、毒蛇咬伤、毒镖、淬毒武器、怪物毒液）一律用 apply_poison 结算：
  一次给出体质豁免、毒素伤害与「中毒」状态，并自动识别抗毒（矮人坚韧、抗毒药剂等）。
  不要只在叙事里写"你喉咙发紧、分不清是毒还是酒"而不结算——玩家要能在状态面板上对上。
- 玩家获得或失去抗性时用 update_state 写结构化字段，不要只写在叙事里：
  damage_resistances_add / damage_immunities_add / damage_vulnerabilities_add（移除用 _remove，
  整组替换直接用同名字段）。例：`update_state(changes={{"damage_resistances_add": ["火焰"]}})`。
- 战场态势（位置与掩体）用 set_tactical_state 登记一次即可：
  band=engaged(缠斗)/near(约30尺)/far(约120尺)/out(脱离)，cover=none/half(+2)/three_quarters(+5)/full。
  后端会自动给掩体加 AC 与敏捷豁免、拦下够不到的攻击、并提示"脱离缠斗会引发借机攻击"；近战够不到时不要硬写命中——用 close_distance=true 声明接近，或以远程/法术手段处理。
- 光照用 update_scene 写 light=明亮|微光|黑暗（可加 light_source=火把/月光/无光）：进洞、点火把、
  熄灯、入夜、走到阳光/阴影里都要更新。后端据此判定——黑暗里没有黑暗视觉的生物看不见
  （攻击劣势、被打有优势），别人也看不见它（可以直接藏）；微光下依赖视觉的察觉有劣势（被动 -5）。
- 追逐（有人逃跑/被追、翻墙、钻人群、甩开追踪）用 resolve_chase 记账：追与被追每回合的冲刺都调
  action=dash（免费次数 = 3 + 体质调整值，超出后后端掷体质豁免、失败力竭 +1）；
  想真正脱身必须 action=escape（隐匿对抗追兵被动察觉，成功才结束追逐并清零计数）。
  不要用叙事直接宣布"你甩掉了他们"或"他们追上来了"——冲几次、跑没跑掉都由后端判定。
- 攻击优势/劣势（后端算）：combat_round / enemy_attack 会先按状态（目盲/中毒/俯卧/束缚/麻痹/隐形）、力竭、目标俯卧与近战/远程、长射程、特长（神射手/弩专家/擒抱）自动判定；常规情况不要传 advantage。只有包抄、高台、特定法术/生物特性等未结构化来源，才传 advantage + advantage_reason。
- 对抗动作（擒抱/推撞/摔倒/挣脱）必须用 resolve_contest 掷对抗检定，不要让叙事抢在工具前面：
  写成"试图抓住/想把它按倒"，成功与否与「擒抱/俯卧」状态一律以后端返回为准，不要先写"已经抓住了"再补判。
- 时间与补给：赶路/搜索/守夜/等待必须调用 advance_time（hours=…/minutes=…，夜间加 light_source）。
  后端会更新日数与时刻、跨天扣除 1 份口粮+1 份饮水、缺补给累积力竭（1 级检定劣势 /
  3 级攻防劣势 / 6 级死亡），并按 1 支/小时扣除火把。短休/长休用 take_rest（自带 1 小时/8 小时）。
  旅行时加 pace=fast/normal/slow：后端按天累计里程，超过 8 小时后每小时掷体质豁免（失败力竭 +1）。
  不要把"过了三天"只写进叙事——玩家状态面板要能对上。
  用 update_scene 改 current_time 只能改叙述措辞；如果时间确实前进（例如从清晨到入夜），
  仍要调用 advance_time，否则日数/口粮/力竭都不会动（后端会尝试按叙述时间校准并在返回里说明）。
"""
    if getattr(state, "resumed", False):
        sp += """
## 会话状态：读档恢复
- 这是从存档恢复的会话，前端已加载完整对话历史。
- 请严格基于这段历史继续推进，不要重新开场、不要重置剧情、不要重复已经发生的事。
"""

    # 追逐进行中：只在账本非空时提醒。实测"一次性写死的提示词"会被后面的叙事需求挤掉，
    # 而这一段每回合都随当前状态出现，DM 才不会写着写着就把追逃当纯叙事。
    chase = getattr(state, "chase_dashes", None)
    if isinstance(chase, dict) and chase:
        who = "、".join(sorted(str(k) for k in chase))
        sp += f"""
## 进行中的追逐（必须继续记账）
- 参与者的冲刺计数：{who} 已经各有一次以上冲刺（键为角色名，值为已冲次数）。
- 本回合只要还在跑或追，就要调 `resolve_chase(action="dash", actor="谁")`；
  想脱身必须调 `action="escape"`（隐匿对抗追兵被动察觉）并成功；
  追丢了/不追了用 `action="end"` 清零。
- 不要用叙事直接宣布"追上了""甩掉了"——冲几次、跑没跑掉都由后端判定。
"""

    # 动态上下文统一放在静态规则之后
    mem_text = mem if mem.strip() else "冒险刚启。篝火刚点起来，第一颗骰子还在你的掌心。"
    if lite:
        mem_text = mem_text[:800]
    elif focused and module != "memory":
        mem_text = mem_text[:1200]
    else:
        mem_text = mem_text[:3000]
    sp += f"\n\n## 当前角色\n{char_info}"
    if module_needs_full_rules:
        sp += f"\n\n## 数值含义速查\n{build_stat_glossary(_game_system(state))}"
    else:
        sp += "\n\n## 数值含义速查（精简）\n- 属性/技能/特性等数值以规则工具返回为准，不要凭空臆造。"
    sp += backstory_block
    if subagent_brief:
        # 专家简报覆盖规则/战斗/场景/记忆/图谱，主提示词不再重复塞完整长文；
        # 但保留剧本背景与紧凑世界状态，让主 DM 仍有世界操控权。
        sp += f"\n\n## 本回合专家简报（并发专业子Agent已甄别）\n{subagent_brief[:3000]}"
        sp += ("""
\n## 专家简报使用规则
- 先核对每个任务的完成状态。失败、超时和未完成任务的文字不代表已结算；以执行记录和当前世界状态为准，补全剩余动作。
- 简报中的【仅DM可见】信息只能用于你裁决与推进剧情，绝不能直接展示给玩家。
- 不要在玩家可见文本中出现“专家”“子Agent”“后台分析”“简报”等字眼。
- 你是唯一叙事者与最终裁决者：简报只提供弹药，正文、语气、节奏、戏剧张力由你负责。""")
        if ws and getattr(ws, "scene", None):
            cur = ws.scene.current_location
            cur_time = ws.scene.current_time or f"第{ws.scene.day_count}天"
            if cur:
                sp += f"\n\n## 当前场景（同步）\n{cur} · {cur_time} · {ws.scene.weather}"
        if wc:
            sp += f"\n\n## 剧本/世界背景（同步）\n{wc[:1600]}"
        if wsc:
            sp += f"\n\n## 世界状态精简（主DM世界操控用）\n{wsc[:1500]}"
    else:
        sp += f"\n\n## 记忆上下文\n{mem_text}"
        if wc:
            sp += f"\n\n## 世界上下文\n{wc}"
        if wsc:
            sp += f"\n\n## 世界状态精简\n{wsc}"
    scenario_id = state.character_info.get("scenario_id", "")
    sp += "\n\n## 当前剧本约束"
    if scenario_id:
        sp += f"\n- 当前剧本ID: {scenario_id}"
    sp += "\n- 所有叙事必须严格贴合当前剧本的世界观、人物、地点、暗线与基调；不要脱离剧本自由发挥。"
    sp += "\n- 如果玩家提及剧本中不存在的人物/地点/事件，应引导其在剧本内寻找、调查或确认引入，而不是直接凭空添加。"
    sp += "\n- 地点/NPC/剧情信息只有在玩家通过探索、检定或剧情推进真正接触后才对玩家可见；不要一次性暴露后台设定。"
    if retrieved_chunks:
        chunk_count = 3 if lite else 5
        chunk_chars = 300 if lite else 500
        if focused:
            if module == "rules":
                chunk_count, chunk_chars = 5, 450
            elif module == "combat":
                chunk_count, chunk_chars = 3, 350
            else:
                chunk_count, chunk_chars = 2, 250
        sp += "\n\n## 检索到的设定/规则细节（按需使用，优先于你的记忆）\n"
        for item in retrieved_chunks[:chunk_count]:
            sp += f"\n- [{item.get('title','')}]({item.get('source','')}) {item.get('text','')[:chunk_chars]}"
    if focus_context:
        sp += f"\n\n## 本回合模块焦点（主 Agent 分发）\n{focus_context}"
        if tool_hint:
            sp += f"\n- 推荐工具：{tool_hint}"
    if getattr(state, "bestiary_overrides", None):
        sp += "\n\n## 本局生物图鉴临时覆写（优先级高于知识库）\n"
        for name, changes in state.bestiary_overrides.items():
            sp += f"\n- {name}: {changes}"
    if getattr(state, "city_overrides", None):
        sp += "\n\n## 本局城市/地点临时覆写（优先级高于知识库）\n"
        for name, changes in state.city_overrides.items():
            sp += f"\n- {name}: {changes}"
    return sp


# ═══════════════════════════════════════════════════════════════
# 工具执行
# ═══════════════════════════════════════════════════════════════

# 工具分发/写锁/笔记推送/同回合去重已抽到 backend.engine.tool_executor；
# 这里保留同名再导出，原有调用方与测试的 patch 目标保持有效。


def _mode_instructions(s: GameSessionState, focused: bool = False) -> str:
    """根据游玩模式生成附加指令，控制 token 消耗与扮演深度。"""
    mode = _play_mode(s)
    if focused:
        return """
模块化回合：
- 聚焦本回合模块目标，不展开无关背景与完整世界设定。
- 输出更紧凑：1-3段，每段不超过4句。
- 工具调用只执行本模块必需项。
"""
    if mode == "lite":
        return """
===============================================================================
精简模式（玩家选择：性价比玩法）
===============================================================================
- 叙事长度：每轮正文控制在80-160字，开场白控制在120-200字。
- 描写密度：保留最关键的感官细节与动作，不需要展开每个环境的物理量。
- 工具调用：只调用当前行动必需的规则工具；不要为了“仪式感”额外调用。
- 决策建议：每次给出2-3个简洁选项，每个选项不超过25字。
- 战斗节奏：压缩到1-2句/轮，快速结算，减少重复环境描写。
- 目标：在明显更少的token消耗下，仍然保留完整的D&D规则、选择权和剧情推进。
"""
    return """
===============================================================================
深度模式（玩家选择：高token高深度扮演）
===============================================================================
- 叙事长度：每轮正文保持250-500字，开场白300-500字。
- 描写密度：严格执行L节——物理量、至少两种感官、环境活性、角色微表情。
- 工具调用：完整执行B2工具顺序，场景/检定/记忆/世界状态都不省略。
- 决策建议：每次给出3-4个选项，每个选项包含风险与回报的细节。
- 战斗节奏：按B3节完整描写首轮与末轮，中段保留关键动作链条。
- 目标：用更高token消耗换取更深的人物弧光、世界沉浸与戏剧张力。
"""


# ── 提示词文本已拆到 prompt_texts，这里再导出保持既有 import ──
