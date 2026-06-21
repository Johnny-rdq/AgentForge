# 后端 SSE 流式对话 API — 任务执行 + HITL 审批恢复 + 取消 + token 流式输出
import json
import os
import asyncio
import time
import queue
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Request, UploadFile, File, Form
from sse_starlette.sse import EventSourceResponse
from langgraph.types import Command
from app.core.logger import get_logger
from app.core.config import settings
from app.models.schemas import ChatRequest
from app.agent.state import create_initial_state
from app.graph.workflow import get_agent_graph
from app.memory.sql_store import sql_memory

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["agent"])

_pending_reviews: dict[str, dict] = {}
_cancel_flags: dict[str, bool] = {}
_conversation_history: dict[str, list[dict]] = {}  # 后端 会话级对话记忆，thread_id → [{"role":..., "content":...}]

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "uploads")


@router.get("/health")
async def health_check():
    """后端 健康检查端点"""
    from datetime import datetime
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """后端 SSE 流式对话：接收任务 → 流式执行 → 实时推送状态"""
    return EventSourceResponse(
        _execute_and_stream(request.task, request.thread_id or "default_session", request.files_json or "[]"),
        headers={"Content-Type": "text/event-stream; charset=utf-8"}
    )


@router.post("/chat/resume")
async def resume_stream(request: dict):
    """后端 审批恢复：将 approve/reject/modify 决策注入 LangGraph 继续执行"""

    # 后端 核心：Command(resume=human_response) 从 interrupt 暂停点恢复
    task_id = request.get("task_id", "")
    action = request.get("action", "approve")
    thread_id = request.get("thread_id", "default")

    config = {"configurable": {"thread_id": thread_id}}
    graph = get_agent_graph()

    human_response = {"action": action}
    if request.get("subtasks"):
        human_response["subtasks"] = request["subtasks"]

    logger.info(f"审批恢复: task={task_id}, action={action}")

    return EventSourceResponse(
        _execute_resume(graph, config, human_response, task_id, thread_id),
        headers={"Content-Type": "text/event-stream; charset=utf-8"}
    )


@router.post("/chat/cancel")
async def cancel_task(request: dict):
    """后端 任务取消：设置内存取消标记，执行循环检测到后中止"""
    task_id = request.get("task_id", "")
    if not task_id:
        return {"error": "缺少 task_id"}

    _cancel_flags[task_id] = True
    _pending_reviews.pop(task_id, None)
    logger.info(f"任务取消请求: {task_id}")
    return {"status": "cancelled", "task_id": task_id}


async def _execute_and_stream(task_input: str, thread_id: str = "default_session", files_json: str = "[]"):
    """后端 核心执行流程：简单任务直接调 Worker（跳过 graph），复杂任务走 LangGraph"""
    start_time = time.time()

    sql_memory.create_session(thread_id)
    sql_memory.update_title(thread_id, task_input)

    history = _conversation_history.get(thread_id, [])
    state = create_initial_state(task_input, conversation_history=history)
    task_id = state["task_id"]

    # ===== 超级快速通道：regex 检测到的简单单任务 → 跳过整个 graph =====
    from app.agent.master import _fast_path
    fast_subtasks = _fast_path(task_input)
    if fast_subtasks and len(fast_subtasks) == 1:
        sub = fast_subtasks[0]
        sub["_dep_results"] = ""  # 后端 单任务无依赖

        yield _sse("thinking", {"stage": "execute", "message": "正在处理..."})

        import app.agent.worker as worker_mod
        from app.agent.worker import execute_subtask
        token_queue: queue.Queue = queue.Queue()
        worker_mod._token_bridge = token_queue

        worker_result = [None]  # 后端 用 list 容器在线程间传递结果

        def run_worker():
            worker_result[0] = execute_subtask(sub)

        wf_executor = ThreadPoolExecutor(max_workers=1)
        future = wf_executor.submit(run_worker)
        has_streamed = False

        # 后端 轮询：排空 token → 看到哨兵或 Worker 完成 → 确保拿到结果再退出
        while True:
            sentinel_seen = False
            while True:
                try:
                    token = token_queue.get_nowait()
                    if token is None:  # 后端 哨兵：LLM 流式已完成
                        sentinel_seen = True
                    else:
                        yield _sse("token", token)
                        has_streamed = True
                except queue.Empty:
                    break
            if sentinel_seen:
                # 后端 等 Worker 真正结束再读结果（防止流式中断后的非流式回退还没跑完）
                try:
                    future.result(timeout=30)
                except Exception:
                    pass
                # 后端 排空 Worker 结束后可能残余的 token
                while True:
                    try:
                        token = token_queue.get_nowait()
                        if token is not None:
                            yield _sse("token", token)
                            has_streamed = True
                    except queue.Empty:
                        break
                break
            if future.done():
                while True:
                    try:
                        token = token_queue.get_nowait()
                        if token is not None:
                            yield _sse("token", token)
                            has_streamed = True
                    except queue.Empty:
                        break
                break
            await asyncio.sleep(0.02)

        worker_mod._token_bridge = None
        wf_executor.shutdown(wait=False)

        elapsed = time.time() - start_time
        final_output = worker_result[0] or ""

        yield _sse("result", {
            "output": "" if has_streamed else final_output,
            "task_id": task_id, "subtask_count": 1,
            "streamed": has_streamed, "elapsed_ms": int(elapsed * 1000),
        })
        if final_output:
            _bg_persist(elapsed, task_id, thread_id, task_input, final_output, fast_subtasks, files_json)
            _save_conversation(thread_id, task_input, final_output)
        yield _sse("done", {"elapsed": round(elapsed, 1)})
        logger.info(f"⚡ 快速通道: {task_id}, 耗时 {elapsed:.1f}s")
        return

    # ===== Graph 路径：复杂/多子任务 =====
    config = {"configurable": {"thread_id": thread_id}}

    yield _sse("thinking", {"stage": "decompose", "message": "正在分析任务..."})

    graph = get_agent_graph()

    # 后端 线程安全队列：Worker 线程写入 token，主协程读取推送 SSE
    import app.agent.worker as worker_mod
    token_queue: queue.Queue = queue.Queue()
    worker_mod._token_bridge = token_queue

    # 后端 步骤队列：LangGraph 每完成一个节点就放入（asyncio.Queue 只在主协程使用，线程安全由 call_soon_threadsafe 保证）
    step_queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def run_graph_in_thread():
        """后端 在独立线程中同步执行 LangGraph 图"""
        try:
            for step_output in graph.stream(state, config):
                asyncio.run_coroutine_threadsafe(step_queue.put(("step", step_output)), loop)
                if time.time() - start_time > settings.workflow_timeout:
                    asyncio.run_coroutine_threadsafe(step_queue.put(("timeout", None)), loop)
                    return
                if _cancel_flags.get(task_id):
                    asyncio.run_coroutine_threadsafe(step_queue.put(("cancelled", None)), loop)
                    return
        except Exception as e:
            asyncio.run_coroutine_threadsafe(step_queue.put(("error", e)), loop)
        finally:
            asyncio.run_coroutine_threadsafe(step_queue.put(("graph_done", None)), loop)

    executor = ThreadPoolExecutor(max_workers=1)
    executor.submit(run_graph_in_thread)

    final_state = None
    has_streamed = False
    aborted = False
    done_sent = False
    streaming_complete = False  # 后端 收到哨兵后置 True，触发立即退出
    # 后端 缓存第一个有 Worker 结果的 state，token 流完后用于提前结束
    _worker_result_state = None

    try:
        while True:
            # 后端 步骤1：排空 token 队列（含哨兵检测）
            token_drained = False
            while True:
                try:
                    token = token_queue.get_nowait()
                    if token is None:  # 后端 哨兵：Worker LLM 流式已完成
                        streaming_complete = True
                        continue
                    yield _sse("token", token)
                    has_streamed = True
                    token_drained = True
                except queue.Empty:
                    break

            # 后端 步骤2：哨兵已到 → 快速收尾，不等 graph 后续节点
            if streaming_complete and not done_sent:
                done_sent = True
                # 后端 等 graph 线程把 execute 节点的 step 发过来（最长 5 秒）
                deadline = time.time() + 5.0
                while time.time() < deadline:
                    try:
                        msg_type, payload = await asyncio.wait_for(step_queue.get(), timeout=0.5)
                        if msg_type == "step":
                            for ns in payload.values():
                                for s in ns.get("subtasks", []):
                                    if s.get("result") and s["status"] in ("done", "failed"):
                                        _worker_result_state = payload
                                        break
                            if _worker_result_state is not None:
                                break  # 后端 拿到 Worker 结果了，退出等待
                        elif msg_type == "graph_done":
                            break
                    except asyncio.TimeoutError:
                        continue

                fout, slist = _extract_output(_worker_result_state) if _worker_result_state else ("", [])
                elapsed = time.time() - start_time
                logger.info(f"⚡ 哨兵提前结束: {task_id}, 耗时 {elapsed:.1f}s")
                if fout:
                    _bg_persist(elapsed, task_id, thread_id, task_input, fout, slist, files_json)
                    _save_conversation(thread_id, task_input, fout)
                else:
                    _bg_persist(elapsed, task_id, thread_id, task_input, "(处理中)", slist, files_json)
                worker_mod._token_bridge = None
                executor.shutdown(wait=False)
                yield _sse("result", {"output": "", "task_id": task_id, "subtask_count": len(slist), "streamed": True, "elapsed_ms": int(elapsed * 1000)})
                yield _sse("done", {"elapsed": round(elapsed, 1)})
                return

            # 后端 步骤3：取下一个步骤事件（含超时）
            try:
                msg_type, payload = await asyncio.wait_for(step_queue.get(), timeout=0.03 if token_drained else 0.15)
            except asyncio.TimeoutError:
                # 后端 旧版兼容：token 已全部输出 + 有 Worker 结果 → 提前结束
                if has_streamed and not done_sent and _worker_result_state is not None:
                    fout, slist = _extract_output(_worker_result_state)
                    if fout:
                        done_sent = True
                        elapsed = time.time() - start_time
                        logger.info(f"⚡ 提前结束(超时检测): {task_id}, 耗时 {elapsed:.1f}s")
                        _bg_persist(elapsed, task_id, thread_id, task_input, fout, slist, files_json)
                        _save_conversation(thread_id, task_input, fout)
                        worker_mod._token_bridge = None
                        executor.shutdown(wait=False)
                        yield _sse("result", {"output": "", "task_id": task_id, "subtask_count": len(slist), "streamed": True, "elapsed_ms": int(elapsed * 1000)})
                        yield _sse("done", {"elapsed": round(elapsed, 1)})
                        return
                continue

            # 后端 步骤4：处理步骤事件
            if msg_type == "graph_done":
                break
            elif msg_type == "timeout":
                logger.warning(f"工作流超时: {task_id}")
                yield _sse("error", {"message": f"任务执行超时，请简化任务重试"})
                aborted = True
                return
            elif msg_type == "cancelled":
                logger.info(f"任务被取消: {task_id}")
                yield _sse("cancelled", {"task_id": task_id, "message": "任务已被取消"})
                _cancel_flags.pop(task_id, None)
                aborted = True
                return
            elif msg_type == "error":
                raise payload
            elif msg_type == "step":
                step_output = payload
                # 后端 缓存第一个包含 Worker 结果的状态
                if _worker_result_state is None:
                    for ns in step_output.values():
                        for s in ns.get("subtasks", []):
                            if s.get("result") and s["status"] in ("done", "failed"):
                                _worker_result_state = step_output
                                break
                for node_name, node_state in step_output.items():
                    for evt in _process_step(node_name, node_state, task_id):
                        yield evt
                final_state = step_output

    finally:
        while True:
            try:
                token = token_queue.get_nowait()
                yield _sse("token", token)
                has_streamed = True
            except queue.Empty:
                break
        worker_mod._token_bridge = None
        executor.shutdown(wait=False)

    if aborted or done_sent:
        return

    elapsed = time.time() - start_time
    logger.info(f"任务完成: {task_id}, 耗时 {elapsed:.1f}s, 流式token: {has_streamed}")

    fout, slist = _extract_output(final_state) if final_state else ("", [])
    # 后端 流式已推送 token → result 不带 content（避免覆盖前端）
    yield _sse("result", {
        "output": "" if has_streamed else fout,
        "task_id": task_id, "subtask_count": len(slist),
        "streamed": has_streamed, "elapsed_ms": int(elapsed * 1000),
    })
    if fout:
        _bg_persist(elapsed, task_id, thread_id, task_input, fout, slist, files_json)
        _save_conversation(thread_id, task_input, fout)

    yield _sse("done", {"elapsed": round(elapsed, 1)})


async def _execute_resume(graph, config, human_response, task_id, thread_id):
    """后端 从 interrupt 点恢复执行（审批后继续，含流式输出）"""
    start_time = time.time()
    logger.info(f"开始审批恢复执行: {task_id}")
    yield _sse("thinking", {"stage": "execute", "message": "审批通过，开始执行..."})

    # 后端 线程安全队列：Worker 线程写入 token
    import app.agent.worker as worker_mod
    token_queue: queue.Queue = queue.Queue()
    worker_mod._token_bridge = token_queue

    step_queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def run_graph_in_thread():
        async def _run():
            try:
                async for step_output in graph.astream(Command(resume=human_response), config):
                    if _cancel_flags.get(task_id):
                        asyncio.run_coroutine_threadsafe(step_queue.put(("cancelled", None)), loop)
                        return
                    asyncio.run_coroutine_threadsafe(step_queue.put(("step", step_output)), loop)
            except Exception as e:
                asyncio.run_coroutine_threadsafe(step_queue.put(("error", e)), loop)
            finally:
                asyncio.run_coroutine_threadsafe(step_queue.put(("graph_done", None)), loop)
        asyncio.run(_run())

    executor = ThreadPoolExecutor(max_workers=1)
    executor.submit(run_graph_in_thread)

    final_state = None
    has_streamed = False
    aborted = False

    try:
        while True:
            while True:
                try:
                    token = token_queue.get_nowait()
                    yield _sse("token", token)
                    has_streamed = True
                except queue.Empty:
                    break

            try:
                msg_type, payload = await asyncio.wait_for(step_queue.get(), timeout=0.03)
            except asyncio.TimeoutError:
                continue

            if msg_type == "graph_done":
                break
            elif msg_type == "cancelled":
                yield _sse("cancelled", {"task_id": task_id, "message": "任务已被取消"})
                _cancel_flags.pop(task_id, None)
                aborted = True
                return
            elif msg_type == "error":
                raise payload
            elif msg_type == "step":
                step_output = payload
                for node_name, node_state in step_output.items():
                    for evt in _process_step(node_name, node_state, task_id):
                        yield evt
                final_state = step_output
    finally:
        while True:
            try:
                token = token_queue.get_nowait()
                yield _sse("token", token)
                has_streamed = True
            except queue.Empty:
                break
        worker_mod._token_bridge = None
        executor.shutdown(wait=False)

    if aborted:
        return

    elapsed = time.time() - start_time
    elapsed_ms = int(elapsed * 1000)
    if final_state:
        for evt in _emit_final_result(final_state, "(审批恢复)", thread_id, task_id, "", has_streamed, elapsed_ms):
            yield evt

    yield _sse("done", {"elapsed": round(elapsed, 1)})


def _process_step(node_name: str, node_state: dict, task_id: str):
    """后端 将 LangGraph 节点输出转为 SSE 事件（单子任务简化：跳过中间状态，直接流式输出）"""
    stage = node_state.get("current_stage", "")
    subtasks = node_state.get("subtasks", [])
    is_simple = len(subtasks) <= 1  # 后端 单子任务 → 简化 UI，不推送中间状态

    if node_name == "human_review":
        plan = [{"id": s["id"], "description": s["description"], "agent_type": s["agent_type"], "depends_on": s.get("depends_on", [])} for s in subtasks]
        if plan and settings.hitl_enabled:
            _pending_reviews[task_id] = {"plan": plan, "user_input": node_state.get("user_input", "")}
            yield _sse("review_required", {"task_id": task_id, "message": "请审批子任务拆解方案", "plan": plan})

    elif stage == "decompose":
        if not is_simple:  # 后端 简单任务跳过拆解展示
            yield _sse("subtask_update", {
                "stage": "decompose",
                "subtasks": [{"id": s["id"], "description": s["description"], "agent_type": s["agent_type"], "depends_on": s.get("depends_on", [])} for s in subtasks]
            })

    elif stage == "execute":
        if not is_simple:  # 后端 简单任务跳过执行中提示
            running = [s for s in subtasks if s["status"] == "running"]
            yield _sse("thinking", {"stage": "execute", "message": f"正在并行执行 {len(running)} 个子任务...", "running_ids": [s["id"] for s in running]})

    elif stage == "aggregate":
        if not is_simple:
            yield _sse("thinking", {"stage": "aggregate", "message": "汇总生成最终交付物..."})


def _emit_final_result(final_state, task_input, thread_id, task_id="", files_json: str = "[]", has_streamed: bool = False, elapsed_ms: int = 0):
    """后端 推送最终结果 + 持久化（含耗时）"""
    final_output = ""
    subtask_list = []

    if isinstance(final_state, dict):
        for ns in final_state.values():
            final_output = ns.get("final_output", "") or final_output
            subtask_list = ns.get("subtasks", []) or subtask_list

    # 后端 流式已推送 token → result 只带元数据
    if has_streamed:
        yield _sse("result", {"output": "", "task_id": task_id, "subtask_count": len(subtask_list), "streamed": True, "elapsed_ms": elapsed_ms})
    else:
        yield _sse("result", {"output": final_output, "task_id": task_id, "subtask_count": len(subtask_list), "elapsed_ms": elapsed_ms})

    # 后端 持久化到 SQLite（含耗时）
    if task_id and final_output:
        try:
            import re
            clean_input = re.sub(r'\n*[（(]用户上传了文件[^)）]+[)）]', '', task_input)
            clean_input = re.sub(r'\n*\[用户上传了文件[^\]]+\]', '', clean_input)
            clean_input = clean_input.strip()
            sql_memory.save_task(
                task_id=task_id, thread_id=thread_id,
                user_input=clean_input, subtasks=subtask_list,
                final_output=final_output, status="completed",
                files_json=files_json, elapsed_ms=elapsed_ms,
            )
        except Exception as e:
            logger.error(f"保存任务失败: {e}")


def _sse(event: str, data: any) -> dict:
    """后端 构造 SSE 事件字典"""
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}


def _extract_output(state: dict) -> tuple:
    """后端 从 LangGraph 状态中提取最终输出和子任务列表"""
    fout = ""
    slist = []
    if isinstance(state, dict):
        for ns in state.values():
            fout = ns.get("final_output", "") or fout
            slist = ns.get("subtasks", []) or slist
            if not fout and slist:
                for s in slist:
                    if s.get("result"):
                        fout = s["result"]
                        break
    return fout, slist


def _bg_persist(elapsed_s: float, task_id: str, thread_id: str, task_input: str,
                final_output: str, subtask_list: list, files_json: str):
    """后端 同步写 SQLite（INSERT < 5ms，不需要后台线程，避免数据丢失）"""
    try:
        import re
        elapsed_ms = int(elapsed_s * 1000)
        clean_input = re.sub(r'\n*[（(]用户上传了文件[^)）]+[)）]', '', task_input)
        clean_input = re.sub(r'\n*\[用户上传了文件[^\]]+\]', '', clean_input)
        clean_input = clean_input.strip()
        sql_memory.save_task(
            task_id=task_id, thread_id=thread_id,
            user_input=clean_input, subtasks=subtask_list,
            final_output=final_output, status="completed",
            files_json=files_json, elapsed_ms=elapsed_ms,
        )
        logger.debug(f"任务已存库: {task_id} ({elapsed_ms}ms)")
    except Exception as e:
        logger.error(f"保存任务失败: {e}")


def _save_conversation(thread_id: str, task_input: str, final_output: str):
    """后端 保存对话到内存（最近 10 轮）"""
    hist = _conversation_history.setdefault(thread_id, [])
    hist.append({"role": "user", "content": task_input})
    hist.append({"role": "assistant", "content": final_output[:500]})
    if len(hist) > 20:
        hist[:] = hist[-20:]
