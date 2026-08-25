# TRPG AI 跑团主持

单人 TRPG 智能主持应用：先创建或导入剧本，再创建角色卡，由大语言模型担任主持人，完成叙事推进、规则检定、战斗结算、世界状态与资源管理。

## 功能概览

### 剧本

- 内置免费经典剧本，支持 PDF、TXT、DOCX、DOC、MD 导入
- 文本自动切分（段落 + 语义），生成约 400 字剧本摘要
- 根据描述生成完整世界大纲（世界观、主线、NPC、遭遇、规则），生成过程通过 SSE 实时显示进度
- 自动识别规则系统（D&D 5e / D&D 4e / COC / 自定义），可手动覆盖

### 规则系统

- D&D 5e：购点/掷骰属性、职业生命骰、熟练加值、豁免、被动感知、1–9 环法术位、邪术师契约法术位
- D&D 5e 职业资源：术法点、气、狂暴次数、诗人激励、圣疗、引导神力、荒野形态、回气、动作如潮、奥术回想
- D&D 4e：生命值、回复力、四类防御、行动点
- COC 7e：官方属性掷骰、双池技能点（教育×4 职业 / 智力×2 兴趣）、HP=(CON+SIZ)/10、MP=POW/5、SAN=POW
- 自定义规则：由玩家提供规则文本，角色与剧本互不绑定

### 主持与叙事

- Function Calling 工具化处理：属性检定、战斗轮、死亡豁免、短休/长休、状态更新、世界状态、信息揭示、场景更新
- 低 token 快捷工具：`get_character_state` 查角色状态、`adjust_resource` 增减职业资源、`cast_spell` 自动扣法术位、`learn_spell`/`forget_spell` 管理法术、`search_npcs`/`adjust_npc` 查询与增减 NPC 数值、`search_bestiary`/`adjust_bestiary` 查询与修改生物数值
- 战斗与实体卡联动：DM 战前必须 `search_npcs`/`search_bestiary` 查卡；`combat_round` 只传动作与敌人名即可自动读取角色卡攻击/AC、NPC 卡或图鉴卡 HP/AC/攻击，并将伤害写回实际实体；图鉴怪物首次交战时自动注册为世界状态 NPC；新地点经 `update_scene` 自动写入地点列表
- 短期记忆（精简 5 轮 / 深度 10 轮）+ 自动摘要压缩 + 按用户隔离的长期记忆
- 按规则系统切换提示词、技能与思维链（CoT）
- 轻量 / 标准 / 深度思考三档
- DM 输出兼容 Markdown：标题、列表、引用、分隔线、表格均可在前端正确渲染

### 知识与图鉴

- 本地 RAG：jieba 分词 + TF-IDF + BM25 融合检索，零 token 消耗
- 内置规则备注与 5etools SRD，支持上传知识库文档，按规则系统过滤
- 内置 30 个中文经典法术（火球术、魔法飞弹、治疗伤害等），并自动从知识库 SRD JSON 抓取 361 个法术，统一为「名称/环位/学派/仪式/施法时间/距离/成分/持续/职业/效果」格式
- 玩家与 DM 均可在游戏内自建法术，字段与内置法术卡一致
- 地图、生物图鉴、法术图鉴均按剧本隔离；DM 可通过工具检索并向当前剧本添加条目
- 世界生成时自动提取 NPC、地点、生物、法术进入图鉴

### 角色与存档

- 角色卡独立于剧本保存，可复用；D&D 与 COC 使用对应官方纸面角色卡布局
- 角色卡按「一行摘要 + 点开详情」组织：职业资源、法术位、已习得法术、攻击/豁免/技能均展示计算公式与最终值；法术显示为「火球术：三环 塑能（术士、法师）」，点开查看施法时间/距离/成分/持续/完整效果
- 生物图鉴与 NPC 卡同样折叠显示：怪物摘要为「名称 · CR · HP · AC」，NPC 卡按 D&D 官方 NPC 卡排版（护甲等级/生命值/六维调整/技能/特性/动作）
- 角色创建支持按职业/种族选择戏法与一环法术：法师 3 戏法+6 法术、术士 4+2、牧师/德鲁伊按感知调整准备法术、诗人 2+4、邪术师 2+2；高等精灵额外获得法师戏法，提夫林获得奇术
- 新角色自动获得职业初始装备（武器/护甲/法器/冒险套件按官方起始装备表发放），背包显示数量，空背包才发放，不覆盖玩家自定义开局
- 金币参与交易结算：购买、雇佣、贿赂等行为由 DM 工具直接更新余额
- 自动 / 手动存档，独立存档页；读档恢复完整对话历史，不重新调用模型生成开场

### 接口与部署

- OpenAI 兼容接口：启动时自动探测 `/models` 与 `/v1/models`，前端模型下拉框直接选择
- 前端可保存多组 API 配置；剧本、存档、角色卡、扩展、媒体文件与用户知识文档均按用户名隔离（内置规则与 SRD 为全局共享）
- 旧版根目录剧本在非 default 用户首次打开剧本列表时自动迁移到该用户名下，已有剧本立即可用
- 一键安装 / 启动脚本；GitHub Release 提供打包产物

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11+、FastAPI、SQLAlchemy 异步、SQLite |
| AI | OpenAI 兼容 API、SSE 流式输出 |
| 前端 | React 18、TypeScript、Vite、Tailwind CSS、Zustand |
| 检索 | jieba + TF-IDF + BM25（本地计算） |
| 部署 | 本地运行、zip 打包、GitHub Release |

## 快速开始

环境要求：Python 3.11+、Node.js 18+。

安装：

```bash
# Windows
setup.bat

# macOS / Linux / Git Bash
bash setup.sh
```

配置：复制 `.env.example` 为 `.env`，填写 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL_NAME`。也可以跳过 `.env`，在网页顶部的 API 设置中填写。

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
│   ├── main.py                 # FastAPI 路由 + SSE
│   ├── config.py               # 配置
│   ├── schemas.py              # 请求/响应模型
│   ├── scenario_importer.py    # 剧本导入、切分、摘要
│   ├── scenario_store.py       # 剧本存储
│   ├── knowledge_base.py       # RAG 知识库
│   ├── save_manager.py         # 存档管理
│   ├── character_card_manager.py # 角色卡管理
│   ├── media_manager.py        # 地图 / 图鉴 / 图片
│   ├── classic_scenarios.py    # 免费经典剧本
│   └── engine/
│       ├── dm_agent.py         # AI 主持核心
│       ├── world_builder.py    # 多步世界生成
│       ├── game_systems.py     # 规则计算与职业资源
│       ├── world_state.py      # 世界状态
│       ├── session.py          # 会话与 SSE
│       └── memory.py           # 记忆系统
├── frontend/src/
│   ├── components/             # UI 组件
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

`scenarios/`、`knowledge_base/`、`saves/`、`media/`、`characters/` 为运行时用户数据，已加入 `.gitignore`。发布包内包含清理后的内置知识库（规则备注 + SRD）与免费经典剧本。

## 常见问题

**无法获取模型列表？**
确认 API 地址为 OpenAI 兼容格式（如 `https://api.deepseek.com/v1` 或 `https://api.deepseek.com`），并确认 API Key 有效。后端会自动尝试 `/models` 与 `/v1/models`。

**上传图片不显示？**
开发模式经 Vite 代理 `/media` 到后端，生产模式由 FastAPI 静态目录提供。

**读档后没有对话历史？**
读档通过 SSE `history` 事件恢复完整对话，不重新生成开场白。若仍看不到历史，请使用最新 release 包。

## License

MIT
