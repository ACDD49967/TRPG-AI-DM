# TRPG AI 跑团主持

单人 TRPG 智能主持应用：先创建或导入剧本，再创建角色卡，由大语言模型担任主持人，完成叙事推进、规则检定、战斗结算、世界状态、资源管理、记忆暗线与知识图谱维护。

## 核心设计

- **剧本驱动**：所有冒险从剧本开始，系统按剧本生成世界状态、NPC、地点、生物、剧情旗标与知识图谱。
- **规则系统由剧本决定**：角色系统自动跟随剧本系统。
- **DM 与玩家信息隔离**：NPC/地点/剧情旗标通过 `discovered` / `visible` 控制，后台信息只进 DM 上下文，玩家仅看到已发现内容。
- **类知识图谱**：角色/地点/生物/剧情组织成节点与关系，支持亲密度、置信度、局部子图查询、向量检索与前端可视化。
- **ReAct 稳健性**：工具调用失败时会把错误回传给 DM 修正，而不是直接中断；同会话行动串行化，避免并发状态损坏。
- **主 DM 分配任务 + 子 Agent 调用工具**：主 DM 负责判断本回合需要哪些专业能力，规则裁决、战斗战术、场景事实、剧情连续性、关系图谱由专业子 Agent 并行执行；每个子 Agent 按技能包的 `allowed-tools` 调用工具并返回简报，主 DM 专注角色扮演、故事生成与世界操控；行动建议由后台子 Agent 强制生成。
- **RAG 混合检索**：本地稠密向量 + TF-IDF + BM25 三路融合，零外部 embedding 成本；可选 BGE-M3 稠密+稀疏、BGE-reranker 重排与 pgvector 持久化。

## 功能概览

### 剧本

- 内置免费经典剧本，支持 PDF、TXT、DOCX、DOC、MD 与扫描图片导入
- 统一文档管线：页级解析、OCR（PaddleOCR，可选安装）、跨页表格合并、页眉页脚清洗、注释合并、图片提取与自动图鉴载入
- 文本自动切分：快速切分、递归父子块切分（15% overlap）、语义切分、LLM 智能切分
- 识别/切分/载入异步执行：知识库上传走任务中心 + SSE 进度，前端可随时取消；剧本导入与知识库使用同一套递归父子块切分
- 剧本原件绑定到该剧本知识库（父子块/图片/表格同源存储），修订剧本仍作为使用剧本
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
- 主 DM 任务分配 + 子 Agent 工具执行：主 DM 负责选择任务，专业子 Agent 按 `SKILL.md` 的 `allowed-tools` 调用工具并返回简报，推理与工具选择对玩家隐藏；行动建议由后台子 Agent 强制生成
- AI 技能包标准化：每个技能是一个 `SKILL.md`（YAML Frontmatter + Markdown 指令正文），规则系统与专业子 Agent 能力均按需加载
- 战斗系统：多敌人独立单位、敌人回合 `enemy_attack`、同回合每敌人最多结算一次、被绑/昏迷/濒死敌人不会机械反杀、前端多敌人战斗面板与战斗记录
- 动态世界增删改：NPC/地点/旗标/世界规则可新增、更新、删除；`update_npc`/地点/旗标只覆写显式字段，删除时同步清理笔记与关系
- 开场与流式输出：开场白禁用思考保证稳定正文，流式叙事过滤“系统工具/我来结算”等幕后台词，避免破坏沉浸感
- 长期记忆：Markdown 记忆库（index/daily/episodic/semantic/procedural/thread/reflection）+ SQLite 多因子检索索引，支持合并、衰减与遗忘
- 短期记忆：LangGraph 装配图负责最近轮次、实体抽取、长期记忆检索与上下文装配；记忆检索子 Agent 通过 `search_memory` 工具按需取用
- 后台剧情推进：玩家视线之外的世界持续发展，深度模式每 3 轮、精简模式每 5 轮触发一次
- 知识图谱子 AGENT：DM 识别到关系变化时调用，子 AGENT 从文本中识别实体关系并更新，结果/错误回传 DM

### 知识与图鉴

- 本地 RAG：稠密向量 + TF-IDF + BM25 三路融合检索，SQLite 向量持久化
- 可选 BGE-M3（稠密+稀疏混合检索）、BGE-reranker 重排、pgvector 向量层
- 内置规则备注与 5etools SRD，支持上传知识库文档
- 法术图鉴、地图/地点图鉴、生物图鉴：结构化字段、自建、搜索、机翻
- 地图/生物/法术按剧本隔离；当前剧本显示剧本条目 + 全局通用参考；DM 可用 `search_*` 精简查询或完整卡面工具
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
- 任务中心：文档上传解析、BGE 模型下载等长任务统一走 SSE 进度事件
- 前端可保存多组 API 配置；剧本、存档、角色卡、扩展、媒体、知识文档按用户名隔离
- 一键安装/启动脚本；GitHub Release 提供打包产物

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11+、FastAPI、SQLAlchemy 异步、SQLite |
| AI | OpenAI 兼容 API、SSE 流式输出、ReAct、LangGraph |
| 前端 | React 18、TypeScript、Vite、Tailwind CSS、Zustand |
| 检索 | 本地稠密向量 + TF-IDF + BM25；可选 BGE-M3 / BGE-reranker / pgvector |
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

可选增强依赖（默认不安装，基础文本 PDF 可直接使用）：

```bash
# 扫描件 OCR（PaddleOCR / PaddlePaddle，体积较大且对平台有要求）
python scripts/install_runtime_deps.py --ocr

# 版面解析（PP-StructureV3）
python scripts/install_runtime_deps.py --layout

# BGE-M3 / reranker 本地模型
python scripts/install_runtime_deps.py --bge

# PostgreSQL + pgvector
python scripts/install_runtime_deps.py --pgvector
```

> 未安装 OCR 时，PDF 扫描页会被跳过或仅保留可提取文本；基础 PDF / DOCX / TXT / MD 导入不受影响。

## 项目结构

```
TRPG-AI-DM/
├── backend/
│   ├── main.py                 # FastAPI 路由 + SSE + 图谱/角色绑定
│   ├── config.py               # 配置
│   ├── schemas.py              # 请求/响应模型
│   ├── scenario_importer.py    # 剧本导入、切分、摘要
│   ├── scenario_store.py       # 剧本存储
│   ├── knowledge_base.py       # RAG 知识库（父子块 + 混合检索）
│   ├── local_vector_store.py   # 内置 SQLite 向量持久化
│   ├── vector_store.py         # pgvector 可选向量层
│   ├── task_center.py          # 长任务中心 + SSE 进度
│   ├── long_term_memory.py     # EverOS 风格 Markdown 长期记忆库 + SQLite 检索索引
│   ├── save_manager.py         # 存档管理
│   ├── character_card_manager.py # 角色卡管理（不绑定剧本）
│   ├── media_manager.py        # 地图 / 图鉴 / 图片
│   ├── classic_scenarios.py    # 免费经典剧本
│   ├── document_pipeline/      # 统一文档管线（PDF/OCR/表格/图片/父子块）
│   ├── skills/                 # AI 技能包（SKILL.md：YAML Frontmatter + Markdown 指令）
│   └── engine/
│       ├── dm_agent.py         # AI 主持核心 + ReAct + 工具
│       ├── dm_modules.py       # 模块化调度（LangGraph）
│       ├── focused_subagents.py # 多专业子 Agent 并发委派与简报聚合
│       ├── short_term_memory.py # LangGraph 短期记忆装配图
│       ├── world_builder.py    # 多步世界生成 + LangGraph 提取
│       ├── knowledge_graph.py  # 知识图谱构建/局部子图/向量检索
│       ├── graph_agent.py      # 知识图谱子 AGENT（文本识别更新）
│       ├── rag_utils.py        # 本地/BGE 稠密、稀疏、重排
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
DM 视图的知识图谱可视化，展示角色/地点/生物/剧情之间的节点与关系（含亲密度/置信度）。

## License

MIT
