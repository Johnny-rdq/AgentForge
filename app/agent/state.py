# 后端 LangGraph 工作流状态定义
import uuid
from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class SubtaskDef(TypedDict):
    """后端 子任务数据结构"""
    id: str
    description: str
    agent_type: str
    depends_on: list[str]  # 前置依赖的子任务 ID 列表
    status: str  # pending → running → needs_reflect → done | failed
    result: Optional[str]
    retries: int


class WorkflowState(TypedDict):
    """后端 多 Agent 工作流全局状态（LangGraph StateGraph 状态字典）"""
    task_id: str
    user_input: str
    subtasks: list[SubtaskDef]
    # 后端 add_messages 自动累加消息而非覆盖
    messages: Annotated[list[BaseMessage], add_messages]
    current_stage: str
    error_count: int
    final_output: Optional[str]
    conversation_history: list[dict]  # 后端 最近几轮对话，每轮 {"role": ..., "content": ...}


def create_initial_state(user_input: str, conversation_history: list[dict] = None) -> WorkflowState:
    """后端 创建工作流初始状态"""
    return WorkflowState(
        task_id=str(uuid.uuid4()),
        user_input=user_input,
        subtasks=[],
        messages=[],
        current_stage="decompose",
        error_count=0,
        final_output=None,
        conversation_history=conversation_history or [],
    )
