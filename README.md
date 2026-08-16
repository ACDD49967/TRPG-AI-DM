# 🐉 AI Dungeon Master — 单人 D&D 跑团桌游

由大语言模型驱动的 D&D 5e 地下城主。创建角色、生成世界、掷骰战斗——AI 扮演 DM，你扮演冒险者。

## ✨ 核心特性

- **剧本先行**：先选择/生成/导入剧本，再创建角色，让角色与故事更贴合。
- **多格式剧本导入**：支持上传 `pdf`、`txt`、`md`、`docx`、`doc` 等常见剧本格式。
- **两种切分方式**：可选「切分器」快速硬切分，或「语义切分」按语义连贯性分组。
- **400 字剧本总结**：每个生成的剧本自动附带约 400 字总结，方便快速回顾与选择。
- **多规则系统**：内置 D&D 5e、D&D 4e、克苏鲁的呼唤 7e（COC）与自定义规则；自动识别剧本类型，角色创建面板随系统切换（D&D 显示 HP/法术位，COC 显示 HP/理智/魔法等）。
- **精简 / 深度双模式**：开局选择「精简模式」（低 token、快节奏）或「深度模式」（高 token、高深度扮演）。

## 系统要求

| 组件 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.11+ | 后端 API 服务器 |
| Node.js | 18+ | 前端 UI（可选，后端可独立运行） |
| DeepSeek API Key | — | [免费获取](https://platform.deepseek.com/api_keys) |

macOS 用户：`brew install python@3.12 node`
Ubuntu 用户：`sudo apt install python3.12 python3.12-venv nodejs npm`

## 快速开始（3 步）

### 第一步：初始化

```bash
# Windows — 双击或在终端运行：
setup.bat

# macOS / Linux / Git Bash：
bash setup.sh
```

`setup` 脚本会自动：创建 Python 虚拟环境 → 安装后端依赖 → 安装前端依赖 → 生成 `.env` 配置文件。

### 第二步：配置 API Key

打开项目根目录下的 `.env` 文件，填入你的 API Key：

```
LLM_API_KEY=sk-你的密钥
```

> 如果 `.env` 不存在，复制 `.env.example` 并重命名为 `.env`。

### 第三步：启动

```bash
# Windows — 双击：
run.bat

# macOS / Linux / Git Bash：
bash run.sh
```

浏览器会自动打开 `http://localhost:5173`，开始冒险！

> **纯后端模式**：如果你没有安装 Node.js，`run.bat`/`run.sh` 会自动降级为后端-only 模式，API 文档在 http://localhost:8000/docs。

## 剧本导入与切分

在「剧本」步骤中，你可以：

1. 直接粘贴参考剧本，或填写世界描述后点击「生成世界大纲」；
2. 上传 `pdf` / `txt` / `md` / `docx` / `doc` 剧本文件；
3. 选择切分方式：
   - **切分器**：按段落和字数快速硬切分；
   - **语义切分**：基于字符 n-gram 的局部语义相似度切分，长剧本更连贯。
4. 系统会自动将剧本切分为多个片段 → 多 Agent 生成新剧本 → 生成约 400 字剧本总结 → 保存到 `scenarios/`。

> 老式 `.doc` 为尽力支持：优先使用系统 `antiword`，不可用时退回文本提取。建议复杂 `.doc` 文件先另存为 `.docx` 或 `.txt`。

## 规则系统

- **D&D 5e**：d20 检定、优势/劣势、法术位、死亡豁免。
- **D&D 4e**：d20 对防御、HP/回复力、威能系统、四类防御。
- **COC 7e**：d100 百分比检定、理智（SAN）、魔法（MP）、幸运、调查员职业。
- **自定义 / 其他**：上传自定义剧本并填写自定义规则文本，AI DM 按你的规则主持。

在「剧本」步骤可选择生成时使用的规则系统；导入剧本文件时如果不指定，后端会通过固定关键词自动识别剧本类型（无需额外 token）。

## 精简模式 / 深度模式

开始页顶部即可选择：

| 模式 | Token 消耗 | 适合场景 |
|------|-----------|---------|
| ⚡ 精简模式 | 低 | 快速体验、节省 API 费用 |
| 🐉 深度模式 | 高 | 高沉浸扮演、更丰富描写与选择 |

模式会影响叙事长度、描写密度、决策选项数量和工具调用频率。

## 项目结构

```
dndgame/
├── backend/               # Python FastAPI 后端
│   ├── main.py            # API 路由 + SSE 长连接
│   ├── config.py           # 配置（从 .env 加载）
│   ├── database.py         # SQLite 数据库 + ORM
│   ├── models.py           # 数据模型
│   ├── schemas.py          # 请求/响应 schema
│   ├── scenario_store.py   # 剧本存储
│   ├── scenario_importer.py# 剧本导入：PDF/DOCX/TXT 解析、切分、总结
│   └── engine/
│       ├── dm_agent.py     # AI 地下城主核心
│       ├── game_systems.py # D&D5e/D&D4e/COC/自定义规则配置与识别
│       ├── rules.py        # D&D 5e 规则引擎
│       ├── tools.py        # AI 工具定义
│       ├── feats.py        # 特长系统
│       ├── world_state.py  # 世界状态持久化
│       ├── world_builder.py# 多 Agent 世界生成
│       ├── session.py      # 会话管理 + SSE
│       └── memory.py       # 记忆系统
├── frontend/              # React + Vite + Tailwind 前端
│   └── src/
│       ├── components/     # UI 组件
│       ├── hooks/          # SSE Hook
│       ├── store/          # Zustand 状态管理
│       └── types/          # TypeScript 类型
├── scenarios/             # 已保存的冒险剧本
├── world_states/          # 世界状态持久化
├── setup.bat / setup.sh   # 一键初始化
├── run.bat / run.sh       # 一键启动
├── .env.example           # 环境变量模板
└── README.md
```

## 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | FastAPI (Python) |
| AI 引擎 | DeepSeek API（兼容 OpenAI 协议） |
| 数据库 | SQLite + SQLAlchemy 异步 ORM |
| 实时通信 | Server-Sent Events (SSE) |
| 前端框架 | React 18 + TypeScript |
| 构建工具 | Vite 5 |
| CSS 框架 | Tailwind CSS 3 |
| 状态管理 | Zustand |
| 动画 | Framer Motion |

## 常见问题

**Q: 启动后前端页面空白？**
A: 确认 Node.js 已安装（`node --version`），然后 `cd frontend && npm install`。

**Q: 后端报 API 调用失败？**
A: 检查 `.env` 中的 `LLM_API_KEY` 是否正确。确认网络能访问 `api.deepseek.com`。

**Q: 端口被占用？**
A: `run.bat`/`run.sh` 会自动杀掉 8000/5173 端口的旧进程。如果仍失败，手动 `netstat -ano | findstr :8000` 查看占用。

**Q: 如何更换模型？**
A: 编辑 `.env`，修改 `LLM_BASE_URL` 和 `LLM_MODEL_NAME`。任何兼容 OpenAI 协议的 API 都可用。

**Q: pip 安装很慢？**
A: setup 脚本已内置阿里云镜像作为 fallback。你也可以手动：
```bash
pip install -r backend/requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

**Q: 如何把项目发给朋友？**
A: 运行 `package.bat`（或 `bash package.sh`），将 `dist/AI-Dungeon-Master.zip` 发给对方。他们解压后只需运行 `setup.bat` + 配置 `.env` + `run.bat`。
