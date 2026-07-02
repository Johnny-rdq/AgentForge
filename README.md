# AgentForge ⚡

基于 **LangGraph + MCP 协议 + FastAPI** 的多 Agent 自主任务系统。自然语言输入 → 自动拆解 → 并行执行 → 汇总交付，支持 token 级流式 SSE 输出。

## 快速开始

### 1. 环境准备

```bash
# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置

```bash
copy .env.example .env
# 编辑 .env，填入 LLM_API_KEY
```

### 3. 启动

```bash
start_api.bat
# 或者
python app/main.py
```

访问 **http://localhost:7860**

## 访问地址

- **前端界面**：http://localhost:7860
- **API 文档**：http://localhost:7860/docs
- **健康检查**：http://localhost:7860/health

## 核心特性

- 🧠 **LLM 拆解** — Master Agent 分析意图，自动拆解为类型化子任务
- 🔀 **依赖感知并行** — 无依赖子任务线程池并行，有依赖拓扑排序
- 📡 **Token 级流式** — Worker 线程逐 token 推送 SSE
- 🔧 **MCP 协议工具** — 7 个标准化工具（搜索/文件/代码/天气）
- 🛡️ **安全沙箱** — Python 代码 AST 扫描拦截 + 子进程隔离执行
- 📎 **文件分析** — 上传 PDF/Word/TXT/MD，自动预读内容注入 LLM
- 🖼️ **图片灯箱** — 对话中的图表/图片点击放大，支持缩放和下载
- 🔍 **Reflector** — 执行后自动审查+修正，不合格自动重试
- 🎛️ **HITL 人工审批** — 拆解方案暂停确认后才执行
- 📊 **自动化评测** — 50 题标准基准测试，自动生成报告
- 💾 **PostgreSQL + 向量记忆** — 会话持久化 + 语义记忆搜索（Milvus / Zilliz Cloud）
- 🔒 **会话隔离** — 不同会话的图表/文件互不污染

## 向量记忆配置

AgentForge 使用 Milvus 向量数据库存储历史任务语义记忆，Master 拆解时自动搜索相似历史任务作为参考。

### 方式一：Zilliz Cloud（推荐，免费 1GB）

无需 Docker，注册即用：

```env
# .env
MILVUS_URI=https://in03-xxx.api.zillizcloud.com   # 集群端点
MILVUS_TOKEN=你的APIKey                            # API Key
```

> 去 [cloud.zilliz.com](https://cloud.zilliz.com) 创建免费集群，获取端点和 Key。

### 方式二：本地 Docker

```bash
docker compose up -d milvus etcd minio
```

```env
# .env
MILVUS_HOST=localhost
MILVUS_PORT=19530
```

### 方式三：跳过（使用本地 JSON 存储）

```env
# .env
SKIP_MILVUS=true
```

## API 接口

### 聊天接口

```bash
POST /api/v1/chat/stream
Content-Type: application/json

{
  "task": "帮我写一个Python程序，计算斐波那契数列",
  "thread_id": "session_123"
}
```

### 恢复对话

```bash
POST /api/v1/chat/resume
Content-Type: application/json

{
  "task_id": "task_id",
  "action": "approve",
  "subtasks": [...],
  "thread_id": "session_123"
}
```

### 其他接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/health` | 健康检查 |
| GET | `/api/v1/sessions` | 会话列表 |
| POST | `/api/v1/sessions` | 创建会话 |
| DELETE | `/api/v1/sessions/{id}` | 删除会话 |
| POST | `/api/v1/upload` | 上传文件 |
| POST | `/api/v1/benchmark/run` | 触发评测 |

## 配置说明

```env
# ========== LLM 配置（必填）==========
LLM_API_KEY=你的API密钥
LLM_MODEL=qwen-plus
LLM_PROVIDER=agnes
LLM_BASE_URL=https://apihub.agnes-ai.com/v1

# ========== 服务配置 ==========
APP_HOST=0.0.0.0
APP_PORT=7860

# ========== Agent 配置 ==========
MAX_WORKERS=6
MAX_RETRIES=2
HITL_ENABLED=false
REFLECTION_ENABLED=false
WORKFLOW_TIMEOUT=300

# ========== PostgreSQL 数据库 ==========
PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=agentforge
PG_USER=agentforge
PG_PASSWORD=agentforge123

# ========== Milvus / Zilliz Cloud 向量记忆 ==========
# 推荐：Zilliz Cloud（免费 1GB，无需 Docker）
MILVUS_URI=https://in03-xxx.api.zillizcloud.com
MILVUS_TOKEN=你的APIKey
# 本地 Docker（二选一）
# MILVUS_HOST=localhost
# MILVUS_PORT=19530
# 跳过向量记忆
# SKIP_MILVUS=true
```

## Agent 类型

| Agent | 功能 | 工具 |
|-------|------|------|
| `researcher` | 搜索/天气/读文件 | search_internet, fetch_weather, read_file |
| `analyst` | 数据分析 | execute_python, read_file, search_internet |
| `visualizer` | 图表生成 | execute_python |
| `data_cleaner` | 数据清洗 | execute_python, read_file |
| `writer` | 文档撰写 | read_file |
| `executor` | 代码执行 | execute_python, install_package |
| `tester` | 测试代码 | execute_python, read_file |
| `reviewer` | 代码审查 | read_file |
| `translator` | 翻译 | — |

## 项目结构

```
AgentForge/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── api/                 # API 路由（chat, session, upload, benchmark）
│   ├── agent/               # Agent 实现（master, worker, reflector）
│   ├── graph/               # LangGraph 工作流节点
│   ├── core/                # 核心组件（config, llm, mcp_manager, logger）
│   ├── tools/               # MCP 工具（file, code, search）
│   ├── memory/              # 存储层（sql_store, vector_store）
│   └── models/              # 数据模型
├── data/                    # 运行时数据（uploads, generated, benchmarks）
├── frontend/                # 前端 React SPA
├── logs/                    # 日志文件
├── docker-compose.yml       # Docker 编排（PostgreSQL + Milvus）
└── *.bat                    # Windows 启动脚本
```

## 开发模式

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 7860 --reload
```

## 生产环境

```bash
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:7860
```
