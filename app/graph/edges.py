# 后端 LangGraph 条件路由 — 精简为单一路由
from app.agent.state import WorkflowState


def route_after_execute(state: WorkflowState) -> str:
    """后端 执行后：还有待处理 → 继续执行（循环）；全部完成 → 汇总"""
    return state.get("current_stage", "aggregate")
