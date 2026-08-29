# TRPG AI 跑团主持 — 产品与系统规格（SPEC）

版本：v0.2.4 系列
状态：评审稿（未提交）

## 1. 产品目标

为单人 TRPG 玩家提供一位“持续在线、遵守规则、维护世界一致性”的 AI 地下城主（DM）。核心不是生成一段文本，而是让玩家在一个**结构化的活世界**中自由行动，同时保证规则、记忆、暗线与关系网络长期一致。

## 2. 核心概念

| 概念 | 说明 |
|------|------|
| 剧本（Scenario） | 冒险的权威来源：大纲、世界状态、规则系统、自定义规则、专属职业/技能/属性 |
| 角色卡（Character Card） | 可复用的玩家角色数据；不绑定具体剧本，但必须与剧本同规则系统 |
| 游戏会话（Session） | 一次运行中的冒险：角色 + 剧本 + WorldState + 记忆 + SSE 事件流 |
| WorldState | 当前世界的运行时状态：NPC、地点、生物、剧情旗标、显式关系、幕后事件 |
| 知识图谱 | 从 WorldState 派生的关系网络，DM 专用，支持亲密度/置信度/局部子图/向量检索 |
| RAG | 本地混合检索：稠密向量 + TF-IDF + BM25 |
| ReAct | 工具调用失败时回传错误让 DM 修正，而不是中断 |

## 3. 规则系统绑定

- 剧本有且仅有一个规则系统（dnd5e / dnd4e / coc / custom）。
- 角色系统由剧本系统决定，不允许自由选择。
- 自建剧本（AI 生成）时，玩家选择的是“剧本规则系统”；角色系统自动跟随。
- 导入剧本时后端自动识别系统。
- 已有剧本选择时，前端只显示与当前剧本系统匹配的角色卡。
- 角色卡库不包含 scenario_id，不绑定具体剧本。
- 后端 `create_new_game` 会校验 `saved.meta.system == request.game_system`，不匹配返回 400。

## 4. 剧本生成流程

1. 输入：基调、参考文本、备注、剧本规则系统、自定义规则/职业/技能/属性。
2. `build_world` 多步 LLM 生成：
   - 世界观与核心驱动
   - 主线三幕
   - NPC 与支线
   - 遭遇与隐藏内容
   - 合并 + 自评
   - 结构化字段提取
3. 字段提取使用 **LangGraph 专业 AGENT**：
   - `extract -> validate -> fix -> validate`
   - 严格校验 NPC/location/plot_flags 的必填字段与类型
   - 最多 2 轮纠错
4. 自动保存：生成/导入完成后前端立即调用保存；开局前再次保存。
5. SSE 流式输出 LLM 实时 token 与阶段进度。

## 5. 新游戏创建

1. 选择/生成剧本（绑定系统）。
2. 选择同系统角色卡或创建新角色。
3. 若未指定金币，DM 子 Agent 按财宝规则 + 剧本大纲 + 角色背景生成起始金币。
4. 创建 GameSession 与 WorldState。
5. 初始化记忆、长期事实、扩展包、RAG。

## 6. 游戏对话（DM 主循环）

- 每会话串行锁：同一会话同一时间只处理一个玩家行动。
- `process_player_action`：
  1. 构造 system prompt（角色、世界、记忆、知识图谱、检索片段）
  2. LLM 流式输出 + 工具调用
  3. 工具执行失败 -> 错误回传 LLM 修正（ReAct）
  4. 连续工具错误 >= 3 次停止重试
  5. 每轮强制 `suggest_choices`
  6. 世界状态 advance_turn + 存档
  7. 后台剧情推进按频率触发
- 工具集合：dice、combat、state、equip、spell、npc、bestiary、location、memory、plot memory、knowledge graph、scene、reveal、suggest 等。

## 7. 记忆与暗线

- 短期轮次：精简 5 轮 / 深度 10 轮。
- 摘要压缩：LLM 生成摘要，失败时提取式摘要。
- 长期事实：SQLite 按用户隔离。
- 结构化记忆：`major_events`、`hidden_threads`、`character_impacts`。
- 后台事件：`background_events`，按轮次频率触发，玩家仅看到公开传闻。

## 8. 知识图谱

- 节点：npc / location / creature / plot / entity。
- 边来源：
  - 结构化 `related_*` 字段；
  - 显式关系表 `ws.relations`：source/target/relation/strength/confidence/notes。
- 更新触发：
  - `record_plot_memory`（大事件/暗线/人物影响）自动建立关系；
  - `add_character_note`（带 related_npcs）自动建立关系；
  - `update_knowledge_graph` 子 AGENT 文本识别并更新。
- 查询：
  - DM 工具 `get_entity_graph` 返回局部子图；
  - 前端 `/api/game/{id}/graph` 支持完整图/局部图/向量搜索。
- 向量化：本地哈希嵌入（512 维），TF-IDF + 余弦。

## 9. RAG

- 分词：jieba + 字符 trigram。
- 检索融合：0.45 稠密向量 + 0.30 TF-IDF + 0.25 BM25。
- 向量缓存：按文档块内容 md5 缓存。
- 语义切分：使用本地向量计算句子相似度，按主题边界切分。

## 10. 玩家可见性边界

| 数据 | 玩家可见条件 |
|------|-------------|
| NPC | `discovered == True` |
| 地点 | `discovered == True` |
| 剧情旗标 | `visible == True` |
| 关系图谱 | 仅 DM 上下文/前端 DM 图谱 |
| 幕后事件 | 仅公开传闻（public_hint） |
| 记忆暗线 | 仅已揭示内容进入玩家可见叙事 |

## 11. API 概览

- `POST /api/game/new`：创建游戏（校验系统绑定）
- `POST /api/game/{id}/action`：提交玩家行动
- `GET /api/game/{id}/stream`：SSE 事件流
- `POST /api/game/{id}/equip`：装备/卸下
- `GET /api/game/{id}/journal`：玩家笔记
- `GET /api/game/{id}/graph`：知识图谱（DM）
- `GET/POST/PUT/DELETE /api/scenarios...`：剧本管理
- `GET/POST/DELETE /api/characters...`：角色卡管理
- `GET/POST/DELETE /api/knowledge...`：知识库
- `GET/POST/DELETE /api/maps|bestiary|spells`：图鉴
- `POST /api/generate/world/stream`：世界生成（SSE）
- `POST /api/scenarios/import`：剧本导入（SSE）

## 12. 安全与稳健性

- 工具错误信息脱敏（不含堆栈/路径）。
- 同一会话串行锁，避免并发状态损坏。
- 连续工具错误上限。
- 角色/剧本系统绑定校验。
- 用户数据按 username 隔离。
- 运行期 world_states 自动清理。
- 隐藏信息在后端视图层过滤，不直接暴露给玩家 API。

## 13. 发布

- 打包：`git archive` + `prepare_pkg.py` 净化知识库 + 内置经典剧本。
- 产物：`dist/TRPG-AI-DM-v0.2.4.zip`。
- README 在发布包内使用最新重写版本。
