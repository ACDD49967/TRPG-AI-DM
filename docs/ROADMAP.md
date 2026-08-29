# TRPG AI 跑团主持 — 项目路线图（ROADMAP）

版本：v0.2.4 系列  
状态：规划稿（未提交）  
优先级原则：先修“玩家直接感知的稳定性/一致性”，再增强“DM 智能与世界深度”，最后做“工程化/规模化”。

---

## 一、短期计划（1–4 周，v0.2.5–v0.3.x）

目标：把当前已实现能力打磨到“稳定、一致、可交付”，并补齐最影响体验的闭环。

### 1.1 会话安全与归属校验
- [ ] 在 `backend/main.py` 所有 `/api/game/{session_id}/*` 路由中校验 `state.username` 与请求 `username` 一致（journal/equip/graph/abort/save 等）。
- [ ] 为前端所有相关 fetch 显式携带 `username` 参数。
- [ ] 对无 session 的读接口返回统一 404，避免信息泄露。
- 验收：非归属用户无法读取/操作他人会话；现有游戏流程不回归。

### 1.2 状态同步与 SSE 可靠性
- [ ] `backend/engine/session.py` 的 `push_event` 统一携带 `seq`，`sse_event_generator` 按 `seq` 顺序发送。
- [ ] `frontend/src/hooks/useSSE.ts` 增加 `lastEventSeq` 去重，处理乱序/重复。
- [ ] `GameScreen.tsx` / `StatusPanel.tsx` 增加 SSE 断线重连提示（重连中/已恢复）。
- 验收：断网恢复后状态面板、叙事流、图谱按钮均能恢复，不丢事件。

### 1.3 图谱与关系可视化补全
- [ ] `backend/engine/knowledge_graph.py` 增加 `get_path(source, target, max_depth=4)` 最短路径。
- [ ] 新增 DM 工具 `get_graph_path`，返回路径文本。
- [ ] `frontend/src/components/GameScreen.tsx` 图谱 Modal 增加：
  - 力导向布局（可选：不引第三方，用轻量模拟）
  - 节点点击高亮相邻关系
  - 关系强弱颜色映射
- 验收：DM 可查“A 如何认识 B”，图谱可交互查看。

### 1.4 自动保存与剧本生命周期
- [ ] `backend/main.py` 为 `POST /api/generate/world/stream` 与 `POST /api/scenarios/import` 增加明确的 `status`（生成中/已完成/失败）字段。
- [ ] `frontend/src/components/StartScreen.tsx` 在生成/导入失败时显示重试按钮，不丢失已有输入。
- [ ] 生成/导入完成后统一调用 `updateScenario`，并刷新剧本列表。
- 验收：生成成功、失败、断线三种路径均能在场景列表中找到对应状态。

### 1.5 RAG 短期增强
- [ ] `backend/knowledge_base.py` 增加查询分类（规则/人物/地点/生物/法术），根据关键词调整三路权重。
- [ ] `backend/engine/rag_utils.py` 增加向量维度可配置与简单缓存上限。
- [ ] `backend/scenario_importer.py` 语义切分增加 Markdown 标题强制断点。
- 验收：规则查询与人物查询各自 Top3 命中更准；Markdown 剧本切分保留标题结构。

### 1.6 测试补强
- [ ] 将 `dist/lowlevel_test.py` 迁移为 `backend/tests/test_lowlevel.py`（pytest 风格）。
- [ ] 增加 API 契约测试：`TestClient` 覆盖 session/graph/equip/scenario binding。
- [ ] 前端构建错误提升为 CI 硬门槛。
- 验收：`pytest` 全绿；新增 30+ 测试。

---

## 二、中期计划（1–3 个月，v0.3.x–v0.4.x）

目标：提升 DM 智能与世界深度，引入子 Agent 体系与真正的多实例能力。

### 2.1 子 Agent 体系
- [ ] `backend/engine/agents/` 新增：
  - `memory_agent.py`：每 N 轮整理记忆，提取大事件/暗线进展
  - `thread_agent.py`：暗线推演，判断“可揭示时机”
  - `combat_balance_agent.py`：战斗前检查 CR/HP/AC 合理性
  - `style_agent.py`：按基调微调叙事风格
- [ ] 用 `agent_graph.py` 统一编排，主 DM 只负责调度与叙事。
- [ ] 主 system prompt 中移除过长子任务说明，只保留调度规则。
- 验收：主 DM 上下文减少 30%+，子 Agent 输出可追溯、可回放。

### 2.2 记忆升级
- [ ] `backend/engine/memory.py` 增加 `memory_index`（向量 + 关键词）。
- [ ] `build_context` 从“全量拼接”改为“TopN 检索 + 摘要 + 最近轮次”。
- [ ] 记忆增加 `importance` / `decay` / `last_accessed`。
- [ ] 长期记忆 SQLite 表增加 `importance`、`access_count` 字段。
- 验收：长会话 100+ 轮不超上下文；关键旧线索仍能召回。

### 2.3 知识图谱动态演化
- [ ] `backend/engine/knowledge_graph.py` 增加：
  - 关系时间线 `relation_history`
  - 关系衰减与增强规则
  - 自动从 `character_notes` / `plot_memory` 提取关系变化
- [ ] `WorldState.relations` 增加 `updated_at` / `source` 字段。
- [ ] DM 工具 `update_knowledge_graph` 支持修改已有边，而不仅是新增。
- 验收：NPC 关系随剧情自然变化，历史可回溯。

### 2.4 多实例基础
- [ ] `SessionManager` 抽象为 `SessionStore` 接口（内存/Redis）。
- [ ] SSE 队列改为可序列化事件存储。
- [ ] 每会话 `asyncio.Lock` 替换为 `redis.asyncio.Lock` 适配层。
- [ ] 增加 `docker-compose.yml`（API + Redis + 可选 pgvector）。
- 验收：两个 API 实例可同时处理不同会话；同会话行动仍串行。

### 2.5 RAG 外部 Embedding
- [ ] `rag_utils.py` 增加 `OpenAIEmbedding` 适配器。
- [ ] `KnowledgeBase` 支持 `EMBEDDING_BASE_URL/API_KEY/MODEL`，失败自动回退本地哈希。
- [ ] 向量缓存持久化到 SQLite（doc_id + chunk_hash + vector json）。
- 验收：配置 embedding 后，语义召回明显提升；不配置时零成本运行。

### 2.6 前端 DM 工作台
- [ ] 新组件 `DmWorkbench.tsx`：世界状态/暗线/记忆/图谱/工具调用日志。
- [ ] 图谱支持手动编辑关系（增删边、调亲密度/置信度）。
- [ ] `PlayerJournal.tsx` 增加“已发现关系”只读视图（可选，默认关闭）。
- 验收：DM 不再依赖弹窗拼凑，所有幕后信息集中可见；玩家默认看不到关系。

### 2.7 内容安全与审计
- [ ] `backend/main.py` 增加 `/api/game/{id}/audit`（仅 owner，返回最近 50 次工具调用）。
- [ ] `dm_agent.py` 每次工具调用记录 name/args/result/success/latency。
- [ ] 内容边界：R18 与“突然越权”分别记录原因，不记录敏感原文到审计日志。
- 验收：可定位问题轮次；日志不含 API Key / 堆栈。

---

## 三、长期计划（3–12 个月，v0.5+）

目标：工程化、规模化、生态化。

### 3.1 数据库迁移
- [ ] PostgreSQL + Alembic，保留 SQLite 单机模式。
- [ ] 所有文件型存储（scenarios/media/characters）提供对象存储适配器。
- [ ] 数据迁移与备份工具。
- 验收：SQLite 与 PostgreSQL 双模式跑通同一测试集。

### 3.2 向量数据库
- [ ] 接入 pgvector / FAISS / Milvus 可插拔检索后端。
- [ ] 知识库、记忆、图谱节点统一进入向量索引。
- [ ] 混合检索 RRF 融合。
- 验收：10 万级 chunk 检索 < 200ms。

### 3.3 多模型路由与成本控制
- [ ] 模型注册表：生成/总结/工具/embedding 可独立配置。
- [ ] 成本统计：每会话/每剧本 token 用量与费用。
- [ ] 自动降级：主模型失败切换备用模型。
- 验收：玩家可选择“性价比”配置；费用可见。

### 3.4 规则引擎深化
- [ ] 5e 动作经济、状态效果、专注、准备动作、夹击等。
- [ ] 4e 威能卡、标记、次要/移动/标准动作。
- [ ] COC 追逐/理智/魔法。
- [ ] 规则 DSL 或表单化自定义规则。
- 验收：AI 只需叙事，规则由程序判定。

### 3.5 战斗系统可视化
- [ ] 多敌人/多角色自动回合管理。
- [ ] 状态效果图标与倒计时。
- [ ] 战利品与经验自动结算。
- [ ] 战斗日志回放。
- 验收：复杂遭遇无需玩家记状态。

### 3.6 开放生态
- [ ] 扩展包 SDK（剧情包/规则包/图鉴包）。
- [ ] 剧本分享与评分。
- [ ] 角色卡模板分享。
- [ ] 社区 Hub 页面。
- 验收：第三方内容可一键导入。

### 3.7 CI/CD 与质量门禁
- [ ] GitHub Actions：lint → type → test → build → release。
- [ ] E2E Playwright 冒烟。
- [ ] LLM 回归快照测试。
- [ ] 自动 CHANGELOG 与 Release 资产。
- 验收：push 到 main 自动产出可发布 zip 与 Release。

### 3.8 可观测性
- [ ] 结构化日志 + trace_id。
- [ ] 指标：P95 响应、工具失败率、token 用量、SSE 断线率。
- [ ] 告警：LLM 不可用、连续失败、队列积压。
- 验收：任何线上问题可快速定位到会话/轮次/工具调用。

---

## 四、执行顺序建议

1. 先做 **1.1 + 1.2 + 1.4**：这是安全与稳定基线，影响所有后续。
2. 再做 **1.3 + 1.5 + 1.6**：图谱与 RAG 是核心差异能力。
3. 中期从 **2.1 + 2.2** 开始：子 Agent 与记忆决定 DM 深度。
4. 然后 **2.3 + 2.5 + 2.6**：图谱动态化、embedding、DM 工作台。
5. **2.4** 多实例在中期后半段启动，为长期数据库/向量化打底。
6. 长期按“数据库 → 向量库 → 多模型 → 玩法 → 生态 → CI/CD”推进。

## 五、里程碑定义

| 里程碑 | 版本 | 完成标准 |
|--------|------|----------|
| M1 稳定基线 | v0.2.5 | 1.1–1.6 全部完成，pytest 全绿 |
| M2 深度 DM | v0.3.0 | 子 Agent 体系可用，记忆检索不爆上下文 |
| M3 关系世界 | v0.4.0 | 动态关系 + DM 工作台 + 外部 embedding |
| M4 规模可用 | v0.5.0 | 多实例 + PostgreSQL/pgvector 可选 |
| M5 生态开放 | v1.0.0 | 扩展包、分享、CI/CD 全链路 |

---

> 注：本文件为规划稿，按约定未提交到版本库。
