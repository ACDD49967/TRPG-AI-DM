"""模块布局守护：拆分后的职责边界、再导出完整性、装配层约束与文件体积棘轮。

背景：把大文件拆成 combat / character_state / dm_prompts / routers 之后，调用方依赖
dm_agent 的再导出；一旦搬移时漏掉某个顶层语句或 import，就会出现 AttributeError/NameError。
这里用一组断言把边界钉住，并用"体积上限"防止大文件重新膨胀。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 体积棘轮：只允许变小，不允许重新膨胀（拆分完成后同步下调）
SIZE_CEILINGS = {
    # dm_agent 只留编排：运行期工具 → dm_runtime，工具处理器 → session/media/world/graph_tools
    # dm_agent 只留主循环编排；开场白/记忆压缩/子 Agent 调度已拆出
    # 回合准备阶段（检索/记忆/委派）搬到 dm_turn；dm_agent 只留提示装配与流式循环
    # 590：补上 narrative_polish / post_turn 阶段计时（此前这两段模型调用没有阶段归属）
    # 560：消息装配拆到 dm_messages（系统提示词 + 历史 + 系统提示，纯装配）
    "backend/engine/dm_messages.py": 100,
    "backend/engine/dm_turn.py": 295,
    "backend/engine/dm_opening.py": 200,
    "backend/engine/dm_subagents.py": 95,
    "backend/engine/dm_memory.py": 75,
    # prompt_texts 只留短提示词；430 行的 SYSTEM_PROMPT 常量 → prompt_system
    "backend/engine/prompt_texts.py": 165,
    "backend/engine/prompt_system.py": 450,
    # world_state 只留 WorldState 的字段与查询/变更入口；模型/IO/上下文/维护已拆出
    # （顶部重复的 dataclass/清洗函数副本已删除，改为从 world_models/world_names 再导出）
    # 268：+NPC 专注字段（怪物施法者）
    # 270：SceneInfo +light / light_source（光照等级与光源）
    "backend/engine/world_models.py": 270,
    "backend/engine/world_names.py": 60,
    # 143：+world_to_dict（存档与世界落盘共用同一份快照构造）
    # 145：场景光照读写
    "backend/engine/world_io.py": 145,
    "backend/engine/world_context.py": 175,
    "backend/engine/world_maintenance.py": 250,
    # 其余大文件也纳入棘轮（此前只覆盖被拆过的文件）
    # world_builder 只留 build_world 编排；生物/提示词/LLM 管道/结构化提取已拆出
    "backend/engine/world_builder.py": 400,
    "backend/engine/world_creatures.py": 135,
    "backend/engine/world_prompts.py": 230,
    "backend/engine/world_llm.py": 240,
    "backend/engine/world_state_extract.py": 150,
    # scenario_importer 只做门面再导出；读取/切分/LLM 切分/生成已拆出
    "backend/scenario_text_io.py": 135,
    "backend/scenario_split.py": 220,
    "backend/scenario_llm_split.py": 225,
    # 子 Agent：运行层留在 focused_subagents，简报层 → dm_brief，公共类型 → subagent_types
    # （测试 patch 的 focused_subagents.run_tool_subagent / get_agent_skill 必须仍在原模块）
    # 并发委派预算 3 → 4（含理由注释），文件 391 → 397
    # 424：总结轮精简（见 SKILL 5.82）+ fast-settle（结算型任务省掉总结轮，见 5.85）
    # dm_brief 收编了委派上下文装配（assemble_brief_context + 图谱上下文），dm_turn 相应减到 271
    # 398：rules/combat 的 rules 任务加 fast_settle 标记
    "backend/engine/subagent_types.py": 45,
    # game_systems 只留门面再导出；规则系统内容按域拆到 rules_* / starter_kits
    "backend/engine/game_systems.py": 65,
    # 250：自定义规则块补"判定骰以本局规则为准"的硬要求
    "backend/engine/rules_system.py": 250,
    "backend/engine/rules_5e.py": 210,
    "backend/engine/rules_4e.py": 95,
    "backend/engine/rules_coc.py": 70,
    "backend/engine/rules_progress.py": 95,
    "backend/engine/starter_kits.py": 90,
    # knowledge_base 只做类装配/单例/兼容再导出；文本辅助 → knowledge_text，
    # 文档 CRUD → knowledge_docs，混合检索 → knowledge_retrieval
    "backend/knowledge_base.py": 95,
    "backend/knowledge_text.py": 130,
    "backend/knowledge_docs.py": 250,
    # 350 → 229：纯计算（索引/TF-IDF/权重/父块回填）→ knowledge_rank，
    # 内置规则种子 → knowledge_seed（本 mixin 继承它）
    "backend/knowledge_retrieval.py": 229,
    "backend/knowledge_rank.py": 88,
    "backend/knowledge_seed.py": 74,
    # 长期记忆：Markdown 记忆页 → memory_vault，检索打分 → memory_scoring
    "backend/memory_vault.py": 115,
    "backend/memory_scoring.py": 90,
    "backend/default_content_data/cities_dnd5e.py": 390,
    # 5 个惰性 shim 收拢到 tool_shims（各模块按需导入；顺带删掉 11 个死 shim）
    "backend/engine/tool_shims.py": 45,
    # 246：骰子裁判 → dice_tools；休息（5e 生命骰 / 4e 回复力短休）→ rest_tools
    # 275：+forget_memory（DM 也要能删掉记错的长期记忆）
    "backend/engine/session_tools.py": 275,
    "backend/engine/sanity_rules.py": 75,
    # 幸运兜底：COC 7e 上限 99 + 消耗 1:1 的强制提示，5e「幸运」专长长休重置
    "backend/engine/luck_rules.py": 95,
    # 4e 里程碑：遭遇结束计数（战斗 True→False），每两次 +1 行动点，长休清零
    "backend/engine/milestones.py": 95,
    # 工具 schema 按域拆出：tools.py 只留 DM_TOOLS 装配与再导出（顺序保持不变）
    "backend/engine/tool_schemas.py": 20,
    # 149：+FORGET_MEMORY_TOOL（长期记忆的删除入口）
    "backend/engine/tool_defs_world.py": 149,
    # 121：adjust_npc 增加 concentration / concentration_clear
    "backend/engine/tool_defs_lookup.py": 121,
    # 80：装配 apply_hazard（环境危害：坠落/严寒酷暑/窒息）
    # 81：再装配 resolve_trap（陷阱：被动察觉/搜查/解除 + 失败 5 点触发）
    # 82：再装配 resolve_stealth（潜行/隐藏）；83：再装配 resolve_contest（对抗动作）
    # 85：再装配 apply_poison（毒药/毒素）
    # 87：再装配 resolve_chase（追逐）
    "backend/engine/tools.py": 89,
    "backend/engine/hazards.py": 115,
    "backend/engine/tool_defs_hazard.py": 15,
    # 153 → 128：熟练加值/被动察觉抽到 perception_rules（潜行也要用同一份算法）
    # 138：+costs_player_action（解除机关/主动搜查才占动作，被动察觉不占）
    "backend/engine/trap_rules.py": 138,
    "backend/engine/tool_defs_trap.py": 26,
    # 潜行拆三段：数值与观察者 / 隐藏状态与暴露 / 判定流程（+ schema 与察觉共用算法）
    # 123：+costs_player_action（Hide 占动作，但 DM 让 NPC 潜行时不扣玩家的）
    # 135：+黑暗里直接藏（对方没有黑暗视觉时不掷骰）
    "backend/engine/stealth_rules.py": 135,
    # 132：被动察觉按光照修正（微光/黑暗 -5）
    "backend/engine/stealth_modifiers.py": 132,
    "backend/engine/stealth_state.py": 98,
    "backend/engine/tool_defs_stealth.py": 22,
    "backend/engine/perception_rules.py": 60,
    # 对抗动作（擒抱/推撞/逃脱）拆两段，加两个共用小模块：状态落卡、同回合去重保护
    # 171：真实探针里模型写过 contestant_a/contestant_b/contest_kind，加参数别名容错
    # 181：擒抱状态维护（谁抓着谁、倒下自动解除）抽到 grapple_state
    "backend/engine/contest_rules.py": 181,
    "backend/engine/grapple_state.py": 93,
    "backend/engine/contest_modifiers.py": 129,
    "backend/engine/tool_defs_contest.py": 27,
    # 68：+状态持续回合（毒药"中毒 1 分钟"要写 remaining_rounds）
    # 71：+extra 结构化附加字段（擒抱的 grappled_by）
    "backend/engine/condition_apply.py": 71,
    # 64：+resolve_chase（同回合重复冲刺等于白送一次免费冲刺）
    "backend/engine/tool_settlement.py": 64,
    # 光照等级与视觉（明亮/微光/黑暗 + 黑暗视觉 / 微光视觉）
    "backend/engine/light_rules.py": 156,
    # 毒药：抗毒识别 + apply_poison（复用 save_damage 管线，不再造第三份豁免/伤害实现）
    "backend/engine/poison_rules.py": 160,
    "backend/engine/tool_defs_poison.py": 26,
    # 追逐拆两段：冲刺计数与力竭落库 / 判定流程（+ schema）
    "backend/engine/chase_rules.py": 131,
    "backend/engine/chase_state.py": 118,
    "backend/engine/tool_defs_chase.py": 19,
    # 161：+力竭 1 级起检定劣势（后端直接套用，不再靠提示词）
    "backend/engine/dice_tools.py": 161,
    "backend/engine/rules.py": 230,
    # 法术类工具（检索/学习/遗忘/施法结算 + 时间停止）拆到 spell_tools
    # 330 → 42：写入 → media_tools_write，检索 → media_tools_search，卡片 → media_tools_cards
    "backend/engine/media_tools.py": 42,
    "backend/engine/media_tools_write.py": 96,
    "backend/engine/media_tools_search.py": 144,
    "backend/engine/media_tools_cards.py": 77,
    # 505：补角色笔记的增/改（add_note/update_note），删此前已有 remove_character_note
    "backend/engine/graph_tools.py": 220,
    # 237：行动经济（主/额外行动配额 + 4e 行动点记账）→ action_economy
    # 245：加 resolve_trap 处理器；247：同回合同参数重掷保护也覆盖 resolve_trap
    # 257：再加 resolve_stealth 处理器与"出手暴露"收口（清理逻辑在 stealth_state）
    # 257：同回合去重表搬到 tool_settlement，再加 resolve_contest 处理器与
    # "NPC 动手不扣玩家主行动"的判断（实际 256 行，低于上限）
    # 279：潜行/陷阱也进主行动账本，行动者判断交给各域（_action_cost_hook）
    # 283：+resolve_chase 处理器，并进玩家主行动（冲刺就是一次动作）
    "backend/engine/tool_executor.py": 284,
    "backend/engine/action_economy.py": 175,
    # 入口只做装配：路由已按域拆到 backend/routers/，这里只允许往下调
    "backend/main.py": 141,
    # 数据表按规则系统拆到 default_content_data/；门面只做再导出
    "backend/default_content.py": 15,
    "backend/default_content_bestiary.py": 15,
    "backend/default_content_cities.py": 15,
    # 内容库按域拆分：store（设施）+ maps / bestiary / spells
    "backend/media_manager.py": 170,
    # 345 → 207：内置内容播种流水线 → media_seed（media_store 用惰性转发保持 import 面；
    # 路径/元数据原语留在原地，因为测试直接 patch media_store.MEDIA_ROOT）
    "backend/media_store.py": 207,
    "backend/media_seed.py": 181,
    "backend/media_maps.py": 250,
    # 350 → 191：知识库 5etools 导入 + 4e PDF 解析 → media_bestiary_import
    "backend/media_bestiary.py": 191,
    "backend/media_bestiary_import.py": 175,
    # 法术库：内置数据 → media_spells_data，格式化规则 → media_spells_format
    # 355 → 210：内置 SRD 播种/导入 + 职业映射 → media_spells_srd
    "backend/media_spells.py": 210,
    "backend/media_spells_srd.py": 176,
    "backend/media_spells_data.py": 245,
    "backend/media_spells_format.py": 125,
    # combat 只留四个规则处理器；武器辅助/战斗快照/奖励与落库各成模块
    # 505：4e 行动点换额外行动时调 action_economy 扣点
    "backend/engine/combat_weapons.py": 75,
    "backend/engine/combat_state.py": 80,
    # 75：写回 HP 时顺带结算 NPC 专注（受伤掷骰、倒地中断）
    # 79：倒地时顺带解除它施加的擒抱（5e：擒抱者无法行动则擒抱结束）
    "backend/engine/combat_rewards.py": 79,
    "backend/engine/combat_targets.py": 190,
    # 310 → 166：伤害类型/文本收集 → damage_types，豁免加值推导 → damage_saves
    # 172：+「状态免疫」不再被当成伤害免疫（状态免疫：中毒 ≠ 毒素伤害免疫）
    "backend/engine/damage_rules.py": 172,
    "backend/engine/damage_types.py": 107,
    "backend/engine/damage_saves.py": 72,
    # 465：build_character_info 里为自定义系统补"本局自定义规则"一行（所有模块都要能看到）
    # character_state 只留 _exec_update_state；归一化/状态效果/装备/濒死各成模块
    # 345：补 inventory_update（物品"改"，add 对已存在物品是 no-op）
    # 幸运兜底接进状态更新路径（+5 行）；法术位写回抽到 spell_slots 后缩回 343
    # 法术位是"完整剩余值"字段：合并写回 + 按职业/等级上限收敛（此前能写成 99）
    "backend/engine/spell_slots.py": 70,
    # 134：+grappled_by（擒抱者倒下时据此自动解除）
    "backend/engine/character_normalize.py": 134,
    "backend/engine/character_conditions.py": 88,
    "backend/engine/character_equipment.py": 55,
    # 83：专注豁免改为后端掷骰（逻辑搬到 concentration.py），濒死流程变短
    "backend/engine/character_dying.py": 83,
    # 150：+NPC 专注（怪物施法者）受伤结算与 adjust_npc 分支
    "backend/engine/concentration.py": 150,
    # 角色生成实现搬到 backend/character_generation（原来一个 277 行的路由函数）
    "backend/routers/generate.py": 290,
    "backend/character_generation.py": 295,
    # 新局创建实现搬到 backend/game_setup（原来一个 342 行的路由函数）
    # 215：补 DELETE /api/game/{sid}（删会话要连世界状态文件一起清）
    "backend/routers/game.py": 215,
    # 上传流水线 → knowledge_tasks，文档→图鉴的 LLM 注入 → knowledge_llm
    "backend/routers/knowledge.py": 260,
    "backend/knowledge_tasks.py": 200,
    "backend/knowledge_llm.py": 135,
    # 两个机翻流水线（SRD 法术 / 地点与生物描述）搬到 backend/media_translate
    "backend/media_translate.py": 170,
    "backend/routers/models.py": 250,
    "backend/routers/tasks.py": 165,
    "backend/routers/saves.py": 145,
    "backend/routers/extensions.py": 145,
    "backend/routers/levelup.py": 125,
    # 90：补 DELETE /api/auth/user（删号 + 名下内容清理，实现见 backend/account_data）
    "backend/routers/auth.py": 90,
    "backend/account_data.py": 120,
    "backend/routers/characters.py": 65,
    "backend/routers/observability.py": 40,
    # world 只做世界/角色状态增删改查；会话设置已拆到 session_settings
    # 140：世界快照加 notes（角色视角笔记），供编辑面板读取
    "backend/routers/world.py": 140,
    "backend/routers/session_settings.py": 75,
    "backend/character_names.py": 70,
    # 拆分时整段复制过来的 import 块被脚本清掉（30 个前端文件 / 777 处）后，
    # 受影响的前端额度统一按清理后的实际行数重设（只允许继续变小）
    # StartScreen 只留流程与状态；数据表 → data/dndData，步骤 JSX → components/start/*
    # StartScreen 只留状态与流程；handler 已按域抽成 hooks
    # 剧本/世界生成整块 → start/useScenarioStudio；StartScreen 只留建角色与开局编排
    # 角色草稿（点购/COC/法术选择）→ start/useCharacterDraft；StartScreen 只留编排与开局
    # 四个步骤组件改从 StartWizardContext 取值（不再收 68-84 个 props）
    # 295：AI 生成角色/背景 与 开始冒险 两个动作 → start/useStartActions
    # 228：启动数据加载/配置持久化/错误 Toast/存档页刷新 → start/useStartBootstrap
    # 176：页头/步骤/说明书弹窗 → start/StartWizardShell
    "frontend/src/components/StartScreen.tsx": 176,
    "frontend/src/components/start/StartWizardShell.tsx": 43,
    "frontend/src/components/start/useStartBootstrap.ts": 92,
    "frontend/src/components/start/useStartActions.ts": 165,
    # context 类型改用各 hook 的 ReturnType 交集 + 显式局部项（74 行，含注释）
    "frontend/src/components/start/StartWizardContext.tsx": 80,
    "frontend/src/components/start/useCharacterDraft.ts": 160,
    # 163 → 19：连接/端点预设 → start/connectionSettings，向量模式与下载 → start/vectorSettings
    "frontend/src/components/start/useModelSettings.ts": 19,
    "frontend/src/components/start/connectionSettings.ts": 111,
    "frontend/src/components/start/vectorSettings.ts": 58,
    "frontend/src/components/start/modelDownloads.ts": 108,
    "frontend/src/components/start/AdventurePrepStep.tsx": 105,
    # 清掉从 StartScreen 复制来的死 import 后同步下调（每个文件 −11 行）
    # 状态从 StartScreen 搬进来（同时删掉 38 个 deps 的解构与死 import），净减
    # 85：知识库动作 → knowledge/kbActions，扩展包动作 → knowledge/extActions
    "frontend/src/components/start/useKnowledgeActions.ts": 85,
    # 178 → 15：查询/删除/播种/LLM 注入 → knowledge/kbQuery，备注/上传/取消 → knowledge/kbIngest
    "frontend/src/components/start/knowledge/kbActions.ts": 15,
    "frontend/src/components/start/knowledge/kbContext.ts": 27,
    "frontend/src/components/start/knowledge/kbQuery.ts": 57,
    "frontend/src/components/start/knowledge/kbIngest.ts": 108,
    "frontend/src/components/start/knowledge/extActions.ts": 91,
    # 再清掉多行 import 块里的死导入（各 −37 行），并让媒体状态搬进 useMediaActions
    # deps 从索引签名改成显式名单（缺 dep 会在编译期报错）
    # 208：保存时区分"更新当前卡"与"另存为新卡"，不再每次点保存都复制一张
    # 34：三个角色卡动作 → start/characterCardActions
    "frontend/src/components/start/useCharacterCardActions.ts": 34,
    "frontend/src/components/start/characterCardActions.ts": 119,
    "frontend/src/components/start/useMediaActions.ts": 100,
    # 71：读档成功后提示"已开始新会话"（后端会换新 session_id，避免玩家在旧标签页困惑）
    "frontend/src/components/start/useSaveActions.ts": 71,
    # 12：连接/模型 → settings/ConnectionSection，模式 → settings/PlayModeSection
    "frontend/src/components/start/ApiSettingsPanel.tsx": 12,
    "frontend/src/components/start/settings/ConnectionSection.tsx": 104,
    "frontend/src/components/start/settings/PlayModeSection.tsx": 46,
    "frontend/src/components/start/WizardNav.tsx": 52,
    "frontend/src/components/start/WizardFooter.tsx": 47,
    "frontend/src/data/dndData.ts": 110,
    # CharacterStep 只留编排；五个区块 → components/start/character/
    "frontend/src/components/start/CharacterStep.tsx": 115,
    "frontend/src/components/start/character/BaseInfoSection.tsx": 102,
    "frontend/src/components/start/character/SpeciesClassSection.tsx": 57,
    "frontend/src/components/start/character/SpellPickerSection.tsx": 92,
    "frontend/src/components/start/character/SkillPickerSection.tsx": 136,
    # 16：D&D/CoC/自定义属性块分别下沉
    "frontend/src/components/start/character/AttributeSection.tsx": 16,
    "frontend/src/components/start/character/attributes/DndAttributeSection.tsx": 82,
    "frontend/src/components/start/character/attributes/CocAttributeSection.tsx": 41,
    "frontend/src/components/start/character/attributes/CustomAttributeSection.tsx": 33,
    # ScenarioStep 只留编排与两个内联片段；三种模式的区块 → components/start/scenario/
    "frontend/src/components/start/ScenarioStep.tsx": 55,
    "frontend/src/components/start/scenario/ScenarioModeTabs.tsx": 30,
    "frontend/src/components/start/scenario/ExistingScenarioPicker.tsx": 55,
    "frontend/src/components/start/scenario/ScenarioGenerateForm.tsx": 86,
    "frontend/src/components/start/scenario/ScenarioRuleSystem.tsx": 45,
    "frontend/src/components/start/scenario/ScenarioSplitImport.tsx": 75,
    "frontend/src/components/start/scenario/ScenarioWorldProgress.tsx": 35,
    "frontend/src/components/start/scenario/ScenarioOutlinePanel.tsx": 60,
    # KnowledgeStep 只留编排；四个区块 → components/start/knowledge/
    "frontend/src/components/start/KnowledgeStep.tsx": 129,
    "frontend/src/components/start/knowledge/KbIngestSection.tsx": 118,
    "frontend/src/components/start/knowledge/VectorModelSection.tsx": 98,
    "frontend/src/components/start/knowledge/ExtensionsSection.tsx": 97,
    "frontend/src/components/start/knowledge/MediaSection.tsx": 96,
    # 游戏状态 store 只留装配与操作：类型 → gameTypes，契约/默认值/清洗 → gameStateShape
    # 156：叙事动作（token 缓冲/玩家消息/骰子/事件/决策提取）→ store/actions/narrativeActions
    "frontend/src/store/gameStore.ts": 156,
    "frontend/src/store/actions/narrativeActions.ts": 125,
    # 187：SceneInfo +light / light_source（顶栏光照）
    "frontend/src/store/gameTypes.ts": 187,
    # 220 → 143：默认值/干净会话 → initialSessionState，SSE 白名单与清洗 → statusWhitelist
    # 148：latestDiceRoll 补 advantage / advantage_note / display（弹窗要显示原因）
    "frontend/src/store/gameStateShape.ts": 148,
    "frontend/src/store/initialSessionState.ts": 54,
    "frontend/src/store/statusWhitelist.ts": 40,
    # SSE 钩子只留 EventSource 生命周期与重连；事件处理器表 → hooks/sseHandlers
    "frontend/src/hooks/useSSE.ts": 142,
    # 处理器表按叙事/状态/战斗三域下沉 → hooks/sse/*，入口只做组合
    "frontend/src/hooks/sseHandlers.ts": 20,
    "frontend/src/hooks/sse/handlerTypes.ts": 9,
    # 90：骰子事件透传 display/advantage/advantage_note 给前端徽章
    "frontend/src/hooks/sse/narrativeHandlers.ts": 90,
    # 79：期刊与 scene_update 两处都同步 light / light_source
    "frontend/src/hooks/sse/stateHandlers.ts": 79,
    # 90：pending_regen 保留在敌人快照里，避免再生中敌人让战斗块误关闭
    "frontend/src/hooks/sse/combatHandlers.ts": 90,
    # GameScreen 只留布局与弹窗编排；图谱布局/怪物格式化/编辑面板已拆出
    # GameScreen 只留布局与弹窗编排；六个 Modal 与工具/编辑面板已拆出
    # GameScreen 只留布局与弹窗编排；图谱状态/交互 → game/useGraphState
    # 图谱 → useGraphState、内容库（地图/图鉴/法术 + 机翻）→ useMediaLibrary
    # 131：写入动作（新增 NPC/地点/生物/法术 + 两处机翻）→ game/useMediaActions
    "frontend/src/components/game/useMediaLibrary.ts": 130,
    # 112：图谱过滤/排序/布局纯计算 → game/graphView
    "frontend/src/components/game/useGraphState.ts": 112,
    "frontend/src/components/game/graphView.ts": 84,
    # 120：力导向 SVG 画布 → game/GraphCanvas；126：去掉被截断的 extra 字幕
    "frontend/src/components/game/GraphModal.tsx": 120,
    # 147：画布高度改为填满弹窗正文（aspect-[3/2] 在 1400px 宽弹窗里算出 892px 高，
    #      底部节点被下沿裁掉），关系文字加碰撞判断、机器关系名换中文
    "frontend/src/components/game/GraphCanvas.tsx": 150,
    # 31：三种角色卡正文 → game/CharacterSheetBody
    "frontend/src/components/game/CharacterSheetModal.tsx": 31,
    "frontend/src/components/game/CharacterSheetBody.tsx": 152,
    # 106：单条地点卡 → game/map/MapEntryCard
    # 96：自建地点表单 → game/map/MapBuilderForm
    "frontend/src/components/game/MapModal.tsx": 96,
    # 88：+删除按钮（媒体条目此前只能建与改）
    "frontend/src/components/game/map/MapEntryCard.tsx": 88,
    "frontend/src/components/game/map/MapBuilderForm.tsx": 26,
    "frontend/src/components/game/DmToolsModal.tsx": 117,
    # 88：法术条目 → spell/SpellEntryCard，自建表单 → spell/SpellBuilderForm
    "frontend/src/components/game/SpellModal.tsx": 88,
    # 73：+删除按钮
    "frontend/src/components/game/spell/SpellEntryCard.tsx": 73,
    "frontend/src/components/game/spell/SpellBuilderForm.tsx": 27,
    "frontend/src/components/game/mediaActions/deleteMedia.ts": 25,
    "frontend/src/components/ui/InlineEdit.tsx": 100,
    "frontend/src/components/start/SaveStep.tsx": 63,
    # EditPanel 只留加载/写回/页签切换；六个标签页 → components/game/edit/
    # 221/80/50/85/105：编辑面板补上物品 CRUD、世界规则与 NPC 细节字段、删除本局会话入口
    # 88：编辑面板数据/写回 → game/edit/useEditPanelState
    # 93：场景保存带上 light / light_source 与显式 clear 列表
    "frontend/src/components/game/EditPanel.tsx": 93,
    "frontend/src/components/game/edit/useEditPanelState.ts": 158,
    "frontend/src/components/game/edit/types.ts": 70,
    "frontend/src/components/game/edit/rows.tsx": 100,
    # 67：+光照下拉（明亮/微光/黑暗/未设置）与光源输入
    "frontend/src/components/game/edit/SceneTab.tsx": 67,
    "frontend/src/components/game/edit/NpcTab.tsx": 80,
    "frontend/src/components/game/edit/LocationTab.tsx": 30,
    "frontend/src/components/game/edit/FlagTab.tsx": 35,
    "frontend/src/components/game/edit/StateTab.tsx": 100,
    "frontend/src/components/game/edit/SessionSettingsTab.tsx": 85,
    "frontend/src/components/game/edit/InventoryTab.tsx": 105,
    "frontend/src/components/game/edit/NoteTab.tsx": 90,
    # 126：+边界收敛 + 稀疏图谱收缩 + 最小间距分离（修掉节点/标签被裁与重叠）
    # 134：关系名映射（note_link / note_context / co_involved 不再原样画给玩家）
    "frontend/src/components/game/graphLayout.ts": 134,
    "frontend/src/components/game/monsterFormat.ts": 35,
    # 此前没纳入棘轮的游戏内组件（按当前值补上，只允许变小）
    # StatusPanel 只留面板编排；库存工具/分组列表、AI 用量卡、物品详情弹窗各成模块
    # 147：生命/资源/战斗/战场先攻/状态效果五段 JSX → status/ 下的展示组件
    # 155：用量卡片贴住侧栏底部（1440px 下侧栏下半屏整块留白），外层改列向 flex
    "frontend/src/components/StatusPanel.tsx": 155,
    "frontend/src/components/status/VitalsBlock.tsx": 70,
    "frontend/src/components/status/ResourceBlock.tsx": 55,
    "frontend/src/components/status/CombatBlock.tsx": 45,
    "frontend/src/components/status/TacticalBlock.tsx": 70,
    "frontend/src/components/status/EffectsBlock.tsx": 66,
    "frontend/src/components/status/inventory.tsx": 80,
    "frontend/src/components/status/MetricsCard.tsx": 85,
    "frontend/src/components/status/ItemDetailModal.tsx": 49,
    # 笔记面板只留数据与编排；展示型子组件与类型 → components/journal/
    # 3：NPC 卡 → journal/NpcCard，基础行/网格 → journal/NpcCardParts
    "frontend/src/components/journal/npcCards.tsx": 3,
    # 185：+行内编辑（身份/位置/态度/HP/AC）与「移除」，走 /world 的 update_npc/remove_npc
    "frontend/src/components/journal/NpcCard.tsx": 185,
    "frontend/src/components/journal/NpcCardParts.tsx": 56,
    "frontend/src/components/journal/types.ts": 45,
    # 155：输入区（实际 149 行；发送按钮/文本框的可点区域已提到 ≥40px）
    "frontend/src/components/InputArea.tsx": 155,
    # 100：升级数据/写回 → levelup/useLevelUp
    "frontend/src/components/LevelUpModal.tsx": 100,
    "frontend/src/components/levelup/useLevelUp.ts": 107,
    # LoginScreen 只留布局与分区标题；表单/品牌区/删号区 → components/login/，
    # 状态与请求（含删号 hook 组合）→ login/useLoginForm + login/useAccountDeletion
    "frontend/src/components/LoginScreen.tsx": 44,
    "frontend/src/components/login/LoginForm.tsx": 99,
    "frontend/src/components/login/LoginBrandPanel.tsx": 38,
    "frontend/src/components/login/DeleteAccountSection.tsx": 33,
    "frontend/src/components/login/useLoginForm.ts": 140,
    "frontend/src/components/login/useAccountDeletion.ts": 67,
    "frontend/src/components/login/errorText.ts": 6,
    # 全仓审计（tools.py 按域拆分这一轮）后补的覆盖：此前未纳入棘轮、且 >=150 行的文件
    # 一律按当前行数封顶，只允许变小；要改大就先拆分并同步下调上限
    "backend/default_content_data/bestiary_coc.py": 334,
    "backend/default_content_data/bestiary_dnd4e.py": 292,
    "backend/default_content_data/cities_coc.py": 293,
    "backend/default_content_data/cities_dnd4e.py": 154,
    "backend/document_pipeline/office_extractor.py": 173,
    "backend/document_pipeline/pipeline.py": 163,
    "backend/document_pipeline/recursive_splitter.py": 166,
    "backend/engine/dm_modules.py": 259,
    # 315 → 93：剧情记忆层 → memory_plot，上下文渲染 → memory_context
    "backend/engine/memory.py": 93,
    "backend/engine/memory_plot.py": 124,
    "backend/engine/memory_context.py": 81,
    "backend/engine/short_term_memory.py": 252,
    "backend/local_vector_store.py": 200,
    "backend/model_setup.py": 163,
    "backend/scenario_store.py": 276,
    "backend/schemas.py": 189,
    "backend/skills/__init__.py": 235,
    "backend/srd_spell_classes.py": 365,
    "backend/task_center.py": 226,
    "backend/vector_store.py": 164,
    # 188 → 136：滚动锁/尺寸/停靠类名 → ui/modalChrome，标题栏 → ui/ModalHeader
    "frontend/src/components/ui/Modal.tsx": 136,
    "frontend/src/components/ui/modalChrome.ts": 52,
    "frontend/src/components/ui/ModalHeader.tsx": 39,
    "backend/engine/knowledge_graph.py": 22,
    "backend/engine/graph_build.py": 203,
    "backend/engine/graph_query.py": 106,
    "backend/engine/graph_context.py": 104,
    # 特长被动：图鉴效果接线（先攻/生命/属性/双持 AC/短休下限），同步逻辑独立成 feat_sync
    "backend/engine/feat_sync.py": 102,
    "backend/engine/rest_tools.py": 112,
    # 5e 怪物图鉴按原条目顺序切四片（每片 5-6 条），主模块只做拼接
    "backend/default_content_data/bestiary_dnd5e.py": 20,
    "backend/default_content_data/bestiary_dnd5e_part1.py": 224,
    "backend/default_content_data/bestiary_dnd5e_part2.py": 222,
    "backend/default_content_data/bestiary_dnd5e_part3.py": 185,
    "backend/default_content_data/bestiary_dnd5e_part4.py": 184,
    # 会话层按职责拆三段：状态对象 / 生命周期 / SSE 总线，session.py 只再导出
    "backend/engine/session.py": 15,
    # 113：+chase_dashes（追逐冲刺计数）
    "backend/engine/session_state.py": 113,
    "backend/engine/session_manager.py": 85,
    "backend/engine/sse_bus.py": 182,
    # 观测层拆三段：类型 / 采集器 / OpenAI 代理，telemetry.py 只再导出
    "backend/telemetry.py": 14,
    "backend/telemetry_types.py": 87,
    "backend/telemetry_collector.py": 136,
    "backend/telemetry_openai.py": 122,
    # RAG 拆三段：模型/全局状态、嵌入、相似度与重排，rag_utils.py 只再导出
    "backend/engine/rag_utils.py": 22,
    "backend/engine/rag_models.py": 208,
    "backend/engine/rag_embed.py": 125,
    "backend/engine/rag_rank.py": 55,
    # 强力攻击（-5/+10）接线后 combat / feat_effects 增长；存档层拆出序列化与恢复
    # 攻击优势/劣势：schema 共享常量放 combat_advantage，工具定义只 +3 行
    # +3：充能能力 schema 共享常量注入 enemy_attack / save_damage
    # 120：advance_time 增加 pace（旅行节奏与强行军）
    "backend/engine/tool_defs_combat.py": 120,
    "backend/save_manager.py": 166,
    # +5/+5：再生待复活标记随动态状态读写
    "backend/save_serialize.py": 68,
    "backend/save_restore.py": 101,
    # combat.py 只留 combat_round 主结算；save_damage/enemy_attack → combat_damage
    # +10/+12：接入后端优势/劣势裁定（规则本体在 combat_advantage）
    # +3：记录玩家对敌人造成的伤害类型，供再生抑制
    # +13：玩家近战击杀前先结算亡灵坚韧（避免误判阵亡/误发经验）
    # 303 → 265：COC d100 对抗整段 → combat_coc.resolve_coc_round
    "backend/engine/combat.py": 265,
    "backend/engine/combat_coc.py": 74,
    # +11：回合开始效果接入（阳光超敏）
    # +3：范围伤害也记录类型
    # +2：允许待再生单位在自己的回合先结算复活
    # +20：enemy_attack/save_damage 接入充能检查
    # +8：enemy_action/reason 自动匹配充能能力
    # +17：save_damage 接入魔法抗性豁免优势
    # +12：save_damage 消耗传奇抗性把失败豁免改为成功
    # +11：save_damage 打到 0 HP 时先过亡灵坚韧
    # 363 → 19：save_damage → combat_save_damage，enemy_attack → combat_enemy_attack
    # 246：伤害参数统一收口（「22」这类字符串固定值不再退化成 0 伤害）
    # （只留门面与"补丁契约"说明：与 combat.py 同一套再导出约定）
    "backend/engine/combat_damage.py": 19,
    # 235：+玩家豁免的力竭 3 级劣势，并与魔法抗性优势互抵
    # 301 → 97：玩家侧 / 生物侧 / 公共裁定参数各成模块，这里只留编排与汇总
    # （`random` 是补丁面：测试打桩 combat_save_damage.random.randint）
    "backend/engine/combat_save_damage.py": 97,
    "backend/engine/combat_save_common.py": 129,
    "backend/engine/combat_save_player.py": 95,
    "backend/engine/combat_save_creature.py": 107,
    "backend/engine/combat_enemy_attack.py": 171,
    "backend/engine/magic_resistance.py": 54,
    "backend/engine/legendary_resistance.py": 54,
    "backend/engine/undead_fortitude.py": 76,
    # 316：Pack Tactics + 阳光敏感/公开光照查询
    # 321：读取 NPC 持久化 conditions 参与优势/劣势
    # 321 → 184：schema/词表/AdvantageDecision → combat_advantage_base，
    # 群体战术/阳光敏感 → combat_advantage_env
    # 184：隐形与隐藏合并成同一条"未被看见"判定（标签统一）
    # 194：+光照（攻守双方在黑暗里看不见）并入同一套优势/劣势来源
    "backend/engine/combat_advantage.py": 194,
    "backend/engine/combat_advantage_base.py": 109,
    "backend/engine/combat_advantage_env.py": 63,
    # 192：阳光超敏 + 再生回血/0 HP 复活/抑制与延迟经验
    # 198：回合开始追加 d6 充能掷骰
    # 214：NPC 条件每回合递减并推送过期
    # 232：阳光超敏致死也要先过亡灵坚韧（光耀压制会写明原因）
    "backend/engine/turn_start_effects.py": 232,
    "backend/engine/recharge_rules.py": 112,
    # media 路由按资源拆四个子路由，media.py 只做装配（路径与标签不变）
    "backend/routers/media.py": 27,
    "backend/routers/media_maps.py": 98,
    "backend/routers/media_spells.py": 103,
    "backend/routers/media_bestiary.py": 106,
    "backend/routers/media_images.py": 82,
    # scenarios 路由拆 crud / import 两个子路由，父模块只装配
    "backend/routers/scenarios.py": 16,
    "backend/routers/scenarios_crud.py": 100,
    "backend/routers/scenarios_import.py": 269,
    # world_tools 拆三段：世界状态写入 / 场景与揭示 / NPC 与角色查询
    "backend/engine/world_tools.py": 18,
    "backend/engine/world_state_tools.py": 274,
    # 86：update_scene 接受并回传 light / light_source
    # 90：+显式 clear=[...]（前端编辑面板要能清空天气/氛围这类文本字段）
    "backend/engine/world_scene_tools.py": 90,
    # +4：condition_add 前置免疫检查
    # 211：+NPC 专注字段分发，search_npcs 显示 [专注:…]
    # 215：+HP 归零同步 alive=False（与 _persist_combat_damage 同一约定）
    # 216：condition_add 透传 grappled_by
    "backend/engine/world_npc_tools.py": 216,
    # 218：条件免疫 + 每回合伤害/治疗 + 回合豁免结束
    # 228：持续伤害打到 0 HP 时先过亡灵坚韧
    "backend/engine/condition_rules.py": 228,
    # DM 主循环的回合收尾拆到 dm_finalize（依赖用 hooks 在调用点解析，保测试补丁语义）
    # 171：记录"补叙事触发前正文长度"（pre_polish_chars）用于成本归因
    "backend/engine/dm_finalize.py": 171,
    # dm_prompts 拆两段：角色信息块 / 系统提示装配，父模块只再导出
    "backend/engine/dm_prompts.py": 40,
    # 334：精简模式不再额外砍动态上下文（实测砍了反而更贵——主 DM 多轮查工具）
    # 335：时间与补给段落补一句"旅行时加 pace"
    # 337：真实模型探针暴露"直接叙事抓住、没掷对抗检定"后，战斗段落补两句对抗动作要求
    # 340：毒药探针两次都"只叙事不结算"，再补两句"毒素用 apply_poison"
    # 343：光照段落（进洞/点火把/熄灯要写 light，及其机械后果）
    # 361：+追逐段落，以及"追逐进行中"的状态驱动段落（只在 chase_dashes 非空时出现——
    #      实测写死在静态提示里会被叙事挤掉，DM 只记第一回合）
    "backend/engine/dm_system_prompt.py": 361,
    # 长期记忆拆三段：写入 / 检索 / 索引；常量与连接留在 long_term_memory（可被测试替换）
    # 105：+memory_manage 再导出（load/delete/update memory）
    "backend/long_term_memory.py": 105,
    "backend/memory_store.py": 170,
    # 109：记忆的读一条/改/删（从 memory_store 拆出：id 是内容哈希，改正文=删旧写新）
    "backend/memory_manage.py": 109,
    "backend/memory_retrieve.py": 143,
    "backend/memory_index.py": 127,
    # 角色卡拆 sheet/ 区块：helpers + 八个展示组件，父组件只做数据准备与编排
    "frontend/src/components/DndCharacterSheet.tsx": 43,
    "frontend/src/components/sheet/helpers.ts": 52,
    "frontend/src/components/sheet/SheetHeader.tsx": 65,
    "frontend/src/components/sheet/AbilitiesBlock.tsx": 73,
    "frontend/src/components/sheet/TraitsBlock.tsx": 16,
    "frontend/src/components/sheet/AttacksBlock.tsx": 31,
    "frontend/src/components/sheet/SpellcastingBlock.tsx": 45,
    "frontend/src/components/sheet/InventoryBlock.tsx": 20,
    "frontend/src/components/sheet/BackstoryBlock.tsx": 9,
    # 剧本工坊：状态留在 hook，两个长流程与 SSE 读取拆到 scenarioActions/scenarioStream；
    # scenario_importer 门面补回 detect_game_system 再导出（导入端点曾因此 500）
    # 158：剧本读取/删除/更新 → start/scenario/scenarioCrud
    "frontend/src/components/start/useScenarioStudio.ts": 158,
    "frontend/src/components/start/scenario/scenarioCrud.ts": 78,
    # 3：世界生成 → scenario/worldGenAction，文件导入 → scenario/importAction
    "frontend/src/components/start/scenarioActions.ts": 3,
    "frontend/src/components/start/scenario/worldGenAction.ts": 116,
    "frontend/src/components/start/scenario/importAction.ts": 124,
    "frontend/src/components/start/scenarioStream.ts": 37,
    "backend/scenario_importer.py": 75,
    # gameSystems 拆三段：数据 / 掷骰 / 派生，原文件只再导出
    "frontend/src/gameSystems.ts": 10,
    "frontend/src/gameSystemsData.ts": 92,
    "frontend/src/gameSystemsRolls.ts": 53,
    "frontend/src/gameSystemsDerived.ts": 62,
    # 先攻拆模型/门面；WorldState 按域拆 mixin（NPC / 场景 / 笔记），字段仍在本体
    # +21/+29：突袭轮标记、警觉/特性免疫、读档往返与行动拦截
    "backend/engine/initiative.py": 188,
    "backend/engine/initiative_model.py": 298,
    "backend/engine/world_state.py": 150,
    # 140：update_npc 改到 0 HP 时同步 alive=False（与 adjust_npc 同一约定）
    "backend/engine/world_npc_mixin.py": 140,
    "backend/engine/world_scene_mixin.py": 124,
    "backend/engine/world_note_mixin.py": 95,
    "backend/engine/feat_effects.py": 276,
    "backend/engine/dm_character_info.py": 139,
    # dm_runtime 拆三段：模型配置 / 叙事过滤 / 流式运行
    # 185：apply_hazard 加进 rules/combat/scene/narrative 的白名单
    # （resolve_trap 复用同样四个白名单，行数不变）
    # 186：resolve_stealth 也进同样的白名单（scene 白名单换行，多 1 行）
    # 189：rules/combat/narrative 三个白名单再加 resolve_contest
    # 192：白名单再加 resolve_chase（rules/combat/scene/narrative）
    # 199：流式出口加协议体检（tool_calls 与 tool 响应必须配对）
    "backend/engine/dm_runtime.py": 199,
    "backend/engine/dm_llm_config.py": 132,
    "backend/engine/dm_narrative_filter.py": 135,
    # focused_subagents 只留带工具的 runner（测试打桩点）；通用 runner/规划/摘要各自成模块
    "backend/engine/focused_subagents.py": 247,
    "backend/engine/subagent_runners.py": 99,
    "backend/engine/subagent_planning.py": 82,
    "backend/engine/subagent_summaries.py": 47,
    # dm_agent 只留回合编排与门面；工具循环（含强制结算守卫）→ dm_tool_loop
    "backend/engine/dm_agent.py": 335,
    # 206：连续错误保护提前退出前补齐 tool 响应；combat_round 的提示挪到整批响应之后
    "backend/engine/dm_tool_loop.py": 206,
    # 工具调用消息配对（协议不变量）单独成模块，别塞回 dm_runtime
    "backend/engine/dm_tool_protocol.py": 87,
    # dm_brief 拆三段：上下文装配 / 候选任务 / 结论聚合
    "backend/engine/dm_brief.py": 71,
    "backend/engine/dm_brief_context.py": 115,
    # 246：精简模式复用同一套模块化选人逻辑，但只留优先级最高的前 N 个（默认 1）
    # 并把预算收小——实测 lite 114k → 77k → 51k tokens（调用 23 → 19 → 11）
    # 263：+DND_SKIP_AGENTS（子 Agent 成本 A/B 开关，默认关闭；深模式也能少派一个做对照）
    "backend/engine/dm_brief_tasks.py": 263,
    # game_setup 只留建局流程；派生值/初始装备/状态响应 → game_derived，世界状态初始化 → game_world_init
    "backend/game_setup.py": 280,
    "backend/game_derived.py": 114,
    "backend/game_world_init.py": 69,
    # battlefield 拆三段：规则模型 / 状态门面 / 攻击预检与工具
    "backend/engine/battlefield.py": 97,
    "backend/engine/battlefield_rules.py": 188,
    "backend/engine/battlefield_actions.py": 126,
    # 总结生成（SUMMARY_PROMPT / 回退 / LLM 摘要）→ scenario_summary
    "backend/scenario_generate.py": 232,
    "backend/scenario_summary.py": 173,
    # 文档图片：文本/实体解析 → image_text，自动登记 → image_register，抽取留在 image_processor
    "backend/document_pipeline/image_processor.py": 162,
    "backend/document_pipeline/image_text.py": 127,
    "backend/document_pipeline/image_register.py": 121,
    # PDF：OCR/表格辅助 → pdf_ocr，extract_pdf 主流程与其再导出留在 pdf_extractor
    "backend/document_pipeline/pdf_extractor.py": 194,
    "backend/document_pipeline/pdf_ocr.py": 188,
    # time_rules 拆三段：时钟 / 补给与力竭 / 推进与长休流程
    # 143：advance_time 接到 travel_rules（强行军逐小时豁免）
    "backend/engine/time_rules.py": 143,
    "backend/engine/travel_rules.py": 86,
    "backend/engine/time_clock.py": 128,
    "backend/engine/time_supplies.py": 124,
    # 冒险笔记：数据 + 轮询 → journal/useJournalData，各页签各成组件
    # 79：+「记忆」页签（长期记忆的玩家入口）
    # 81：页签改成按内容伸缩（五个页签在 288px 侧栏里曾溢出 41px，"角色场景"被截成"场景"）
    "frontend/src/components/PlayerJournal.tsx": 81,
    # 99：+dnd:journal-refresh 监听（界面内改世界状态后主动重拉笔记）
    # 100：JournalTab 加 memories（该页签自己取数，不占用计数）
    "frontend/src/components/journal/useJournalData.ts": 100,
    # 122：记忆面板（列表 / 新增 / 改写 / 删除，自己调 /api/memories）
    "frontend/src/components/journal/MemoriesPanel.tsx": 122,
    "frontend/src/components/journal/NpcPanel.tsx": 56,
    "frontend/src/components/journal/PlotPanel.tsx": 38,
    # 57：占位行补 !l.description（否则没有 type 的地点把 description 印两遍）；
    #     地点名由截断改换行（截断后"（前厅内侧）/（右侧门影处）"看起来像重复卡片）
    "frontend/src/components/journal/PlacesPanel.tsx": 57,
    "frontend/src/components/journal/NotesPanel.tsx": 36,
    # 叙事流：正文渲染 → narrative/NarrativeBlock，骰子徽章 → narrative/DiceBadge
    "frontend/src/components/NarrativeStream.tsx": 139,
    "frontend/src/components/narrative/NarrativeBlock.tsx": 114,
    # 44：显示后端裁定的优势/劣势标签与说明
    # 48：来源说明从 title 改成可见文本（手机没有 hover）
    "frontend/src/components/narrative/DiceBadge.tsx": 48,
    # 生物图鉴：条目卡片 → beast/BeastCard，自建表单 → beast/BeastBuilderForm
    "frontend/src/components/game/BeastModal.tsx": 97,
    # 144：4e/CoC/六维与标准字段面板 → beast/BeastStatBlocks
    # 157：+删除按钮（复用 mediaActions/deleteMedia）
    "frontend/src/components/game/beast/BeastCard.tsx": 157,
    "frontend/src/components/game/beast/BeastStatBlocks.tsx": 76,
    "frontend/src/components/game/beast/BeastBuilderForm.tsx": 38,
    # 内容库动作：写入 → mediaActions/writeActions，机翻 → mediaActions/translateActions
    "frontend/src/components/game/useMediaLibraryActions.ts": 46,
    # 13：NPC/法术、地点、生物写入工厂分别下沉
    "frontend/src/components/game/mediaActions/writeActions.ts": 13,
    "frontend/src/components/game/mediaActions/writeNpcSpell.ts": 54,
    "frontend/src/components/game/mediaActions/writeMap.ts": 53,
    "frontend/src/components/game/mediaActions/writeBeast.ts": 66,
    "frontend/src/components/game/mediaActions/translateActions.ts": 89,
    # 游戏顶栏（品牌/场景/数值/九个导航按钮）→ game/GameHeader，动作经 handlers 传入
    # 186 → 150：全部弹窗装配（含参数接线）→ game/GameModals，这里只留三栏布局与顶栏
    "frontend/src/components/GameScreen.tsx": 150,
    # 78：九个弹窗改 lazy + 打开才挂载（首屏主包 335 → 239.5 kB，gzip 94.6 → 72.2 kB）
    "frontend/src/components/game/GameModals.tsx": 78,
    # 83：导航条 → header/HeaderNav，右侧数值 → header/HeaderStatus
    # 104：+光照指示（图标 + 明亮/微光/黑暗，第一行始终可见；光源描述在宽屏补充行）
    "frontend/src/components/game/GameHeader.tsx": 104,
    "frontend/src/components/game/header/HeaderNav.tsx": 40,
    "frontend/src/components/game/header/HeaderStatus.tsx": 37,
    # 生命阈值兜底：4e 血竭 + CoC 单次重伤/致死 → bloodied.py；状态钩子各 +2~4 行
    # +2：conditions_blocked 回写到 state_update
    # 354：+力竭 4/6 级落数值（实现搬到 exhaustion_effects）
    "backend/engine/character_state.py": 354,
    "backend/engine/exhaustion_effects.py": 61,
    # 206：玩家被打到 0 HP 时同样解除它施加的擒抱
    "backend/engine/player_damage.py": 206,
    "frontend/src/components/sheet/ResourcesBlock.tsx": 46,
    "backend/engine/bloodied.py": 96,
    # 仪式施法（cast_spell ritual=true）落地后同步上限
    "backend/engine/spell_tools.py": 272,
    "backend/engine/tool_defs_state.py": 74,
    # 后台剧情：提示/解析 → background_prompt，落账 → background_apply，调度留在主模块
    "backend/engine/background_events.py": 112,
    "backend/engine/background_prompt.py": 152,
    "backend/engine/background_apply.py": 119,

}

# 入口只装配，不写业务路由
DOMAIN_ROUTERS = (
    "auth", "characters", "extensions", "game", "generate",
    "knowledge", "media", "models", "saves", "scenarios", "session_settings",
    "tasks", "world", "memories",
)


class TestSplitOwnership(unittest.TestCase):
    def test_reexports_point_at_the_new_owners(self):
        from backend.engine import (
            character_state, combat, dm_agent, dm_prompts, dm_runtime,
            graph_tools, media_tools, session_tools, spell_tools, world_tools,
        )

        self.assertIs(dm_agent._exec_combat_round, combat._exec_combat_round)
        self.assertIs(dm_agent._exec_enemy_attack, combat._exec_enemy_attack)
        self.assertIs(dm_agent._exec_save_damage, combat._exec_save_damage)
        self.assertIs(dm_agent._exec_update_state, character_state._exec_update_state)
        self.assertIs(dm_agent.tick_conditions, character_state.tick_conditions)
        self.assertIs(dm_agent.build_system_prompt, dm_prompts.build_system_prompt)
        self.assertIs(dm_agent.build_character_info, dm_prompts.build_character_info)
        # 工具处理器按域归属
        self.assertIs(dm_agent._exec_dice_roll, session_tools._exec_dice_roll)
        self.assertIs(dm_agent.ability_mod_for_skill, session_tools.ability_mod_for_skill)
        # 法术类工具已归 spell_tools；media_tools 只做再导出（dm_agent 同样）
        self.assertIs(dm_agent._exec_cast_spell, spell_tools._exec_cast_spell)
        self.assertIs(dm_agent._exec_learn_spell, spell_tools._exec_learn_spell)
        self.assertIs(media_tools._exec_cast_spell, spell_tools._exec_cast_spell)
        self.assertIs(dm_agent._exec_update_world_state, world_tools._exec_update_world_state)
        self.assertIs(dm_agent._exec_get_character_state, world_tools._exec_get_character_state)
        self.assertIs(dm_agent._exec_update_knowledge_graph, graph_tools._exec_update_knowledge_graph)
        # 运行期工具归属
        self.assertIs(dm_agent._stream_with_tools, dm_runtime._stream_with_tools)
        self.assertIs(dm_agent._client, dm_runtime._client)
        self.assertIs(dm_agent.MODULE_TOOL_NAMES, dm_runtime.MODULE_TOOL_NAMES)

    def test_knowledge_base_composes_mixins_from_new_modules(self):
        from backend import knowledge_base as kb_module
        from backend.knowledge_docs import KnowledgeDocsMixin
        from backend.knowledge_retrieval import KnowledgeRetrievalMixin
        from backend.knowledge_text import _tokenize as text_tokenize

        self.assertTrue(issubclass(kb_module.KnowledgeBase, KnowledgeDocsMixin))
        self.assertTrue(issubclass(kb_module.KnowledgeBase, KnowledgeRetrievalMixin))
        # 职责归属：CRUD 在 docs mixin，检索在 retrieval mixin
        self.assertIs(kb_module.KnowledgeBase.add_document, KnowledgeDocsMixin.add_document)
        self.assertIs(kb_module.KnowledgeBase.get_document, KnowledgeDocsMixin.get_document)
        self.assertIs(kb_module.KnowledgeBase.retrieve, KnowledgeRetrievalMixin.retrieve)
        self.assertIs(kb_module.KnowledgeBase.seed_builtin_rules, KnowledgeRetrievalMixin.seed_builtin_rules)
        # 兼容再导出：既有 `from backend.knowledge_base import _tokenize` 仍可用
        self.assertIs(kb_module._tokenize, text_tokenize)

    def test_tool_table_points_at_domain_modules(self):
        """工具执行层必须直接指向归属模块，而不是绕回 dm_agent 的再导出。"""
        from backend.engine import (
            character_state, combat, graph_tools, media_tools, session_tools, spell_tools, world_tools,
        )
        from backend.engine.tool_executor import _handlers

        handlers = _handlers()
        self.assertIs(handlers["dice_roll"], session_tools._exec_dice_roll)
        self.assertIs(handlers["take_rest"], session_tools._exec_rest)
        self.assertIs(handlers["combat_round"], combat._exec_combat_round)
        self.assertIs(handlers["update_state"], character_state._exec_update_state)
        self.assertIs(handlers["cast_spell"], spell_tools._exec_cast_spell)
        self.assertIs(handlers["update_world_state"], world_tools._exec_update_world_state)
        self.assertIs(handlers["get_graph_path"], graph_tools._exec_get_graph_path)

    def test_dm_agent_still_exposes_the_legacy_surface(self):
        from backend.engine import dm_agent

        for name in ("execute_tool", "primary_action_available", "MODULE_TOOL_NAMES",
                     "SYSTEM_PROMPT", "DM_DECISION_PROMPT", "OPENING_PROMPT",
                     "_normalize_item", "_normalize_spell", "_recalc_equipment_effects",
                     "_refresh_combat_state", "_persist_combat_damage", "_has_feat_effect",
                     "_mode_instructions", "process_player_action", "generate_opening_scene"):
            with self.subTest(name=name):
                self.assertTrue(hasattr(dm_agent, name), f"dm_agent 缺少 {name}")

    def test_tool_registry_covers_every_tool(self):
        from backend.engine.tool_executor import _handlers
        from backend.engine.tools import DM_TOOLS

        handler_names = set(_handlers())
        tool_names = {t["function"]["name"] for t in DM_TOOLS}
        self.assertEqual(tool_names - handler_names, set(), "有工具没有处理器")
        self.assertEqual(handler_names - tool_names, set(), "有处理器没有 schema")

    def test_every_tool_is_reachable_in_some_module(self):
        """白名单决定 DM 看得见哪些工具：一个工具如果不在任何模块里，它等于不存在。

        这条不变量此前靠人工维护（每加一个工具都要记得改 dm_runtime），
        实测漏过几次——所以固化成测试。`suggest_choices` 是**有意**只给后台子 Agent 的，
        在 `_module_tools` 里被显式剔除，这里单独放行。
        """
        from backend.engine.dm_runtime import MODULE_TOOL_NAMES, _module_tools
        from backend.engine.tools import DM_TOOLS

        tool_names = {t["function"]["name"] for t in DM_TOOLS}
        listed: set[str] = set()
        for names in MODULE_TOOL_NAMES.values():
            listed |= set(names)
        self.assertEqual(sorted(tool_names - listed), [], "有工具没有进任何模块白名单，DM 永远看不到")
        self.assertEqual(sorted(listed - tool_names), [], "白名单里有陈旧项（工具已删除或改名）")
        # 白名单里的名字必须真的能被筛出来（防止拼错名字后静默失效）
        for module in MODULE_TOOL_NAMES:
            picked = {t["function"]["name"] for t in _module_tools(module, DM_TOOLS)}
            expected = set(MODULE_TOOL_NAMES[module]) - {"suggest_choices"}
            self.assertEqual(picked, expected & tool_names, f"{module} 模块筛出的工具与白名单不一致")


class TestFileSizeRatchet(unittest.TestCase):
    def test_no_file_exceeds_its_ceiling(self):
        oversized = []
        for relative, ceiling in SIZE_CEILINGS.items():
            path = ROOT / relative
            if not path.exists():
                continue
            lines = len(path.read_text(encoding="utf-8").splitlines())
            if lines > ceiling:
                oversized.append(f"{relative}: {lines} > {ceiling}")
        self.assertEqual(oversized, [], "文件重新膨胀，请拆分或同步下调上限")


class TestEntryIsAssemblyOnly(unittest.TestCase):
    def test_main_declares_no_routes(self):
        """main.py 只能 include_router；新接口一律落在 backend/routers/。"""
        source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
        declared = re.findall(r"^@app\.(?:get|post|put|delete|patch)\(", source, re.MULTILINE)
        self.assertEqual(declared, [], "main.py 不应再直接声明路由，请放到 backend/routers/")

    def test_every_domain_router_is_mounted(self):
        from backend.main import app

        source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
        for name in DOMAIN_ROUTERS:
            with self.subTest(router=name):
                module_path = ROOT / "backend" / "routers" / f"{name}.py"
                self.assertTrue(module_path.exists(), f"缺少路由模块 {name}.py")
                self.assertIn(f"from backend.routers.{name} import router", source)
                self.assertIn(f"app.include_router({name}_router)", source)
        # 装配是否真的生效：每个域至少有一个代表性端点出现在 OpenAPI 里
        schema_paths = set(app.openapi().get("paths", {}))
        for expected in ("/api/health", "/api/auth/login", "/api/scenarios",
                         "/api/characters", "/api/saves", "/api/knowledge",
                         "/api/tasks", "/api/extensions", "/api/maps",
                         "/api/models", "/api/generate/world", "/api/game/new"):
            with self.subTest(path=expected):
                self.assertIn(expected, schema_paths)


if __name__ == "__main__":
    unittest.main()
