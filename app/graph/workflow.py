# 后端 LangGraph 工作流组装 — 精简 DAG：decompose → execute ⇄ execute → aggregate → END
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.core.logger import get_logger
from app.agent.state import WorkflowState
from app.graph.nodes import node_decompose, node_human_review, node_execute, node_aggregate
from app.graph.edges import route_after_execute
from app.core.config import settings

logger = get_logger(__name__)


def build_workflow() -> StateGraph:
    """后端 构建精简多 Agent DAG 工作流

    路径：decompose → (human_review? 仅HITL开启) → execute ⇄ execute → aggregate → END
    execute 节点内部完成调度+执行+自检，自动循环直到全部子任务完成
    """
    workflow = StateGraph(WorkflowState)

    workflow.add_node("decompose", node_decompose)
    workflow.add_node("execute", node_execute)
    workflow.add_node("aggregate", node_aggregate)

    workflow.set_entry_point("decompose")

    # 后端 HITL 审批：开启时在 decompose 和 execute 之间插入 human_review
    if settings.hitl_enabled:
        workflow.add_node("human_review", node_human_review)
        workflow.add_edge("decompose", "human_review")
        workflow.add_edge("human_review", "execute")
        logger.info("HITL 审批已启用")
    else:
        workflow.add_edge("decompose", "execute")

    # 后端 execute 自循环：还有未完成任务 → 回到 execute；全部完成 → aggregate
    workflow.add_conditional_edges("execute", route_after_execute, {
        "execute": "execute",
        "aggregate": "aggregate",
    })

    workflow.add_edge("aggregate", END)

    return workflow


# 后端 内存 Checkpointer（支持 interrupt/resume）
checkpointer = MemorySaver()

agent_graph = None


def get_agent_graph() -> StateGraph:
    """后端 懒加载单例：首次调用时编译，后续复用"""
    global agent_graph
    if agent_graph is None:
        workflow = build_workflow()
        agent_graph = workflow.compile(checkpointer=checkpointer)
        logger.info("多Agent工作流图已编译（精简 3 节点）")
    return agent_graph
