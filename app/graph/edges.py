# 后端 LangGraph 条件路由 — execute 自循环 + reflect 衔接
from app.agent.state import WorkflowState


def route_after_execute(state: WorkflowState) -> str:
    """后端 执行后路由：pending → 继续 execute；executed → reflect；done → aggregate"""
    stage = state.get("current_stage", "aggregate")
    # 后端 current_stage 由 node_execute 设置：execute/reflect/aggregate
    if stage == "execute":
        return "execute"
    elif stage == "reflect":
        return "reflect"
    return "aggregate"
