# AgentForge ⚡

基于 **LangGraph + MCP 协议 + FastAPI** 的多 Agent 自主任务系统。自然语言输入 → 自动拆解 → 并行执行 → 汇总交付，支持 token 级流式 SSE 输出。

## 快速开始

### Docker（推荐）

```bash
git clone https://github.com/Johnny-rdq/AgentForge.git
cd AgentForge
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY
docker compose up -d
# 访问 http://localhost:7860
```

### 本地运行

```bash
# 1. 环境配置
cp .env.example .env
# 编辑 .env 填入 LLM_API_KEY

# 2. 安装依赖
pip install -r requirements.txt

# 3. 构建前端
cd frontend && npm install && npm run build && cd ..

# 4. 启动
python -m app.main
# 访问 http://localhost:7860
```

## 执行流程

```
用户输入
  ↓
Master LLM 拆解 → 子任务列表
  ↓
[人工审批] ← 侧边栏一键开关，运行时动态切换
  ↓
线程池并行执行（依赖感知调度）
  ↓  ← execute 自循环，直到全部执行完
[Reflector 反思审查] ← 可选，通过配置开关
  ↓
LLM 汇总合成最终报告
  ↓
SSE 流式输出（token 级实时渲染）
```

**LangGraph DAG**（4-5 节点）：

```
decompose → [human_review] → execute ⇄ execute → [reflect] → aggregate → END
```

> HITL 开启时插入 `human_review`，REFLECTION 开启时插入 `reflect`。基础 3 节点，全开 5 节点。

## 核心特性

- 🧠 **LLM 拆解** — Master Agent 分析意图，自动拆解为类型化子任务
- 🔀 **依赖感知并行** — 无依赖子任务线程池并行，有依赖拓扑排序，execute 节点自循环调度
- 📡 **Token 级流式** — Worker 线程逐 token 推送 SSE，哨兵机制即时结束
- 🔧 **MCP 协议工具** — 7 个标准化工具（搜索/文件/代码/天气），Agent 白名单隔离
- 🛡️ **安全沙箱** — Python 代码 AST 扫描拦截 + 子进程隔离执行
- 📎 **文件分析** — 上传 PDF/Word/TXT/MD，自动预读内容注入 LLM，图表生成自动挂载，点击放大查看
- 🖼️ **图片灯箱** — 对话中的图表/图片点击放大，支持缩放和下载，ESC 一键关闭
- 🔍 **Reflector** — 独立图节点，执行后自动审查+修正，不合格自动重试（最多 1 轮）
- 🎛️ **HITL 人工审批** — 侧边栏一键开关，拆解方案暂停确认后才执行
- 📊 **自动化评测** — 50 题标准基准测试，前端一键触发，实时进度，自动生成通过率/耗时/质量报告
- 💾 **SQLite + ChromaDB** — 会话历史 + 向量记忆，重启不丢失
- 🔒 **会话隔离** — 不同会话的图表/文件互不污染，同一会话内每次任务自动清理旧产物
- 🐳 **Docker 一键部署** — `docker compose up -d` 即用

## Agent 类型

| Agent | 工具 | 说明 |
|-------|------|------|
| `researcher` | 搜索 / 天气 / 读文件 | 信息调研 |
| `analyst` | 执行 Python / 读文件 / 搜索 | 数据分析 |
| `visualizer` | 执行 Python | 图表生成（matplotlib） |
| `data_cleaner` | 执行 Python / 读文件 | 数据清洗 |
| `writer` | 读文件 | 文档撰写 |
| `executor` | 执行 Python / 安装包 | 代码执行 |
| `tester` | 执行 Python / 读文件 | 测试代码 |
| `reviewer` | 读文件 | 代码审查 |
| `translator` | — | 翻译 |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/health` | 健康检查 |
| GET | `/api/v1/sessions` | 会话列表 |
| POST | `/api/v1/sessions` | 创建会话 |
| GET | `/api/v1/sessions/{id}/messages` | 会话历史消息 |
| DELETE | `/api/v1/sessions/{id}` | 删除会话 |
| POST | `/api/v1/chat/stream` | SSE 流式对话 |
| POST | `/api/v1/chat/resume` | HITL 审批恢复 |
| POST | `/api/v1/chat/cancel` | 取消任务 |
| POST | `/api/v1/upload` | 上传文件 |
| GET | `/api/v1/settings/hitl` | 获取 HITL 状态 |
| POST | `/api/v1/settings/hitl` | 切换 HITL 开关 |
| GET | `/api/v1/benchmark/reports` | 评测报告列表 |
| GET | `/api/v1/benchmark/reports/{name}` | 评测报告详情 |
| GET | `/api/v1/benchmark/status` | 评测运行进度 |
| POST | `/api/v1/benchmark/run` | 触发评测运行 |

### SSE 事件类型

| event | 说明 |
|-------|------|
| `thinking` | 当前执行阶段 |
| `subtask_update` | 子任务拆解结果 |
| `token` | 流式输出文本 |
| `review_required` | HITL 审批请求（含子任务计划） |
| `result` | 最终结果元数据 |
| `done` | 任务结束（含 elapsed） |
| `error` | 异常信息 |

## 配置

全部通过 `.env` 环境变量配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_API_KEY` | - | **必填**，LLM API 密钥 |
| `LLM_MODEL` | `qwen-plus` | 模型名称 |
| `LLM_PROVIDER` | `agnes` | 服务商（agnes / dashscope / openai / deepseek） |
| `LLM_BASE_URL` | 自动匹配 | 自定义 API 地址（覆盖 provider 默认值） |
| `MAX_WORKERS` | `6` | 最大并行 Worker 数 |
| `HITL_ENABLED` | `false` | 人工审批（侧边栏可运行时切换） |
| `REFLECTION_ENABLED` | `false` | Reflector 自反思审查 |
| `WORKFLOW_TIMEOUT` | `300` | 工作流超时秒数 |

## 项目结构

```
AgentForge/
├── app/
│   ├── main.py              # FastAPI 入口 + 静态挂载
│   ├── api/
│   │   ├── chat.py          # SSE 流式对话 + HITL 审批 + 设置接口
│   │   ├── session.py       # 会话 CRUD
│   │   ├── upload.py        # 文件上传
│   │   └── benchmark_api.py # 评测 API（报告查询 + 触发运行）
│   ├── agent/
│   │   ├── state.py         # LangGraph WorkflowState 定义
│   │   ├── master.py        # Master LLM 任务拆解
│   │   ├── worker.py        # Worker 执行（直接模式 + FC 模式）
│   │   └── reflector.py     # Reflector 质量审查修正
│   ├── graph/
│   │   ├── workflow.py      # DAG 组装 + MemorySaver（3-5 节点）
│   │   ├── nodes.py         # decompose / human_review / execute / reflect / aggregate
│   │   └── edges.py         # execute 自循环 + reflect 条件路由
│   ├── core/
│   │   ├── config.py        # 全局配置（多 Provider）
│   │   ├── llm.py           # OpenAI 兼容 LLM 客户端
│   │   ├── mcp_manager.py   # MCP 工具注册中心
│   │   └── session_context.py # 会话隔离上下文（ContextVar）
│   ├── tools/
│   │   ├── mcp_server.py    # MCP 工具注册入口
│   │   ├── file_tools.py    # 文件读写 + PDF OCR
│   │   ├── code_tools.py    # Python AST 安全沙箱
│   │   └── search_tools.py  # Tavily 搜索 + 天气
│   ├── memory/
│   │   ├── sql_store.py     # SQLite 会话/任务持久化
│   │   └── vector_store.py  # ChromaDB 向量记忆
│   ├── eval/
│   │   ├── tasks.py         # 50 个标准评测任务
│   │   └── benchmark.py     # 评测执行引擎
│   └── models/schemas.py    # Pydantic 数据模型
├── frontend/                # React + TailwindCSS SPA
│   ├── src/components/
│   │   ├── ChatArea.jsx     # 消息列表 + 欢迎引导
│   │   ├── ChatMessage.jsx  # 单条消息（Markdown 渲染 + 图片点击）
│   │   ├── ImageViewer.jsx  # 图片灯箱（放大/缩小/下载）
│   │   ├── MessageInput.jsx # 输入框（文件上传 + 发送/停止）
│   │   ├── Sidebar.jsx      # 会话侧边栏
│   │   ├── WorkflowPanel.jsx# 执行过程可视化面板
│   │   └── ErrorBoundary.jsx# React 错误边界
│   ├── src/hooks/
│   │   ├── useChat.js       # SSE 流式对话 Hook
│   │   └── useSessions.js   # 会话管理 Hook
│   └── dist/                # 构建产物（Vite）
├── data/
│   ├── uploads/             # 用户上传文件
│   ├── generated/           # 图表等生成文件（挂载 /generated）
│   └── chroma_db/           # ChromaDB 持久化
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```
