# 后端 LangGraph 条件路由 — execute 自循环 + reflect 衔接
from app.agent.state import WorkflowState


def route_after_execute(state: WorkflowState) -> str:
    """后端 execute 节点之后的条件路由（状态机）：
    - "execute" → 还有 pending 子任务，execute 节点自循环继续调度
    - "reflect" → 全部执行完且 reflection 开启，进入 Reflector 审查
    - "aggregate" → 无需反思（reflection 关闭），直接汇总交付

    current_stage 由 node_execute 设置：检查 subtasks 状态后决定下一阶段。
    """
    stage = state.get("current_stage", "aggregate")
    if stage == "execute":
        return "execute"
    elif stage == "reflect":
        return "reflect"
    return "aggregate"
