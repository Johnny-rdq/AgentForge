# 后端 LangGraph 图节点定义 — 每个节点是工作流的一个处理阶段
import asyncio
from langgraph.types import interrupt
from ..agent.state import WorkflowState, SubtaskDef
from ..agent.master import decompose_task
from ..agent.worker import execute_subtask
from ..agent.reflector import reflect_and_fix
from ..core.config import settings

def node_human_review(state: WorkflowState) -> dict:
    # 后端 节点1.5：Human-in-the-Loop — 人工审批拆解计划
    # 后端 HITL 关闭时自动放行
    if not settings.hitl_enabled:
        return {"current_stage": "schedule"}

    subtasks = state.get("subtasks", [])
    if not subtasks:
        return {"current_stage": "schedule"}

    # 后端 构造审批信息，LangGraph interrupt 会暂停图执行
    plan_summary = []
    for s in subtasks:
        deps = f" ← {s.get('depends_on', [])}" if s.get("depends_on") else ""
        plan_summary.append(f"  [{s['agent_type']}] {s['description'][:80]}{deps}")

    review_request = {
        "action": "review_plan",
        "task_id": state["task_id"],
        "user_input": state["user_input"],
        "subtask_count": len(subtasks),
        "plan": [
            {
                "id": s["id"],
                "description": s["description"],
                "agent_type": s["agent_type"],
                "depends_on": s.get("depends_on", []),
            }
            for s in subtasks
        ],
        "summary": "\n".join(plan_summary),
    }

    # 后端 interrupt() 暂停图，等待人工响应（approve/reject/modify）
    human_response = interrupt(review_request)

    # 后端 处理审批结果
    if human_response.get("action") == "approve":
        return {"current_stage": "schedule"}

    elif human_response.get("action") == "modify":
        # 后端 人工修改了子任务计划
        modified = human_response.get("subtasks", [])
        new_subtasks = []
        for s in modified:
            new_subtasks.append(SubtaskDef(
                id=s.get("id", f"sub_{len(new_subtasks)+1}"),
                description=s.get("description", ""),
                agent_type=s.get("agent_type", "coder"),
                depends_on=s.get("depends_on", []),
                status="pending",
                result=None,
                retries=0,
            ))
        return {"subtasks": new_subtasks, "current_stage": "schedule"}

    elif human_response.get("action") == "reject":
        return {"current_stage": "done", "final_output": "任务已被人工驳回。",
                "error_count": state.get("error_count", 0) + 1}

    # 后端 默认放行
    return {"current_stage": "schedule"}

def node_decompose(state: WorkflowState) -> dict:
    # 后端 节点1：Master Agent 拆解任务
    print(f"[Node] 拆解任务: {state['user_input'][:50]}...")
    subtasks_raw = decompose_task(state["user_input"])

    # 后端 构造 SubtaskDef 列表
    subtasks = []
    for raw in subtasks_raw:
        subtask = SubtaskDef(
            id=raw["id"],
            description=raw["description"],
            agent_type=raw["agent_type"],
            depends_on=raw.get("depends_on", []),
            status="pending",
            result=None,
            retries=0,
        )
        subtasks.append(subtask)

    return {
        "subtasks": subtasks,
        "current_stage": "schedule",
    }

def node_schedule(state: WorkflowState) -> dict:
    # 后端 节点2：依赖感知调度 — 找出本轮可并行执行的子任务
    ready_ids = _get_ready_tasks(state["subtasks"])
    if not ready_ids:
        return {"current_stage": "aggregate"}

    # 后端 标记本轮执行的任务为 running 状态
    new_subtasks = []
    for sub in state["subtasks"]:
        if sub["id"] in ready_ids:
            sub = dict(sub)
            sub["status"] = "running"
        new_subtasks.append(sub)

    return {
        "subtasks": new_subtasks,
        "current_stage": "execute",
    }

def node_execute(state: WorkflowState) -> dict:
    # 后端 节点3：并行执行所有 ready 状态的子任务
    running_tasks = [s for s in state["subtasks"] if s["status"] == "running"]
    print(f"[Node] 并行执行 {len(running_tasks)} 个子任务: {[t['id'] for t in running_tasks]}")

    new_subtasks = []
    for sub in state["subtasks"]:
        if sub["status"] != "running":
            new_subtasks.append(sub)
            continue

        # 后端 注入依赖任务的执行结果
        enriched_sub = dict(sub)
        dep_results = _get_dependency_results(sub, state["subtasks"])
        enriched_sub["_dep_results"] = dep_results

        try:
            result = execute_subtask(enriched_sub)
            enriched_sub["result"] = result
            enriched_sub["status"] = "needs_reflect"  # 后端 标记为待反思，而非直接完成
        except Exception as e:
            enriched_sub["result"] = str(e)
            enriched_sub["status"] = "failed"

        new_subtasks.append(enriched_sub)

    # 后端 检查本轮执行结果
    has_failures = any(s["status"] == "failed" for s in new_subtasks)
    return {
        "subtasks": new_subtasks,
        "current_stage": "reflect" if settings.reflection_enabled else "schedule",
        "error_count": state.get("error_count", 0) + (1 if has_failures else 0),
    }

def node_reflect(state: WorkflowState) -> dict:
    # 后端 节点4：自反思 — 只检查本轮刚完成（needs_reflect）的任务
    fresh_tasks = [s for s in state["subtasks"] if s["status"] == "needs_reflect"]
    if not fresh_tasks:
        return {"current_stage": "schedule"}

    print(f"[Node] 反思检查 {len(fresh_tasks)} 个新完成任务: {[t['id'] for t in fresh_tasks]}")
    fresh_ids = {t["id"] for t in fresh_tasks}
    new_subtasks = []
    for sub in state["subtasks"]:
        if sub["id"] not in fresh_ids:
            new_subtasks.append(sub)
            continue

        # 后端 反思修正
        fixed_result, retries = reflect_and_fix(sub, max_retries=settings.max_retries)
        sub = dict(sub)
        sub["result"] = fixed_result
        sub["retries"] = retries
        sub["status"] = "done"  # 后端 反思完成，标记为最终完成
        new_subtasks.append(sub)

    return {
        "subtasks": new_subtasks,
        "current_stage": "schedule",
    }

def node_aggregate(state: WorkflowState) -> dict:
    # 后端 节点5：汇总所有子任务结果 + 存入记忆
    from ..core.llm import get_llm_response
    from ..memory.vector_store import vector_memory

    done_tasks = [s for s in state["subtasks"] if s["status"] in ("done", "failed")]
    results_text = ""
    for sub in done_tasks:
        results_text += f"\n### {sub['id']}: {sub['description']}\n{sub.get('result', '无结果')}\n"

    prompt = f"""请将以下子任务结果汇总为一份完整的最终输出。

用户原始请求：{state['user_input']}

子任务执行结果：
{results_text}

请输出一份结构清晰、可直接交付的最终结果。如果是数据分析类任务，包含关键结论；如果是代码类任务，输出最终代码；如果是报告类任务，输出完整的 Markdown 文档。"""

    messages = [{"role": "user", "content": prompt}]
    final_output = get_llm_response(messages, temperature=0.3, max_tokens=4096)

    # 后端 存入向量记忆：任务摘要+拆解策略
    try:
        memory_entry = f"任务: {state['user_input']}\n拆解: {len(done_tasks)}个子任务\n结果: {final_output[:500]}"
        vector_memory.store(state["task_id"], memory_entry, {
            "subtask_count": len(done_tasks),
            "agent_types": ",".join(set(s["agent_type"] for s in done_tasks)),
        })
    except Exception:
        pass

    return {
        "final_output": final_output,
        "current_stage": "done",
    }

def _get_ready_tasks(subtasks: list[SubtaskDef]) -> list[str]:
    # 后端 拓扑调度：找出依赖全部完成的待执行任务
    done_ids = {s["id"] for s in subtasks if s["status"] in ("done", "failed")}
    running_ids = {s["id"] for s in subtasks if s["status"] == "running"}
    ready = []
    for sub in subtasks:
        if sub["status"] != "pending":
            continue
        if all(dep in done_ids for dep in sub.get("depends_on", [])):  # 后端 死锁检查
            ready.append(sub["id"])
    return ready

def _get_dependency_results(sub: SubtaskDef, all_subtasks: list[SubtaskDef]) -> str:
    # 后端 收集依赖任务的结果文本
    results = []
    dep_map = {s["id"]: s for s in all_subtasks}
    for dep_id in sub.get("depends_on", []):
        dep_task = dep_map.get(dep_id)
        if dep_task and dep_task.get("result"):
            results.append(f"[{dep_id}输出]:\n{dep_task['result']}")
    return "\n\n".join(results) if results else ""
