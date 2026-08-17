# TRPG AI 跑团主持

> 单人 TRPG 智能主持人：剧本先行、多规则系统、AI 叙事、RAG 知识库、地图/图鉴/存档一站式。

## 项目简介

TRPG-AI-DM 是一个面向单人 TRPG 跑团的 AI 主持应用。玩家先选择/导入/生成剧本，再创建角色卡，随后由大语言模型担任主持人推进剧情、处理检定、管理世界状态。

项目不绑定单一规则系统，内置 D&D 5e、D&D 4e、克苏鲁的呼唤 7e（COC）与自定义规则，角色系统与剧本系统相互独立。

## 功能特性

- **剧本先行**
  - 已有剧本直接使用
  - 上传 PDF / TXT / DOCX / DOC / MD 自动切分
  - AI 根据描述生成完整世界大纲
  - 自动生成约 400 字剧本总结
- **多规则系统**
  - D&D 5e：官方购点、法术位、熟练加值、死亡豁免
  - D&D 4e：威能、回复力、四类防御
  - COC 7e：官方属性掷骰、双池技能点、理智/魔法/幸运
  - 自定义：玩家提供规则文本
- **AI 主持人**
  - 流式世界生成，实时显示进度
  - 开场导语、沉浸叙事、决策建议
  - 工具化检定：d20 / d100 / 战斗结算 / 状态更新
  - 长短期记忆与自动摘要
- **本地 RAG 知识库**
  - 内置规则备注与 5etools SRD 数据
  - 支持上传 PDF/DOCX/TXT/MD
  - 按规则系统过滤检索
- **角色卡与存档**
  - 多张角色卡保存/复用
  - 自动/手动存档，独立存档管理页
  - 读档恢复完整对话历史，不重新开场
- **地图与图鉴**
  - 地图/生物支持自定义图片
  - 生物图鉴搜索、地点↔生物关联
  - DM 工具：手动新增 NPC / 地点 / 生物
- **接口与部署**
  - OpenAI 兼容接口，可保存自定义 API 链接
  - 思维强度选择（轻量 / 标准 / 深度思考）
  - 一键 setup / run 脚本，支持打包发布

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11+、FastAPI、SQLAlchemy（异步）、SQLite |
| AI | OpenAI 兼容 API（DeepSeek 等）、SSE 流式输出 |
| 前端 | React 18、TypeScript、Vite、Tailwind CSS、Zustand |
| 检索 | 本地字符 bigram TF-IDF RAG（零 token 消耗） |
| 部署 | 本地运行、可打包为 zip / GitHub Release |

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+

### 安装

```bash
# Windows
setup.bat

# macOS / Linux / Git Bash
bash setup.sh
```

### 配置

复制 `.env.example` 为 `.env`，填写 API Key：

```
LLM_API_KEY=sk-你的密钥
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=你的模型名
```

也可以不配置 `.env`，直接在网页顶部填写 API 地址、Key、模型，并支持保存多个自定义链接。

### 启动

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
│   ├── scenario_importer.py    # 剧本导入/切分/总结
│   ├── scenario_store.py       # 剧本存储
│   ├── knowledge_base.py       # 本地 RAG 知识库
│   ├── save_manager.py         # 存档管理
│   ├── character_card_manager.py # 角色卡管理
│   ├── media_manager.py        # 地图/图鉴/图片管理
│   ├── classic_scenarios.py    # 免费经典剧本参考
│   └── engine/
│       ├── dm_agent.py         # AI 主持人核心
│       ├── world_builder.py    # 多步世界生成
│       ├── game_systems.py     # 规则系统
│       ├── world_state.py      # 世界状态
│       ├── session.py          # 会话与 SSE
│       └── memory.py           # 记忆系统
├── frontend/
│   └── src/
│       ├── components/         # UI 组件
│       ├── hooks/              # SSE Hook
│       ├── store/              # Zustand 状态
│       └── types/              # 类型定义
├── scenarios/                  # 已保存剧本（本地数据）
├── knowledge_base/             # 知识库数据（本地数据）
├── saves/                      # 存档（本地数据）
├── media/                      # 图片/地图（本地数据）
├── characters/                 # 角色卡（本地数据）
├── setup.bat / setup.sh        # 一键安装
├── run.bat / run.sh            # 一键启动
└── README.md
```

## 目录说明

- `scenarios/`、`knowledge_base/`、`saves/`、`media/`、`characters/` 为运行时用户数据，已加入 `.gitignore`，不会提交到 GitHub。
- 打包发布的压缩包会包含清理后的知识库（内置规则 + SRD）与免费经典剧本参考。

## 常见问题

### 无法获取模型列表？
- 确认 API 地址为 OpenAI 兼容格式（如 `https://api.deepseek.com/v1` 或 `https://api.deepseek.com`）。
- 确认 API Key 有效。
- 后端会自动尝试 `/models` 与 `/v1/models`。

### 上传图片不显示？
- 开发模式已通过 Vite 代理 `/media` 到后端。
- 生产模式由 FastAPI 静态目录 `/media` 提供。

### 读档后没有对话历史？
- 当前版本读档会直接恢复完整对话历史，不重新生成开场白。
- 如果看不到历史，请确认使用的是最新 release 包。

## License

MIT
