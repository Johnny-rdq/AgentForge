# 后端 LangGraph 条件路由 — 状态驱动的工作流分支
from ..agent.state import WorkflowState

def route_after_decompose(state: WorkflowState) -> str:
    # 后端 拆解完成后 → 进入调度
    return "schedule"

def route_after_schedule(state: WorkflowState) -> str:
    # 后端 调度后 → 有就绪任务则执行，否则汇总
    ready = [s for s in state["subtasks"] if s["status"] == "running"]
    return "execute" if ready else "aggregate"

def route_after_execute(state: WorkflowState) -> str:
    # 后端 执行后 → 有待反思的则反思，否则回调度
    needs_reflect = [s for s in state["subtasks"] if s["status"] == "needs_reflect"]
    return "reflect" if needs_reflect else "schedule"

def route_after_reflect(state: WorkflowState) -> str:
    # 后端 反思后 → 回调度看还有没有待执行的
    pending = [s for s in state["subtasks"] if s["status"] == "pending"]
    # 后端 如果还有待执行且失败次数未超限
    if pending and state.get("error_count", 0) < 3:
        return "schedule"
    # 后端 检查是否还有待反思的（极端情况：依赖任务未通过反思）
    needs_reflect = [s for s in state["subtasks"] if s["status"] == "needs_reflect"]
    if needs_reflect:
        return "reflect"
    # 后端 全部完成 → 汇总
    return "aggregate"

def route_after_aggregate(state: WorkflowState) -> str:
    # 后端 汇总完成 → 结束
    return "__end__"
