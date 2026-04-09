长篇网文 AI 创作引擎
> 长篇网文 AI 创作引擎 — 基于 LangGraph 多 Agent 架构，支持百万字级小说的分层记忆与迭代评审。

---

## 核心特性

| 特性 | 说明 |
|------|------|
| **多 Agent 协作** | Planner × Writer × Critic 三节点协作，自动路由迭代 |
| **双层评审** | 架构层（情节/结构/伏笔） + 文字层（文笔/表达）独立反馈 |
| **分层记忆** | 全局记忆 → 卷记忆 → 章节记忆，跨百万字保持一致性 |
| **迭代控制** | 最多 4 轮迭代，评分 ≥8 分自动定稿，支持连续 keep 死循环打破 |
| **情节插入** | 插入新情节时自动分析影响范围，避免与既有设定冲突 |
| **全程可观测** | 完整 SQLite 日志，所有 Agent 调用、评分、路由决策全程记录 |
| **多入口** | 终端对话 / Streamlit Web UI，零代码也能用 |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                      用户输入                            │
│  (创作意图 + 每章写作指令)                                │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│                    Planner Agent                         │
│  · plan_macro：宏观规划（大故事框架 / 世界观 / 人物弧线）  │
│  · plan_phase：阶段性规划（10-30章为单位的小故事大纲）    │
│  · chapter_guide：提取本章写作指引                        │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│                    Writer Agent                          │
│  · 基于策划方案 + 动态记忆 + 章节指引写正文               │
│  · 遵守世界规则约束，不擅自改设定                         │
│  · 字数要求：2500-3500 字/章                             │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│                    Critic Agent                          │
│  · 五维评分（情节/文笔/伏笔/人物弧线/冲突）               │
│  · 双层反馈：arch_action（架构）/ prose_action（文字）    │
│  · JSON 结构化输出，Markdown fallback 兼容               │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│                 路由决策节点                              │
│  · revise  → 打回 Planner 修订策划                       │
│  · rewrite → 打回 Writer 重写正文                        │
│  · keep    → 累计连续 keep 次数，触发 force_write 打破   │
│  · score≥8 → 进入 memory_update → save_chapter → END   │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│               Memory Update 节点                         │
│  · 从正文中提取 MemoryDelta（人物变化/战力突破/伏笔）     │
│  · 更新全局记忆 / 卷记忆 / 章节记忆                       │
│  · 提取并保存伏笔线索                                    │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│               Save Chapter 节点                          │
│  · 章节内容写入 .md 文件                                 │
│  · 章节记录写入 SQLite（标题/大纲/正文/评分/状态）       │
└─────────────────────────────────────────────────────────┘
```

---

## 项目结构

```
writing_langgraph/
├── writing_langgraph/
│   ├── __init__.py
│   ├── agents.py          # Planner / Writer / Critic Agent 实现
│   ├── graph.py           # LangGraph 工作流图构建
│   ├── state.py           # 分层状态定义（WritingState 等）
│   ├── schemas.py         # CriticResponse 结构化响应
│   ├── prompts.py         # 所有 System Prompt
│   ├── persist.py         # 章节保存（文件 + 数据库）
│   ├── utils.py           # 评分解析 / 文本工具函数
│   ├── db/
│   │   ├── __init__.py    # 数据库连接与事务管理
│   │   ├── models.py      # ORM 数据模型
│   │   └── schema.sql     # 完整数据库 Schema
│   ├── memory/
│   │   ├── tools.py       # @tool 函数：供 LLM 查询记忆
│   │   ├── chapter_memory.py   # 章节记忆 CRUD
│   │   ├── global_memory.py    # 全局记忆 CRUD
│   │   ├── volume_memory.py    # 卷记忆 CRUD
│   │   ├── memory_parser.py    # 记忆文本结构化解析
│   │   └── plot_insert.py      # 情节插入影响分析
│   ├── retrieval/
│   │   └── query_engine.py     # RAG 查询引擎（备用）
│   └── templates/
│       ├── tropes.py           # 网文套路模板
│       └── power_systems.py    # 战力体系模板
│
├── terminal_chat.py        # 终端对话入口（自然语言交互）
├── streamlit_app.py        # Streamlit Web UI
├── test_project.py         # 集成测试
├── test_full_flow.py       # 完整流程测试
├── test_write.py           # 写作流程测试
├── requirements.txt
└── README.md
```

---

## 快速开始

### 环境要求

- Python 3.10+
- 一个支持 function calling 的 LLM API（OpenAI / MiniMax / DeepSeek 等）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置 API Key

```bash
# 环境变量（推荐）
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://api.minimaxi.com/v1"   # 可选，默认为 MiniMax
export OPENAI_MODEL="minimax-m2.7"                       # 可选
```

### 启动终端对话

```bash
python terminal_chat.py
```

**对话示例：**

```
你: 写第一章，主角是个修仙少年，杂灵根，被全村人看不起
你: 继续写第二章
你: 查看状态
你: 修改第一章
```

### 启动 Web UI

```bash
streamlit run streamlit_app.py --server.port 8501
```

---

## 数据库 Schema

完整支持以下数据表：

| 表名 | 用途 |
|------|------|
| `novel_metadata` | 小说元数据（标题/类型/世界观规则） |
| `character` | 人物表（名称/境界/位置/心理状态/物品栏） |
| `character_relationship` | 人物关系多对多表 |
| `power_level_definition` | 战力/境界体系定义 |
| `power_change_log` | 战力突破变化日志 |
| `item` | 道具/功法/宝物表 |
| `item_log` | 道具获得/使用日志 |
| `plot_thread` | 伏笔/情节线表（含状态追踪） |
| `volume` | 卷表 |
| `chapter` | 章节表（正文/大纲/评分/状态） |
| `memory_global` | 全局记忆（版本化存储） |
| `memory_volume` | 卷记忆 |
| `memory_chapter` | 章节记忆（每次迭代独立记录） |
| `trope_template` | 网文套路模板 |
| `small_story_tracking` | 小故事追踪（重启后恢复规划状态） |
| `parallel_task` | 并行写作任务追踪 |

---

## 分层记忆系统

### 三层架构

```
GlobalMemory（全局记忆）
  └─ 世界规则 / 战力体系 / 人物模板 / 主线伏笔 / 核心约束
     │
     ▼
VolumeMemory（卷记忆）
  └─ 本卷人物状态 / 活跃伏笔 / 弧光进度 / 伏笔回收计划
     │
     ▼
ChapterMemory（章节记忆）
  └─ 场景细节 / 情节点 / 本章正文摘要
```

### 触发更新时机

| 记忆层 | 更新时机 |
|--------|----------|
| 全局记忆 | 新角色登场 / 大境界突破 / 主线伏笔回收 |
| 卷记忆 | 每章完成后增量更新 |
| 章节记忆 | 章节定稿后保存 |

### 伏笔追踪

 Critic 审阅后自动从正文中提取伏笔线索，存入 `plot_thread` 表并追踪状态：

- `planted` → `foreshadowed` → `resolved`

---

## 工作流详解

### 评分与迭代

 Critic 返回 0-10 分，8 分及以上视为达标可定稿。未达标时：

- `arch_action = revise` → 路由至 **Planner**，修订策划方案
- `prose_action = rewrite` → 路由至 **Writer**，重写正文
- `prose_action = keep` 且连续 2 次 → 触发 `force_write`，强制大幅重构

### 小故事追踪

系统以**小故事（Phase）** 为单位组织章节（每 10-30 章）：

- 小故事有自己的 `phase_start_ch` / `phase_end_ch` 范围
- 当前小故事写完时，Planner 自动生成下一个小故事
- 追踪状态持久化到 `small_story_tracking` 表，重启后可恢复

### 情节插入

当用户要求插入新情节时，Planner 会：

1. 调用 `get_full_context` 加载完整上下文
2. 分析新情节对现有章节的影响（强影响区 / 弱影响区 / 无影响区）
3. 检测与既有设定的冲突
4. 输出包含伏笔更新、新增角色的插入计划
5. 等待用户确认后执行

---

## 接口参考

### `terminal_chat.py` — 终端对话

```python
# 环境变量
OPENAI_API_KEY=xxx
OPENAI_BASE_URL=https://api.minimaxi.com/v1
OPENAI_MODEL=minimax-m2.7

# 运行
python terminal_chat.py
```

支持意图识别：`写`、`继续`、`修改`、`查看`、`插入情节`

### `streamlit_app.py` — Web UI

```bash
streamlit run streamlit_app.py
```

### 核心函数

```python
from writing_langgraph.graph import build_writing_graph
from writing_langgraph.state import initial_state

# 构建工作流
graph = build_writing_graph(llm)

# 初始化状态
state = initial_state(
    story_idea="创作意图",
    chapter_task="本章写作任务",
    chapter_no=1,
    novel_id=1,
    max_iterations=4,
    score_pass=8.0,
)

# 执行工作流
final_state = graph.invoke(state)
```

---

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_iterations` | 4 | 每章最大迭代轮数 |
| `score_pass` | 8.0 | 达标评分（0-10） |
| `temperature_plan` | 0.7 | Planner 温度 |
| `temperature_write` | 0.85 | Writer 温度 |
| `temperature_critic` | 0.35 | Critic 温度 |
| `consecutive_keep_limit` | 2 | 触发 force_write 的连续 keep 次数 |

---

## 技术栈

- **[LangGraph](https://github.com/langchain-ai/langgraph)** — 多 Agent 状态机工作流
- **LangChain Core** — LLM 调用 / Messages / Tools
- **SQLite** — 零依赖持久化存储
- **Streamlit** — Web 可视化界面
- **Pydantic / dataclasses** — 类型安全的数据模型

---

## License

MIT
