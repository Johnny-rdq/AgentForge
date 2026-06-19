# AgentForge — MCP 多Agent 自主任务系统

基于 **LangGraph + MCP 协议 + FastAPI** 构建的多Agent自主任务执行系统。用户自然语言描述需求，系统自动拆解→动态生成Agent→依赖感知调度→并行执行→自反思修正→交付结果。

## 核心特性

- **动态Agent生成** — 根据任务类型自动创建对应Worker Agent，非固定管线
- **MCP协议工具标准化** — 所有工具通过MCP Server注册，面试免检
- **依赖感知并行调度** — 无依赖子任务并行执行，有依赖串行等待
- **自反思修正** — Agent输出后自动检查质量，不通过则自己修改
- **CrewAI对比实验** — 同场景下对比LangGraph动态vs CrewAI固定方案
- **50任务基准评测** — 覆盖数据分析/可视化/代码生成/调研/报告/综合6类

## 架构

```
用户："分析销售数据，输出报告"

Master Agent
    │
    ├── 任务拆解 ──→ 3个子任务
    │   ├── sub_1: 数据清洗 (data_cleaner)
    │   ├── sub_2: 统计分析 (analyst)     ← 依赖 sub_1
    │   └── sub_3: 生成报告 (writer)       ← 依赖 sub_2
    │
    ├── 依赖感知调度 ──→ sub_1 就绪
    │
    ├── 并行执行 (无依赖的并行) ──→ sub_1 完成
    │
    ├── 调度 ──→ sub_2 就绪，执行
    │
    ├── 自反思 ──→ sub_2 输出不完整，自动修正
    │
    ├── 调度 ──→ sub_3 就绪，执行
    │
    └── 汇总交付 ──→ 完整分析报告
```

## 技术栈

| 层级 | 技术 |
|------|------|
| **编排引擎** | LangGraph (StateGraph) + 动态图 |
| **工具协议** | MCP (Model Context Protocol) |
| **LLM** | 阿里云 DashScope (qwen-plus) |
| **Web框架** | FastAPI + SSE 流式 |
| **Agent记忆** | ChromaDB + SQLite |
| **对比实验** | CrewAI |
| **数据处理** | Pandas + Matplotlib |
| **容器化** | Docker |

## 快速开始

```bash
# 1. 配置环境
cp .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务
python -m app.main

# 4. 测试
curl -X POST http://localhost:7860/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"task": "分析这份销售数据CSV，输出统计分析结果"}'
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 服务状态 |
| POST | `/api/v1/chat/stream` | SSE流式任务执行 |

### SSE 事件类型

| event | 说明 |
|-------|------|
| `thinking` | 当前执行阶段 |
| `subtask_update` | 子任务拆解结果 |
| `token` | 流式输出文本 |
| `result` | 最终交付结果 |
| `done` | 任务结束 |
| `error` | 异常信息 |

## 运行评测

```bash
# 运行50任务基准评测
python -m app.eval.benchmark
```

评测维度：通过率 / 平均耗时 / 质量评分 / 分类通过率

## 项目结构

```
AgentForge/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── api/chat.py          # SSE 流式端点
│   ├── core/
│   │   ├── config.py        # 全局配置
│   │   ├── llm.py           # LLM 实例
│   │   └── mcp_manager.py   # MCP 工具管理
│   ├── agent/
│   │   ├── state.py         # 工作流状态
│   │   ├── master.py        # Master 任务拆解
│   │   ├── worker.py        # Worker 动态执行
│   │   └── reflector.py     # 自反思修正
│   ├── graph/
│   │   ├── workflow.py      # 图组装
│   │   ├── nodes.py         # 图节点
│   │   └── edges.py         # 条件路由
│   ├── tools/
│   │   ├── mcp_server.py    # MCP 注册入口
│   │   ├── file_tools.py    # 文件工具
│   │   ├── code_tools.py    # 代码执行
│   │   └── search_tools.py  # 搜索工具
│   ├── memory/
│   │   ├── vector_store.py  # ChromaDB 语义记忆
│   │   └── sql_store.py     # SQLite 结构化记忆
│   ├── eval/
│   │   ├── benchmark.py     # 评测跑分器
│   │   └── tasks.py         # 50标准任务集
│   └── models/schemas.py    # 数据模型
├── crewai_version/          # CrewAI 对比实验
├── frontend/                # React 前端
├── data/                    # 运行时数据
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 与旧项目差异

| | Enterprise_Agent_System | AgentForge |
|---|---|---|
| Agent生成 | 固定4角色管线 | **动态按需生成** |
| 执行模式 | 线性排队 | **依赖感知并行** |
| 工具标准化 | 硬编码函数 | **MCP协议** |
| 质量控制 | 外部审核Agent | **自反思+外检** |
| 方案对比 | 无 | **CrewAI对照实验** |
| 基准评测 | 无 | **50任务自动化跑分** |
