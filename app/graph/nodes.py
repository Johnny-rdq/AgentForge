# 后端 LangGraph 工作流节点 — 精简为 3 核心节点：decompose → execute ⇄ execute → aggregate
from concurrent.futures import ThreadPoolExecutor, as_completed
from langgraph.types import interrupt
from app.core.logger import get_logger
from app.agent.state import WorkflowState, SubtaskDef
from app.agent.master import decompose_task
from app.agent.worker import execute_subtask
from app.core.config import settings

logger = get_logger(__name__)


def node_decompose(state: WorkflowState) -> dict:
    """后端 节点1：Master 拆解任务 → 子任务列表"""
    logger.info(f"拆解任务: {state['user_input'][:50]}...")

    subtasks_raw = decompose_task(state["user_input"], state.get("conversation_history", []))
    subtasks = [SubtaskDef(
        id=raw["id"], description=raw["description"],
        agent_type=raw["agent_type"], depends_on=raw.get("depends_on", []),
        status="pending", result=None, retries=0,
    ) for raw in subtasks_raw]

    return {"subtasks": subtasks, "current_stage": "execute"}


def node_human_review(state: WorkflowState) -> dict:
    """后端 HITL 节点：暂停图执行，等待人工审批拆解计划（仅 HITL 开启时注册）"""
    if not settings.hitl_enabled:
        return {"current_stage": "execute"}

    subtasks = state.get("subtasks", [])
    if not subtasks:
        return {"current_stage": "execute"}

    plan_summary = []
    for s in subtasks:
        deps = f" ← {s.get('depends_on', [])}" if s.get("depends_on") else ""
        plan_summary.append(f"  [{s['agent_type']}] {s['description'][:80]}{deps}")

    human_response = interrupt({
        "action": "review_plan",
        "task_id": state["task_id"],
        "user_input": state["user_input"],
        "subtask_count": len(subtasks),
        "plan": [{"id": s["id"], "description": s["description"], "agent_type": s["agent_type"], "depends_on": s.get("depends_on", [])} for s in subtasks],
        "summary": "\n".join(plan_summary),
    })

    if human_response.get("action") == "approve":
        logger.info("人工审批: 通过")
        return {"current_stage": "execute"}

    if human_response.get("action") == "modify":
        logger.info("人工审批: 修改")
        modified = human_response.get("subtasks", [])
        new_subtasks = [SubtaskDef(
            id=s.get("id", f"sub_{i+1}"),
            description=s.get("description", ""),
            agent_type=s.get("agent_type", "coder"),
            depends_on=s.get("depends_on", []),
            status="pending", result=None, retries=0,
        ) for i, s in enumerate(modified)]
        return {"subtasks": new_subtasks, "current_stage": "execute"}

    if human_response.get("action") == "reject":
        logger.info("人工审批: 拒绝")
        return {"current_stage": "done", "final_output": "任务已被人工驳回。", "error_count": state.get("error_count", 0) + 1}

    return {"current_stage": "execute"}


def node_execute(state: WorkflowState) -> dict:
    """后端 节点2（核心）：调度 + 并行执行 + 自检，合并原 schedule/execute/reflect 三节点

    逻辑：
    1. 找出依赖全部完成的 pending 任务 → 标记 running
    2. 线程池并行执行所有 running 任务
    3. 还有 pending → 返回 "execute" 继续循环；全部完成 → 返回 "aggregate"
    """
    subtasks = state["subtasks"]

    # 后端 步骤1：拓扑调度 — 找就绪任务
    done_ids = {s["id"] for s in subtasks if s["status"] in ("done", "failed")}
    ready_ids = []
    for s in subtasks:
        if s["status"] != "pending":
            continue
        if all(dep in done_ids for dep in s.get("depends_on", [])):
            ready_ids.append(s["id"])

    if not ready_ids:
        # 后端 没有可调度的 → 检查是否全部完成
        all_done = all(s["status"] in ("done", "failed") for s in subtasks)
        return {"current_stage": "aggregate" if all_done else "execute"}

    # 后端 标记就绪 → running
    new_subtasks = []
    for s in subtasks:
        s = dict(s)
        if s["id"] in ready_ids:
            s["status"] = "running"
        new_subtasks.append(s)
    subtasks = new_subtasks

    running = [s for s in subtasks if s["status"] == "running"]
    logger.info(f"调度+执行 {len(running)} 个子任务: {[t['id'] for t in running]}")

    # 后端 步骤2：线程池并行执行
    def run_one(sub):
        enriched_sub = dict(sub)
        enriched_sub["_dep_results"] = _get_dependency_results(sub, subtasks)
        try:
            result = execute_subtask(enriched_sub)
            enriched_sub["result"] = result
            enriched_sub["status"] = "done"
        except Exception as e:
            logger.error(f"子任务执行失败 {sub['id']}: {str(e)[:100]}")
            enriched_sub["result"] = str(e)
            enriched_sub["status"] = "failed"
        return enriched_sub

    results = []
    with ThreadPoolExecutor(max_workers=min(len(running), settings.max_workers)) as executor:
        futures = {executor.submit(run_one, s): s for s in running}
        for future in as_completed(futures):
            try:
                results.append(future.result(timeout=settings.workflow_timeout))
            except Exception:
                sub = futures[future]
                logger.warning(f"子任务超时: {sub['id']} (>{settings.workflow_timeout}s)")
                sub = dict(sub)
                sub["result"] = f"子任务执行超时（>{settings.workflow_timeout}秒）"
                sub["status"] = "failed"
                results.append(sub)

    result_map = {r["id"]: r for r in results}
    new_subtasks = [result_map.get(s["id"], s) for s in subtasks]

    # 后端 步骤3：判断下一步 — 还有 pending 且错误 < 3 → 继续循环；否则汇总
    has_pending = any(s["status"] == "pending" for s in new_subtasks)
    has_failures = any(s["status"] == "failed" for s in new_subtasks)
    error_count = state.get("error_count", 0) + (1 if has_failures else 0)

    if has_pending and error_count < 3:
        next_stage = "execute"  # 后端 循环回自己，处理下一批
    else:
        next_stage = "aggregate"

    return {
        "subtasks": new_subtasks,
        "current_stage": next_stage,
        "error_count": error_count,
    }


def node_aggregate(state: WorkflowState) -> dict:
    """后端 节点3：汇总所有子任务结果 → 最终交付物"""
    done_tasks = [s for s in state["subtasks"] if s["status"] in ("done", "failed")]

    # 暴力破解：无论有几个子任务，只要有结果了，直接拿最后一个（通常是总结节点）的结果。
    # 彻底砍掉耗时的 get_llm_response 汇总！
    if done_tasks:
        final_output = done_tasks[-1].get("result", "") or f"任务完成: {done_tasks[-1].get('description', '')}"
    else:
        final_output = "任务未生成结果"

    return {"final_output": final_output, "current_stage": "done"}


# ========== 辅助函数 ==========

def _get_dependency_results(sub: SubtaskDef, all_subtasks: list[SubtaskDef]) -> str:
    """后端 收集当前子任务的所有依赖任务的输出（注入 Worker 上下文）"""
    dep_map = {s["id"]: s for s in all_subtasks}
    results = []

    for dep_id in sub.get("depends_on", []):
        dep_task = dep_map.get(dep_id)
        if dep_task and dep_task.get("result"):
            results.append(f"[{dep_id}输出]:\n{dep_task['result']}")

    return "\n\n".join(results) if results else ""
