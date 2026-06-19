# 后端 SSE 流式对话 API — 支持 Human-in-the-Loop 审批
import json
import asyncio
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from langgraph.types import Command
from ..models.schemas import ChatRequest
from ..agent.state import create_initial_state
from ..graph.workflow import get_agent_graph
from ..memory.sql_store import sql_memory

router = APIRouter(prefix="/api/v1", tags=["agent"])

# 后端 存储待审批的任务（生产环境应放 Redis）
_pending_reviews: dict[str, dict] = {}

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    return EventSourceResponse(
        _execute_and_stream(request),
        headers={"Content-Type": "text/event-stream; charset=utf-8"}
    )

@router.post("/chat/resume")
async def resume_stream(request: dict):
    # 后端 人工审批后恢复执行
    task_id = request.get("task_id", "")
    action = request.get("action", "approve")  # approve / reject / modify
    modified_subtasks = request.get("subtasks", None)

    thread_id = request.get("thread_id", "default")
    config = {"configurable": {"thread_id": thread_id}}

    graph = get_agent_graph()
    human_response = {"action": action}
    if modified_subtasks:
        human_response["subtasks"] = modified_subtasks

    return EventSourceResponse(
        _execute_resume(graph, config, human_response, task_id, thread_id),
        headers={"Content-Type": "text/event-stream; charset=utf-8"}
    )

async def _execute_and_stream(request: ChatRequest):
    task_input = request.task
    thread_id = request.thread_id or "default_session"
    config = {"configurable": {"thread_id": thread_id}}

    sql_memory.create_session(thread_id)
    sql_memory.update_title(thread_id, task_input)  # 后端 首次对话自动设标题
    state = create_initial_state(task_input)

    yield _sse("thinking", {"stage": "decompose", "message": "正在分析任务..."})

    graph = get_agent_graph()

    try:
        final_state = None
        task_id = state["task_id"]

        # 后端 流式执行，遇到 interrupt 自动暂停
        for step_output in graph.stream(state, config):
            final_state = step_output
            for node_name, node_state in step_output.items():
                for evt in _process_step(node_name, node_state, task_id):
                    yield evt

        # 后端 流式输出最终结果
        if final_state:
            for evt in _emit_final_result(final_state, task_input, thread_id, task_id):
                yield evt

        yield _sse("done", {})

    except Exception as e:
        yield _sse("error", {"message": str(e)})

async def _execute_resume(graph, config, human_response, task_id, thread_id):
    yield _sse("thinking", {"stage": "execute", "message": "审批通过，开始执行..."})

    try:
        final_state = None
        for step_output in graph.stream(Command(resume=human_response), config):
            final_state = step_output
            for node_name, node_state in step_output.items():
                for evt in _process_step(node_name, node_state, task_id):
                    yield evt

        if final_state:
            for evt in _emit_final_result(final_state, f"(审批恢复)", thread_id):
                yield evt

        yield _sse("done", {})
    except Exception as e:
        yield _sse("error", {"message": str(e)})

def _process_step(node_name: str, node_state: dict, task_id: str):
    # 后端 处理每一步的输出
    stage = node_state.get("current_stage", "")
    subtasks = node_state.get("subtasks", [])

    if node_name == "human_review":
        # 后端 发送审批请求给前端
        plan = [
            {"id": s["id"], "description": s["description"],
             "agent_type": s["agent_type"], "depends_on": s.get("depends_on", [])}
            for s in subtasks
        ]
        # 后端 存储待审批状态
        _pending_reviews[task_id] = {"plan": plan, "user_input": node_state.get("user_input", "")}
        yield _sse("review_required", {
            "task_id": task_id,
            "message": "请审批子任务拆解方案",
            "plan": plan,
        })

    elif stage == "decompose":
        yield _sse("subtask_update", {
            "stage": "decompose",
            "subtasks": [
                {"id": s["id"], "description": s["description"],
                 "agent_type": s["agent_type"], "depends_on": s.get("depends_on", [])}
                for s in subtasks
            ]
        })

    elif stage == "execute":
        running = [s for s in subtasks if s["status"] == "running"]
        yield _sse("thinking", {
            "stage": "execute",
            "message": f"正在并行执行 {len(running)} 个子任务...",
            "running_ids": [s["id"] for s in running]
        })

    elif stage == "reflect":
        fresh = [s for s in subtasks if s["status"] == "needs_reflect"]
        yield _sse("thinking", {
            "stage": "reflect",
            "message": f"Agent 自检中 ({len(fresh)}个)"
        })

    elif stage == "aggregate":
        yield _sse("thinking", {"stage": "aggregate", "message": "汇总生成最终交付物..."})

def _emit_final_result(final_state, task_input, thread_id, task_id=""):
    final_output = ""
    subtask_list = []

    if isinstance(final_state, dict):
        for node_name, ns in final_state.items():
            final_output = ns.get("final_output", "") or final_output
            subtask_list = ns.get("subtasks", []) or subtask_list

    yield _sse("result", {
        "output": final_output,
        "task_id": task_id,
        "subtask_count": len(subtask_list),
    })

    # 后端 打字机效果流式输出
    if final_output:
        for i in range(0, len(final_output), 50):
            yield _sse("token", final_output[i:i+50])
            asyncio.sleep(0)  # 后端 让出控制权

    # 后端 保存到数据库
    if task_id and final_output:
        try:
            sql_memory.save_task(
                task_id=task_id, thread_id=thread_id,
                user_input=task_input, subtasks=subtask_list,
                final_output=final_output, status="completed",
            )
        except Exception as e:
            print(f"[DB] 保存任务失败: {e}")

def _sse(event: str, data: any) -> dict:
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}
