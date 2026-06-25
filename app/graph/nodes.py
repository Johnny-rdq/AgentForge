# 后端 LangGraph 工作流节点 — 精简为 3 核心节点：decompose → execute ⇄ execute → aggregate
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from langgraph.types import interrupt
from app.core.logger import get_logger
from app.core.session_context import set_current_thread_id
from app.agent.state import WorkflowState, SubtaskDef
from app.agent.master import decompose_task
from app.agent.worker import execute_subtask
from app.agent.reflector import reflect_and_fix
from app.core.llm import get_llm_response
from app.core.config import settings

logger = get_logger(__name__)


def node_decompose(state: WorkflowState) -> dict:
    """后端 节点1：Master 拆解任务 → 子任务列表"""
    logger.info(f"拆解任务: {state['user_input'][:50]}...")

    subtasks_raw = decompose_task(state["user_input"], state.get("conversation_history", []), state.get("thread_id", ""))
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
            agent_type=s.get("agent_type", "researcher"),
            depends_on=s.get("depends_on", []),
            status="pending", result=None, retries=0,
        ) for i, s in enumerate(modified)]
        return {"subtasks": new_subtasks, "current_stage": "execute"}

    if human_response.get("action") == "reject":
        logger.info("人工审批: 拒绝")
        return {"current_stage": "done", "final_output": "任务已被人工驳回。", "error_count": state.get("error_count", 0) + 1}

    return {"current_stage": "execute"}


def node_execute(state: WorkflowState) -> dict:
    """后端 节点2（核心）：调度 + 并行执行，纯执行不审查

    逻辑：
    1. 找出依赖全部完成的 pending 任务 → 标记 running
    2. 线程池并行执行所有 running 任务 → 标记 executed（待反思）
    3. 还有 pending → 返回 "execute" 继续循环；全部执行完 → reflect 或 aggregate
    """
    subtasks = state["subtasks"]

    # 后端 步骤1：拓扑调度 — 找就绪任务（含已执行但未完成反思的，其产出可被后续任务使用）
    done_ids = {s["id"] for s in subtasks if s["status"] in ("done", "failed", "executed")}
    ready_ids = []
    for s in subtasks:
        if s["status"] != "pending":
            continue
        if all(dep in done_ids for dep in s.get("depends_on", [])):
            ready_ids.append(s["id"])

    if not ready_ids:
        # 后端 没有可调度的 → 检查是否全部完成（没有 pending 也没有 executed）
        all_settled = all(s["status"] in ("done", "failed") or (s["status"] == "executed" and not settings.reflection_enabled) for s in subtasks)
        if all_settled:
            # 后端 反思关闭时 executed 直接视为 done
            for s in subtasks:
                if s["status"] == "executed":
                    s["status"] = "done"
            return {"current_stage": "aggregate", "subtasks": subtasks}
        # 后端 反思开启且有 executed 任务 → 去反思
        has_executed = any(s["status"] == "executed" for s in subtasks)
        if has_executed:
            return {"current_stage": "reflect", "subtasks": subtasks}
        return {"current_stage": "execute", "subtasks": subtasks}

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

    # 后端 步骤2：线程池并行执行（纯执行，不审查）
    def run_one(sub):
        # 后端 设置会话上下文：后续所有工具函数（code_tools/file_tools/upload）自动读取，无需传参
        set_current_thread_id(state.get("thread_id", "default_session"))
        enriched_sub = dict(sub)
        enriched_sub["_thread_id"] = state.get("thread_id", "default_session")  # 后端 传递会话 ID，Worker 扫描生成文件时用
        enriched_sub["_dep_results"] = _get_dependency_results(sub, subtasks)
        enriched_sub["_original_input"] = state.get("user_input", "")  # 后端 传递原始输入，Worker 可提取文件路径
        enriched_sub["_history"] = state.get("conversation_history", [])  # 后端 传递对话历史，Worker 可从中提取之前上传的文件路径
        try:
            result = execute_subtask(enriched_sub)
            enriched_sub["result"] = result
            enriched_sub["status"] = "executed"  # 后端 待反思节点审查
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
    # 后端 归一化：worker 结果中可能含完整 URL（http://localhost:7860/generated/...），统一转相对路径
    for r in results:
        if r.get("result"):
            r["result"] = re.sub(r'https?://[^\s)!]+?/generated/', '/generated/', r["result"])
    new_subtasks = [result_map.get(s["id"], s) for s in subtasks]

    # 后端 步骤3：判断下一步
    has_pending = any(s["status"] == "pending" for s in new_subtasks)
    has_executed = any(s["status"] == "executed" for s in new_subtasks)
    has_failures = any(s["status"] == "failed" for s in new_subtasks)
    error_count = state.get("error_count", 0) + (1 if has_failures else 0)

    if has_pending and error_count < 3:
        next_stage = "execute"  # 后端 循环回自己，处理下一批依赖就绪的任务
    elif has_executed and settings.reflection_enabled:
        next_stage = "reflect"  # 后端 全部执行完毕 → 反思审查
    else:
        # 后端 反思关闭 → 直接把 executed 标为 done，进入汇总
        for s in new_subtasks:
            if s["status"] == "executed":
                s["status"] = "done"
        next_stage = "aggregate"

    return {
        "subtasks": new_subtasks,
        "current_stage": next_stage,
        "error_count": error_count,
    }


def node_reflect(state: WorkflowState) -> dict:
    """后端 节点3（可选）：Reflector 审查所有已执行子任务 → 修正 → 标记 done/failed"""
    subtasks = state["subtasks"]
    new_subtasks = []

    reflected_count = 0
    fixed_count = 0

    for s in subtasks:
        s = dict(s)
        if s["status"] == "executed":
            # 后端 可视化/图表结果跳过反思：Reflector LLM 看不到图片，修正反而会丢弃 markdown 图片引用
            result_text = s.get("result", "") or ""
            if "](/generated/" in result_text or "](data:image/" in result_text:
                logger.info(f"Reflector 跳过 {s['id']}（含图片引用，无需文本审查）")
                s["status"] = "done"
                reflected_count += 1
                new_subtasks.append(s)
                continue
            try:
                reviewed_result, fix_attempts = reflect_and_fix(
                    {"result": s.get("result", ""), "description": s.get("description", "")},
                    max_retries=1,
                )
                if fix_attempts > 0:
                    logger.info(f"Reflector 修正了 {s['id']} 的输出（{fix_attempts}次）")
                    fixed_count += 1
                s["result"] = reviewed_result
                s["status"] = "done"
                reflected_count += 1
            except Exception as e:
                logger.error(f"反思审查异常 {s['id']}: {str(e)[:100]}")
                s["status"] = "done"  # 后端 反思异常不阻塞流程，保留原结果
        new_subtasks.append(s)

    logger.info(f"Reflector 审查完成: {reflected_count} 个审查, {fixed_count} 个修正")
    return {"subtasks": new_subtasks, "current_stage": "aggregate"}


def node_aggregate(state: WorkflowState) -> dict:
    """后端 节点3：汇总所有子任务结果 → 最终交付报告"""
    done_tasks = [s for s in state["subtasks"] if s["status"] in ("done", "failed")]

    if not done_tasks:
        return {"final_output": "任务未生成结果", "current_stage": "done"}

    # 后端 只有 1 个子任务 → 直接返回，无需 LLM 汇总
    if len(done_tasks) == 1:
        final_output = done_tasks[0].get("result", "") or "任务完成"
        final_output = re.sub(r'https?://[^\s)!]+?/generated/', '/generated/', final_output)
        return {"final_output": final_output, "current_stage": "done"}

    # 后端 多子任务 → 组装所有结果，调 LLM 合成一份完整报告
    parts = []
    for s in done_tasks:
        status_tag = "✓" if s["status"] == "done" else "✗"
        result_text = s.get("result", "") or "(无输出)"
        parts.append(f"### [{status_tag}] {s.get('description', s['id'])}\n\n{result_text}")
    all_results = "\n\n---\n\n".join(parts)

    aggregate_prompt = f"""请将以下多个子任务的执行结果，整合成一份完整、连贯的最终交付报告。

规则：
- 用 Markdown 格式输出，标题清晰，结构合理
- 保留所有关键信息：数据、图表描述、代码、链接等
- 按逻辑顺序排列，不是简单拼接
- 去掉重复内容，让报告读起来像一篇完整文档
- 如有多个子任务产出同类内容（如图表+分析），将它们组织在一起
- ⚠️ 图片路径只能用相对格式 ![描述](/generated/文件名.png)，禁止使用完整 URL

用户原始任务：{state['user_input'][:200]}

各子任务执行结果：
{all_results}

请输出最终报告："""

    try:
        final_output = get_llm_response(
            [{"role": "user", "content": aggregate_prompt}],
            temperature=0.3, max_tokens=2048,
        )
        logger.info(f"汇总完成：{len(done_tasks)} 个子任务 → {len(final_output)} 字符")
        # 后端 兜底替换：LLM 可能生成完整 URL，统一转为相对路径 /generated/文件名
        final_output = re.sub(r'https?://[^\s)!]+?/generated/', '/generated/', final_output)
    except Exception as e:
        logger.warning(f"LLM 汇总失败，降级拼接: {str(e)[:80]}")
        # 后端 降级：按顺序拼接所有子任务结果
        fallback = [f"## {s.get('description', s['id'])}\n\n{s.get('result', '')}" for s in done_tasks]
        final_output = "\n\n---\n\n".join(fallback)
        # 后端 兜底替换：降级拼接也可能含完整 URL
        final_output = re.sub(r'https?://[^\s)!]+?/generated/', '/generated/', final_output)

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
