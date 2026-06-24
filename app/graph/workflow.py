# 后端 LangGraph 工作流组装 — DAG：decompose → execute ⇄ execute → reflect → aggregate → END
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.core.logger import get_logger
from app.agent.state import WorkflowState
from app.graph.nodes import node_decompose, node_human_review, node_execute, node_reflect, node_aggregate
from app.graph.edges import route_after_execute
from app.core.config import settings

logger = get_logger(__name__)


def build_workflow() -> StateGraph:
    """后端 构建多 Agent DAG 工作流

    路径：decompose → (human_review) → execute ⇄ execute → (reflect) → aggregate → END
    HITL 开启时插入 human_review；REFLECTION 开启时插入 reflect
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

    # 后端 Reflector 反思：开启时在 execute 和 aggregate 之间插入 reflect 节点
    if settings.reflection_enabled:
        workflow.add_node("reflect", node_reflect)
        workflow.add_conditional_edges("execute", route_after_execute, {
            "execute": "execute",
            "reflect": "reflect",
            "aggregate": "aggregate",
        })
        workflow.add_edge("reflect", "aggregate")
        logger.info("Reflector 反思审查已启用")
    else:
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
        # 后端 节点数计算
        node_count = 3  # decompose + execute + aggregate
        if settings.hitl_enabled:
            node_count += 1
        if settings.reflection_enabled:
            node_count += 1
        logger.info(f"多Agent工作流图已编译（{node_count} 节点）")
    return agent_graph
