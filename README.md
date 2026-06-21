# AgentForge ⚡

基于 **LangGraph + MCP 协议 + FastAPI** 的多 Agent 自主任务系统。自然语言输入，自动拆解→调度→执行→交付，支持 token 级流式输出。

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

## 架构

```
用户输入 → 快速通道(regex 分类) → Worker 直接执行 → 流式输出 → 完成
                ↓ (复杂任务)
         Master LLM 拆解 → execute ⇄ execute → aggregate → 完成
```

精简 3 节点 Graph：**decompose → execute（自循环调度）→ aggregate**

## 核心特性

- ⚡ **超级快速通道** — 搜索/读文件/翻译/问答等 90% 场景 regex 秒判，1 次 LLM 调用出结果
- 📡 **Token 级流式输出** — Worker 线程逐 token 推送，前端实时渲染，哨兵机制确保内容出完立刻结束
- 🔧 **MCP 协议工具** — 7 个标准化工具（搜索/文件/代码/天气），Agent 工具白名单隔离
- 🧵 **依赖感知并行** — 无依赖子任务线程池并行执行，有依赖拓扑排序串行
- 💾 **SQLite 持久化** — 会话 + 任务历史 + 耗时全记录，刷新不丢失
- 🎛️ **HITL 人工审批** — 可选开启，拆解方案需人工确认后才执行
- 📎 **文件上传** — PDF/Word/TXT/MD/图片，支持 OCR 解析
- 🐳 **Docker 一键部署** — `docker compose up -d` 即用

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

### SSE 事件类型

| event | 说明 |
|-------|------|
| `thinking` | 当前执行阶段 |
| `subtask_update` | 子任务拆解结果 |
| `token` | 流式输出文本 |
| `result` | 任务元数据（含耗时） |
| `done` | 任务结束（含 elapsed） |
| `error` | 异常信息 |

## 配置

全部通过 `.env` 环境变量配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_API_KEY` | - | **必填**，LLM API 密钥 |
| `LLM_MODEL` | `qwen-plus` | 模型名称 |
| `LLM_PROVIDER` | `agnes` | 服务商（agnes/dashscope/openai） |
| `MAX_WORKERS` | `6` | 最大并行 Worker 数 |
| `HITL_ENABLED` | `false` | 人工审批开关 |
| `REFLECTION_ENABLED` | `false` | 自反思开关 |
| `WORKFLOW_TIMEOUT` | `300` | 工作流超时秒数 |

## 项目结构

```
AgentForge/
├── app/
│   ├── main.py              # FastAPI 入口，挂载前端 SPA
│   ├── api/
│   │   ├── chat.py          # SSE 流式对话（含快速通道 + 哨兵机制）
│   │   ├── session.py       # 会话管理 CRUD
│   │   └── upload.py        # 文件上传
│   ├── agent/
│   │   ├── state.py         # LangGraph 工作流状态
│   │   ├── master.py        # Master 任务拆解 + regex 快速分类
│   │   └── worker.py        # Worker 执行（直接模式 + FC 模式）
│   ├── graph/
│   │   ├── workflow.py      # 精简 3 节点 DAG 组装
│   │   ├── nodes.py         # decompose / execute(调度+执行) / aggregate
│   │   └── edges.py         # 条件路由
│   ├── core/
│   │   ├── config.py        # 全局配置
│   │   ├── llm.py           # LLM 客户端（流式 + 非流式）
│   │   └── mcp_manager.py   # MCP 工具注册中心
│   ├── tools/
│   │   ├── file_tools.py    # 文件读写 + OCR
│   │   ├── code_tools.py    # Python 沙箱执行
│   │   └── search_tools.py  # 网络搜索
│   ├── memory/
│   │   ├── sql_store.py     # SQLite 会话/任务历史
│   │   └── vector_store.py  # ChromaDB 语义记忆
│   └── models/schemas.py    # Pydantic 数据模型
├── frontend/                # React + TailwindCSS 前端
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```
