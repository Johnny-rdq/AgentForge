# 后端 API 数据模型定义
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, Any

class TaskStatus(str, Enum):
    pending = "pending"
    decomposing = "decomposing"
    executing = "executing"
    reflecting = "reflecting"
    completed = "completed"
    failed = "failed"

class SubtaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    reflecting = "reflecting"
    done = "done"
    failed = "failed"

class ChatRequest(BaseModel):
    # 后端 聊天请求体
    task: str = Field(..., description="用户任务描述")
    thread_id: Optional[str] = Field(None, description="会话 ID")
    token: Optional[str] = Field("demo_token", description="访问令牌")

class SubtaskInfo(BaseModel):
    # 后端 子任务信息
    id: str
    description: str
    agent_type: str
    depends_on: list[str] = []
    status: SubtaskStatus = SubtaskStatus.pending
    result: Optional[str] = None
    retries: int = 0

class TaskResponse(BaseModel):
    # 后端 任务状态响应
    task_id: str
    status: TaskStatus
    subtasks: list[SubtaskInfo] = []
    final_result: Optional[str] = None
    error_message: Optional[str] = None

class SSEEvent(BaseModel):
    # 后端 SSE 事件
    event: str
    data: Any

class BenchmarkResult(BaseModel):
    # 后端 评测结果
    task_id: str
    task_description: str
    passed: bool
    subtask_count: int
    total_time_seconds: float
    retry_count: int
    output_quality_score: float
