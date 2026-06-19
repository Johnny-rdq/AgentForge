# 后端 LangGraph 工作流状态定义
import uuid
from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class SubtaskDef(TypedDict):
    # 后端 子任务结构
    id: str
    description: str
    agent_type: str  # 动态分配的 Agent 类型
    depends_on: list[str]  # 依赖的子任务 ID 列表
    status: str  # pending | running | done | failed
    result: Optional[str]
    retries: int

class WorkflowState(TypedDict):
    # 后端 多Agent工作流全局状态
    task_id: str
    user_input: str
    subtasks: list[SubtaskDef]
    messages: Annotated[list[BaseMessage], add_messages]
    current_stage: str  # decompose | schedule | execute | reflect | aggregate | done
    error_count: int
    final_output: Optional[str]

def create_initial_state(user_input: str) -> WorkflowState:
    # 后端 初始化工作流状态
    return WorkflowState(
        task_id=str(uuid.uuid4()),
        user_input=user_input,
        subtasks=[],
        messages=[],
        current_stage="decompose",
        error_count=0,
        final_output=None,
    )
