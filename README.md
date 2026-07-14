# 朝花夕拾 Flower Dance

> 🌸 AI 驱动的自我认知探索工具

通过上传个人内容（文字/文件/图片），构建"认知卡片"，最终形成跨维度的"全局画像"。以中国传统"十二花神"为隐喻体系，帮助你更深刻地了解自己。

---

## 🌺 十二花神分类体系

| 序号 | 花名 | 分类维度 | 寓意 |
|:---:|------|---------|------|
| 1 | 梅花 | 性格特征 | 傲雪凌霜，喻坚韧高洁的内在品格 |
| 2 | 杏花 | 学习/成长 | 杏坛讲学，孔子治学的典故 |
| 3 | 桃花 | 情感/恋爱 | 桃花运，最经典的情感意象 |
| 4 | 牡丹 | 技能/能力 | 花中之王，喻技艺登峰造极 |
| 5 | 石榴花 | 家人/家庭 | 多子多福，家庭兴旺的直接象征 |
| 6 | 荷花 | 健康/身心 | 出淤泥而不染，身心清净养性 |
| 7 | 兰花 | 社交/朋友 | 金兰之交、芝兰之室，友谊的经典喻体 |
| 8 | 桂花 | 工作/事业 | 蟾宫折桂，功成名就的科举意象 |
| 9 | 菊花 | 兴趣/爱好 | 采菊东篱下，悠然自得的精神家园 |
| 10 | 木芙蓉 | 情绪/心态 | 拒霜花，在逆境中保持优雅的能力 |
| 11 | 山茶 | 习惯/规律 | 凌寒独自开，日复一日的坚持 |
| 12 | 水仙 | 决策/选择 | 凌波仙子，在迷雾中做出判断 |

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────┐
│           前端 (Frontend)           │
│  HTML5 + CSS3 + JavaScript (ES6+)   │
│  暗色花海主题 · 玻璃拟态面板         │
└─────────────────┬───────────────────┘
                  │ HTTP/REST
┌─────────────────▼───────────────────┐
│           后端 (Backend)            │
│    Python 3.9+ + FastAPI + Uvicorn  │
│    SQLite 持久化 · AI 流水线处理     │
└─────────────────┬───────────────────┘
                  │ API 调用
┌─────────────────▼───────────────────┐
│           AI 服务 (LLM)             │
│    智谱 AI · GLM-4-Flash (文本)     │
│    GLM-4V-Flash (视觉)              │
└─────────────────────────────────────┘
```

### 数据存储

- **数据库**: SQLite（本地文件存储）
- **数据位置**: `data/flower_dance.db`
- **持久化内容**: 上传记录、认知卡片、全局画像、用户反对记录
- **内存缓存**: 启动时从数据库加载，运行时读写缓存，写操作同步到数据库

---

## ✨ 核心功能

### 1. 内容上传与认知卡片生成
- **支持格式**: 文本、PDF、DOCX、图片
- **AI 流水线**: 分类判断 → 事实提取 → 卡片建议生成
- **质量把控**: 禁用词过滤、事实溯源校验、拼接检测、兜底重写

### 2. 卡片管理
- 分类浏览十二花神维度的认知卡片
- 支持编辑、删除、确认 AI 建议

### 3. 全局画像
- 跨分类综合分析（需至少 3 个分类各 2 张卡片）
- 发现维度间的张力与反差
- 支持"反对"反馈，避免重复生成

### 4. 拾花对话
- 自然语言提问 → 关键词匹配分类 → 检索相关卡片 → 基于卡片推理
- 三段式回答：看到的内容 / 综合分析 / 具体建议

### 5. 演示模式（Demo Mode）
- 一键进入演示模式，自动加载预设数据
- 3 个完整虚拟用户画像（约 190 张认知卡片）
- 18 个示例文本案例，覆盖全部分类维度
- 7 个演示文档（工作周报、学习笔记、日记等）
- 不影响真实用户数据，退出后自动恢复

---

## 🚀 快速开始

### 环境要求

- **Python**: 3.9+
- **Node.js**: 18+（仅 Electron 打包需要）
- **API Key**: 智谱 AI API Key（免费可用）

### 一键启动（推荐）

#### Mac / Linux
```bash
# 方式一：双击快捷方式
# 直接双击项目中的 FlowerDance.command 文件

# 方式二：终端命令
cd "flower dance"
bash scripts/FlowerDance.command
```

#### Windows
```powershell
# 方式一：双击快捷方式
# 直接双击项目中的 FlowerDance.bat 文件

# 方式二：命令提示符
cd "flower dance"
scripts\FlowerDance.bat
```

### 启动演示模式

#### Mac / Linux
```bash
# 使用 Python 启动器
python3 scripts/start_app.py --demo
python3 scripts/start_app.py --demo --demo-user demo_user_a

# 使用 Shell 脚本
bash scripts/start.sh --demo --demo-user demo_user_b

# 列出可用演示用户
python3 scripts/start_app.py --list-demo-users
```

#### Windows
```powershell
python scripts\start_app.py --demo
python scripts\start_app.py --demo --demo-user demo_user_a
python scripts\start_app.py --list-demo-users
```

### 手动启动

```bash
# 1. 安装后端依赖
cd backend
pip3 install -r requirements.txt

# 2. 设置 API Key（可选，默认使用免费模型）
cp .env.example .env
# 编辑 .env 文件，填入你的 API Key

# 3. 启动后端服务
cd backend
python3 -m uvicorn main:app --host 127.0.0.1 --port 8000

# 4. 在浏览器中打开
# http://localhost:8000

# 5. 在页面中点击"进入演示模式"按钮
```

### Electron 桌面应用（开发中）

Electron 版本因 M1/M2 Mac 架构兼容性问题暂不可用，推荐使用浏览器方式。

```bash
# 安装依赖
npm install

# 启动 Electron（仅 x86_64 架构可用）
npm start

# 打包（仅 x86_64 架构可用）
npm run build:mac
npm run build:win
npm run build:linux
```

---

## 📁 项目结构

```
flower dance/
├── backend/                    # 后端服务
│   ├── main.py                # FastAPI 主文件
│   ├── database.py            # 数据库操作
│   ├── prompts.py             # AI 提示词管理
│   ├── requirements.txt       # Python 依赖
│   └── __pycache__/           # Python 缓存
├── frontend/                  # 前端页面
│   ├── index.html             # 主页面
│   └── product-doc.html       # 产品文档
├── assets/                    # 资源文件
│   └── demo/                  # 演示数据
│       ├── texts/             # 示例文本（18个）
│       ├── docs/              # 演示文档（7个）
│       ├── users/             # 虚拟用户数据（3个）
│       └── create_demo_docs.py # 文档生成脚本
├── docs/                      # 项目文档
│   └── Demo.md                # 演示模式指南
├── scripts/                   # 启动脚本
│   ├── start.sh               # 一键启动脚本
│   ├── start_app.py           # Python 启动器（支持演示模式）
│   └── FlowerDance.command    # 桌面快捷方式
├── data/                      # 数据库文件
│   └── flower_dance.db        # SQLite 数据库
├── electron/                  # Electron 桌面应用
│   ├── main.js                # 主进程
│   └── preload.js             # Preload 脚本
├── tests/                     # 测试文件
├── logs/                      # 日志文件
├── .env                       # 环境变量
├── .env.example               # 环境变量模板
├── .gitignore                 # Git 忽略规则
├── AGENTS.md                  # AI Agent 工程规范
├── CHANGELOG.md               # 更新日志
├── DEVELOPMENT_PLAN.md        # 开发计划
├── README.md                  # 项目文档
└── package.json               # Electron 配置
```

---

## 🎭 演示模式说明

### 演示用户

| 用户 | 身份 | 特征标签 | 卡片数量 |
|------|------|---------|---------|
| 张小明 | 刚毕业研究生 | 学习积极、工作焦虑、社交较少、家庭关系良好 | ~50 |
| 李明 | AI工程师 | 长期加班、睡眠不足、兴趣广泛 | ~80 |
| 王艺涵 | 自由创作者 | 情绪丰富、阅读很多、旅行频繁 | ~60 |

### 演示流程（5分钟）

1. **上传文本** → 点击示例文本填充，「种下这段记忆」
2. **查看十二花神** → 观察花海中不同颜色的花朵分布
3. **查看全局画像** → 观察各维度节点和连接线
4. **提问对话** → "最近我最大的变化是什么？"
5. **成长总结** → "我的成长方向是什么？"
6. **切换用户** → 退出后选择另一个用户

### 推荐提问

- 我最大的优势是什么？
- 最近发生了什么变化？
- 我有哪些压力来源？
- 我的兴趣有哪些？
- 我的工作状态如何？
- 我的学习方式有什么特点？
- 我的情绪变化趋势是什么？
- 哪个花神维度最活跃？
- 我最近应该关注什么？
- 我的成长方向是什么？

---

## ⚙️ 配置说明

### API 配置

在 `backend/.env` 文件中配置：

```env
API_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
API_KEY=your_api_key_here
```

如果不配置，将使用智谱 AI 的免费模型。

---

## 📜 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)

---

## 📖 工程规范

详见 [AGENTS.md](AGENTS.md) - AI Agent 工程规范

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

MIT License