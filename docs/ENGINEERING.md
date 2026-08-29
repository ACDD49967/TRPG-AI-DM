# TRPG AI 跑团主持 — 项目工程说明（ENGINEERING）

版本：v0.2.4 系列
状态：评审稿（未提交）

## 1. 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11+、FastAPI、SQLAlchemy(async)、SQLite、SSE |
| AI | OpenAI 兼容 API、AsyncOpenAI、Function Calling、ReAct、LangGraph |
| 前端 | React 18、TypeScript、Vite、Tailwind CSS、Zustand、Framer Motion |
| 检索 | jieba、rank-bm25、自研本地稠密向量（rag_utils） |
| 打包 | git archive、prepare_pkg.py、Compress-Archive |

## 2. 目录结构

```
backend/
  main.py                  # FastAPI 路由、SSE、图谱端点、系统绑定校验
  config.py                # 环境配置
  schemas.py               # Pydantic 请求/响应
  scenario_importer.py     # 导入、切分、摘要、语义切分（稠密向量）
  scenario_store.py        # 剧本存储
  knowledge_base.py        # RAG（稠密+TFIDF+BM25）
  save_manager.py          # 存档
  character_card_manager.py# 角色卡（不绑剧本）
  media_manager.py         # 地图/生物/法术/图片
  classic_scenarios.py     # 经典剧本
  engine/
    dm_agent.py            # 主持核心、ReAct、工具、知识图谱子AGENT
    world_builder.py       # 多步世界生成、LangGraph 提取
    agent_graph.py         # LangGraph 提取/校验/纠错图
    knowledge_graph.py     # 图谱构建/局部子图/向量检索
    rag_utils.py           # 本地稠密向量
    starting_gold.py       # 起始金币 DM 生成
    game_systems.py        # 规则计算
    world_state.py         # 世界状态 + 关系表
    session.py             # 会话 + SSE + 串行锁
    memory.py              # 记忆系统
frontend/src/
  components/              # UI（含图谱可视化、角色创建、剧本、图鉴）
  hooks/                   # useSSE
  store/                   # Zustand
  types/                   # SSE/事件类型
docs/
  SPEC.md                  # 产品/系统规格
  ENGINEERING.md           # 本文档
```

## 3. 环境与安装

- Python 3.11+、Node.js 18+
- Windows：`setup.bat`
- macOS/Linux：`bash setup.sh`
- 依赖：`backend/requirements.txt`（含 langgraph、numpy、rank-bm25、jieba 等）
- 前端：`cd frontend && npm install`
- 环境变量：`.env` 支持 `LLM_API_KEY / LLM_BASE_URL / LLM_MODEL_NAME` 等

## 4. 开发运行

```bash
# 后端（默认 8000）
cd backend && uvicorn main:app --reload --port 8000

# 前端（默认 5173，Vite 代理 /api、/media）
cd frontend && npm run dev
```

## 5. 测试

- 低级/边界测试：`python dist/lowlevel_test.py`
  - 当前 251 项，覆盖 KB、切分、DM 工具、装备、记忆、暗线、后台事件、知识图谱、RAG、起始金币、隐藏信息。
- 后端语法：`python -m compileall -q backend`
- 前端构建：`cd frontend && npm run build`

## 6. 关键实现说明

### 6.1 DM 主循环
- `process_player_action` 是带锁入口，内部调用 `_process_player_action_inner`。
- 工具循环中：
  - JSON 参数错误 -> 回传 tool 错误；
  - 工具异常 -> 回传安全错误文本；
  - `error_streak >= 3` 停止重试；
  - 每轮未出现 `suggest_choices` 时强制补一次。

### 6.2 世界状态与知识图谱
- `WorldState.relations` 持久化显式关系边。
- `knowledge_graph.build_knowledge_graph(ws)` 派生完整图；
- `get_local_subgraph(ws, name, depth)` BFS 子图；
- `search_graph_nodes(graph, query)` 本地向量检索；
- `update_knowledge_graph` 工具调用子 AGENT，校验后写入关系。

### 6.3 RAG
- `KnowledgeBase.retrieve`：
  - 候选过滤（系统、用户）
  - BM25 稀疏
  - TF-IDF 稀疏
  - 稠密向量（rag_utils.embed_text）
  - 最终融合 `0.45*dense + 0.30*tfidf + 0.25*bm25`
- `split_text_semantic` 使用稠密向量计算句子相似度。

### 6.4 剧本/角色系统绑定
- 后端 `create_new_game` 校验 `saved.meta.system == request.game_system`。
- 前端：
  - 自建剧本时只选择“剧本规则系统”；
  - 已有剧本列表按当前系统过滤；
  - 加载剧本时自动把 `gameSystem` 同步为剧本系统；
  - 切换系统时清空不匹配的已选剧本；
  - 角色卡列表按系统过滤。

### 6.5 自动保存
- `genWorld` / `importScenario` 完成后调用 `updateScenario(overrides, sid)`；
- `start()` 创建游戏前 `await updateScenario()`。

## 7. 发布流程

1. `git archive --format=zip -o dist/pkg.zip HEAD`
2. `Expand-Archive dist/pkg.zip dist/pkg`
3. 复制最新 `README.md` 到 `dist/pkg/README.md`（若不提交 README）
4. `python dist/prepare_pkg.py dist/pkg`（净化知识库 + 经典剧本）
5. `Compress-Archive dist/pkg/* dist/TRPG-AI-DM-v0.2.4.zip`
6. 清理临时 `dist/pkg`、`dist/pkg.zip`
7. GitHub Release 需要 `gh` 或 token 上传 zip（当前环境未具备）

## 8. 已知限制与后续

- GitHub Release 资产上传依赖 `gh`/token，当前环境未安装。
- `deepseek-v4-flash` 在部分长上下文下可能只返回 reasoning 不返回 content；脚本已有重试/降级。
- 图谱关系目前主要来自结构化字段与子 AGENT 文本识别；后续可增加动态权重、路径查询、前端交互编辑。
- RAG 稠密向量为本地哈希，不具备跨语言/深层语义泛化；后续可接入外部 embedding。
- 多实例部署需将 `SessionManager` 与串行锁迁移到 Redis。

## 9. 工作区状态

- 代码更新已提交：`a7515eb`
- README、docs/SPEC.md、docs/ENGINEERING.md 为未提交评审稿
- Release zip：`dist/TRPG-AI-DM-v0.2.4.zip`
