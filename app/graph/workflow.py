# 后端 LangGraph 工作流组装 — 动态图 + Human-in-the-Loop + Checkpointer
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from ..agent.state import WorkflowState
from .nodes import (
    node_decompose,
    node_human_review,
    node_schedule,
    node_execute,
    node_reflect,
    node_aggregate,
)
from .edges import (
    route_after_schedule,
    route_after_execute,
    route_after_reflect,
)

def build_workflow() -> StateGraph:
    # 后端 构建多Agent工作流图
    workflow = StateGraph(WorkflowState)

    # 后端 添加处理节点
    workflow.add_node("decompose", node_decompose)
    workflow.add_node("human_review", node_human_review)  # Human-in-the-Loop 审批
    workflow.add_node("schedule", node_schedule)
    workflow.add_node("execute", node_execute)
    workflow.add_node("reflect", node_reflect)
    workflow.add_node("aggregate", node_aggregate)

    # 后端 设置入口
    workflow.set_entry_point("decompose")

    # 后端 连线：拆解 → 人工审批 → 调度
    workflow.add_edge("decompose", "human_review")
    workflow.add_edge("human_review", "schedule")

    # 后端 条件分支
    workflow.add_conditional_edges("schedule", route_after_schedule, {
        "execute": "execute",
        "aggregate": "aggregate",
    })

    workflow.add_conditional_edges("execute", route_after_execute, {
        "reflect": "reflect",
        "schedule": "schedule",
    })

    workflow.add_conditional_edges("reflect", route_after_reflect, {
        "schedule": "schedule",
        "reflect": "reflect",
        "aggregate": "aggregate",
    })

    workflow.add_edge("aggregate", END)

    return workflow

# 后端 内存 checkpointer（支持 interrupt/resume）
checkpointer = MemorySaver()

# 后端 编译好的图实例
agent_graph = None

def get_agent_graph() -> StateGraph:
    # 后端 获取或创建编译好的 Agent 工作流图（带 checkpointer）
    global agent_graph
    if agent_graph is None:
        workflow = build_workflow()
        agent_graph = workflow.compile(checkpointer=checkpointer)
        print("[Graph] 多Agent工作流图已编译（含 HITL + 记忆）")
    return agent_graph
