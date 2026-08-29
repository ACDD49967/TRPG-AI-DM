# TRPG AI 跑团主持

单人 TRPG 智能主持应用：先创建或导入剧本，再创建角色卡，由大语言模型担任主持人，完成叙事推进、规则检定、战斗结算、世界状态、资源管理、记忆暗线与知识图谱维护。

## 核心设计

- **剧本驱动**：所有冒险从剧本开始，系统按剧本生成世界状态、NPC、地点、生物、剧情旗标与知识图谱。
- **规则系统由剧本决定**：角色系统自动跟随剧本系统。
- **DM 与玩家信息隔离**：NPC/地点/剧情旗标通过 `discovered` / `visible` 控制，后台信息只进 DM 上下文，玩家仅看到已发现内容。
- **类知识图谱**：角色/地点/生物/剧情组织成节点与关系，支持亲密度、置信度、局部子图查询、向量检索与前端可视化。
- **ReAct 稳健性**：工具调用失败时会把错误回传给 DM 修正，而不是直接中断；同会话行动串行化，避免并发状态损坏。
- **RAG 混合检索**：本地稠密向量 + TF-IDF + BM25 三路融合，零外部 embedding 成本；语义切分同样使用本地向量。

## 功能概览

### 剧本

- 内置免费经典剧本，支持 PDF、TXT、DOCX、DOC、MD 导入
- 文本自动切分：快速切分、语义切分、LLM 智能切分
- 根据描述生成完整世界大纲（世界观、主线、NPC、遭遇、规则），SSE 实时显示 LLM 输出
- 自建剧本时选择剧本规则系统（角色系统自动跟随）；导入剧本时后端自动识别规则系统
- 生成/导入完成后自动保存剧本，开局前再次自动保存当前编辑

### 规则系统

- D&D 5e：购点/掷骰属性、职业生命骰、熟练加值、豁免、被动感知、1–9 环法术位、邪术师契约法术位
- D&D 5e 职业资源：术法点、气、狂暴、诗人激励、圣疗、引导神力、荒野形态、回气、动作如潮、奥术回想
- D&D 4e：生命值、回复力、四类防御、行动点
- COC 7e：官方属性掷骰、双池技能点、HP/MP/SAN/幸运
- 自定义规则：由玩家提供规则文本；生成剧本时使用该规则系统

### 主持与叙事

- Function Calling 工具化处理：检定、战斗、死亡豁免、休息、状态更新、世界状态、信息揭示、场景更新
- 低 token 工具：角色状态、职业资源、施法、习得/遗忘法术、NPC 查询/调整、生物图鉴查询/调整
- ReAct 工具纠错：工具参数错误或执行失败会回传 DM，DM 接受报错并修改
- 记忆系统：短期轮次 + 自动摘要 + 长期记忆；大事件、暗线、人物影响结构化记忆
- 后台剧情推进：玩家视线之外的世界持续发展，深度模式每 3 轮、精简模式每 5 轮触发一次
- 知识图谱子 AGENT：DM 识别到关系变化时调用，子 AGENT 从文本中识别实体关系并更新，结果/错误回传 DM

### 知识与图鉴

- 本地 RAG：稠密向量 + TF-IDF + BM25 三路融合检索
- 内置规则备注与 5etools SRD，支持上传知识库文档
- 法术图鉴、地图/地点图鉴、生物图鉴：结构化字段、自建、搜索、机翻
- 地图/生物/法术按剧本隔离；DM 可用 `search_*` 精简查询或完整卡面工具
- 世界生成时自动提取 NPC、地点、生物、法术进入图鉴
- 类知识图谱：节点（NPC/地点/生物/剧情）+ 关系（亲密度/置信度/备注），支持局部子图查询与向量检索

### 角色与存档

- 角色卡独立于剧本保存，按规则系统过滤复用；不绑定具体剧本
- D&D 与 COC 官方纸面角色卡布局
- 装备/卸下实时影响 AC，武器优先使用已装备武器
- 经验按 D&D 官方升级表显示（5e/4e）
- 自动/手动存档，读档恢复完整对话历史

### 接口与部署

- OpenAI 兼容接口，自动探测 `/models` 与 `/v1/models`
- 前端可保存多组 API 配置；剧本、存档、角色卡、扩展、媒体、知识文档按用户名隔离
- 一键安装/启动脚本；GitHub Release 提供打包产物

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11+、FastAPI、SQLAlchemy 异步、SQLite |
| AI | OpenAI 兼容 API、SSE 流式输出、ReAct、LangGraph |
| 前端 | React 18、TypeScript、Vite、Tailwind CSS、Zustand |
| 检索 | 本地稠密向量 + TF-IDF + BM25（jieba 分词） |
| 部署 | 本地运行、zip 打包、GitHub Release |

## 快速开始

环境要求：Python 3.11+、Node.js 18+。

```bash
# Windows
setup.bat

# macOS / Linux / Git Bash
bash setup.sh
```

启动：

```bash
# Windows
run.bat

# macOS / Linux / Git Bash
bash run.sh
```

浏览器打开 `http://localhost:5173`。

## 项目结构

```
TRPG-AI-DM/
├── backend/
│   ├── main.py                 # FastAPI 路由 + SSE + 图谱/角色绑定
│   ├── config.py               # 配置
│   ├── schemas.py              # 请求/响应模型
│   ├── scenario_importer.py    # 剧本导入、切分、摘要
│   ├── scenario_store.py       # 剧本存储
│   ├── knowledge_base.py       # RAG 知识库（稠密+稀疏混合）
│   ├── save_manager.py         # 存档管理
│   ├── character_card_manager.py # 角色卡管理（不绑定剧本）
│   ├── media_manager.py        # 地图 / 图鉴 / 图片
│   ├── classic_scenarios.py    # 免费经典剧本
│   └── engine/
│       ├── dm_agent.py         # AI 主持核心 + ReAct + 工具
│       ├── world_builder.py    # 多步世界生成 + LangGraph 提取
│       ├── agent_graph.py      # LangGraph 专业提取流程
│       ├── knowledge_graph.py  # 知识图谱构建/局部子图/向量检索
│       ├── graph_agent.py      # 知识图谱子 AGENT（文本识别更新）
│       ├── rag_utils.py        # 本地稠密向量
│       ├── starting_gold.py    # DM 按财宝规则生成起始金币
│       ├── game_systems.py     # 规则计算与职业资源
│       ├── world_state.py      # 世界状态 + 显式关系表
│       ├── session.py          # 会话与 SSE + 每会话串行锁
│       └── memory.py           # 记忆系统
├── frontend/src/
│   ├── components/             # UI 组件（含知识图谱可视化）
│   ├── hooks/                  # SSE Hook
│   ├── store/                  # Zustand 状态
│   └── types/                  # 类型定义
├── scenarios/                  # 运行时数据，不入库
├── knowledge_base/             # 运行时数据，不入库
├── saves/                      # 运行时数据，不入库
├── media/                      # 运行时数据，不入库
├── characters/                 # 运行时数据，不入库
├── setup.bat / setup.sh        # 一键安装
└── run.bat / run.sh            # 一键启动
```

## 可选 RAG 模型

使用 BGE-M3 GGUF Q4_K_M 进行稠密向量生成，未配置或模型文件不存在时自动回退本地哈希向量。

使用 BGE-reranker-base 对混合检索结果进行重排序，未配置时按原混合分数返回。

## 常见问题

**生成剧本后为什么自动保存？**
生成/导入完成后系统会自动调用剧本保存接口；玩家后续编辑大纲/总结/自定义规则时，在开局前也会再次自动保存。

**图谱按钮是什么？**
DM 视图的知识图谱可视化，展示角色/地点/生物/剧情之间的节点与关系（含亲密度/置信度）。它只对主持人可见，不会向玩家泄露隐藏信息。

## License

MIT
