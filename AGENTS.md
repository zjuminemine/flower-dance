# Flower Dance Agent Engineering Specification

本文件用于规范所有 AI Agent（Trae、Claude Code、Codex、Cursor 等）参与 Flower Dance 项目开发时的工程行为。

目标：

允许项目持续迭代，但保证工程结构始终清晰、统一、可维护。

---

## 一、总体原则

本项目允许：

- 新增功能
- 重构局部模块
- 优化算法
- 调整 Prompt
- 提升 UI
- 新增 API

但必须保证：

- 工程结构保持统一
- 文件放置符合规范
- 不产生历史垃圾
- 不产生重复实现
- 不随意增加目录

---

## 二、目录规范

任何新增文件都必须放入对应目录。

禁止：

```
backend/
├── test.py
├── new.py
├── utils2.py
└── temp.py
```

禁止在根目录新增临时文件。

---

推荐目录：

```
project/
├── frontend/
├── backend/
│   ├── api/
│   ├── services/
│   ├── models/
│   ├── prompts/
│   ├── utils/
│   ├── core/
│   ├── config/
│   ├── database/
│   ├── cache/
│   └── tests/
├── assets/
└── docs/
```

新增模块时优先使用已有目录。

如果目录不存在，请先评估是否真的需要新增。

---

## 三、根目录规范

根目录只允许存在：

```
README.md
AGENTS.md
CHANGELOG.md
ROADMAP.md
DEVELOPMENT_PLAN.md
LICENSE
requirements.txt
package.json
backend/
frontend/
assets/
docs/
scripts/
```

不要把：

- 测试文件
- 日志
- JSON
- 缓存
- Prompt
- 临时脚本

直接放在根目录。

---

## 四、Prompt 管理

所有 Prompt 必须集中管理。

例如：

```
backend/prompts/
├── card_prompt.py
├── profile_prompt.py
├── chat_prompt.py
└── system_prompt.py
```

不要：

- 把 Prompt 写在多个 Python 文件中。
- 复制相同 Prompt。
- 多个 Prompt 完成同一功能。

---

## 五、API 规范

API 按功能划分。

例如：

```
api/
├── upload.py
├── cards.py
├── profile.py
└── chat.py
```

不要：

- 所有接口写到 main.py。

新增 API 时：

- 保持命名统一。
- 保持 REST 风格。

---

## 六、业务逻辑规范

业务逻辑：

- 放入 services。

API：

只负责：

- 接收请求；
- 调用 Service；
- 返回结果。

不要：

- 在 API 中直接写复杂逻辑。

---

## 七、工具函数规范

所有公共函数：

统一放入：

```
utils/
```

禁止：

- 每个文件复制一份。

如果发现已有实现：

- 必须复用。

---

## 八、配置规范

所有：

- API Key
- 模型名称
- 路径
- 缓存时间

统一进入：

```
config/
```

禁止：

- 硬编码。

---

## 九、模型调用规范

所有 LLM 调用：

- 统一封装。

不要：

- 每个模块直接调用模型。
- 复制调用代码。

---

## 十、静态资源规范

图片：

```
assets/images/
```

图标：

```
assets/icons/
```

示例数据：

```
assets/demo/
```

不要：

- 放到根目录。

---

## 十一、文档规范

所有文档：

进入：

```
docs/
```

例如：

```
Architecture.md
Pipeline.md
API.md
Demo.md
```

不要：

- 把大量 Markdown 放在根目录。

---

## 十二、命名规范

Python：

- snake_case

类：

- PascalCase

前端：

- 保持现有风格。

接口：

- 统一命名。

不要：

出现：

- new.py
- temp.py
- utils_new.py
- final.py
- test2.py

---

## 十三、删除规范

删除任何内容之前：

先确认：

- 是否仍被引用。

不要：

- 留下死代码。
- 留下废弃 Prompt。
- 留下重复文件。

---

## 十四、新增功能规范

任何新增功能：

优先：

- 扩展已有模块。

不要：

- 重新创建一套实现。

例如：

已有：

- CardService

不要：

再创建：

- CardService2

---

## 十五、提交规范

每次开发：

- 只完成一个目标。

保持：

- 小改动；
- 小提交；
- 容易回滚。

不要：

- 一次修改整个项目。

---

## 十六、开发完成后必须执行

请自行检查：

- [ ] 是否新增了重复代码？
- [ ] 是否新增了重复 Prompt？
- [ ] 是否新增了重复 API？
- [ ] 是否新增了无用文件？
- [ ] 是否新增了无用目录？
- [ ] 是否修改了无关模块？
- [ ] 是否保持目录规范？

如果存在以上问题，请先整理，再结束开发。

---

## 十七、项目目标

Flower Dance 是一个长期维护项目。

工程规范优先级高于开发速度。

任何协作者都应让项目：

- 更稳定；
- 更统一；
- 更容易维护；

而不是更复杂。

请始终遵循：

> 在正确的位置，以正确的方式，实现正确的功能。