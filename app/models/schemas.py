# 后端 Pydantic 数据模型 — 请求/响应校验
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
    task: str = Field(..., description="用户任务描述（含文件分析指令）")
    thread_id: Optional[str] = Field(None, description="会话 ID")
    token: Optional[str] = Field("demo_token", description="访问令牌")
    files_json: Optional[str] = Field(None, description="上传文件元数据 JSON")


class SubtaskInfo(BaseModel):
    id: str
    description: str
    agent_type: str
    depends_on: list[str] = []
    status: SubtaskStatus = SubtaskStatus.pending
    result: Optional[str] = None
    retries: int = 0


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    subtasks: list[SubtaskInfo] = []
    final_result: Optional[str] = None
    error_message: Optional[str] = None


class SSEEvent(BaseModel):
    event: str
    data: Any


class BenchmarkResult(BaseModel):
    task_id: str
    task_description: str
    passed: bool
    subtask_count: int
    total_time_seconds: float
    retry_count: int
    output_quality_score: float


class FileUploadResponse(BaseModel):
    """后端 文件上传结果"""
    filename: str
    saved_path: str
    size_bytes: int
