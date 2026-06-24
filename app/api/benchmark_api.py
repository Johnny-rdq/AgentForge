# 后端 评测报告 API — 报告列表 + 单篇详情 + 触发运行
import os
import json
import asyncio
import threading
from fastapi import APIRouter
from app.core.logger import get_logger

router = APIRouter(prefix="/api/v1/benchmark", tags=["benchmark"])

logger = get_logger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")

# 后端 评测运行状态（线程安全）
_bench_state = {"running": False, "current": 0, "total": 50, "message": ""}
_bench_lock = threading.Lock()


@router.get("/reports")
async def list_reports():
    """后端 列出所有评测报告，按时间倒序"""
    reports = []
    if os.path.exists(DATA_DIR):
        for f in sorted(os.listdir(DATA_DIR), reverse=True):
            if f.startswith("benchmark_report_") and f.endswith(".json"):
                path = os.path.join(DATA_DIR, f)
                try:
                    with open(path, "r", encoding="utf-8") as fp:
                        data = json.load(fp)
                    reports.append({
                        "filename": f,
                        "timestamp": data.get("timestamp", ""),
                        "total": data.get("total", 0),
                        "passed": data.get("passed", 0),
                        "pass_rate": data.get("pass_rate", "0%"),
                        "avg_duration_s": data.get("avg_duration_s", 0),
                        "avg_quality_score": data.get("avg_quality_score", 0),
                    })
                except Exception:
                    pass  # 跳过损坏文件
    return {"reports": reports}


@router.get("/reports/{filename}")
async def get_report(filename: str):
    """后端 获取单个评测报告完整内容"""
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return {"error": "报告不存在"}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/status")
async def bench_status():
    """后端 查询评测运行状态"""
    with _bench_lock:
        return dict(_bench_state)


@router.post("/run")
async def run_benchmark(count: int = 10):
    """后端 触发评测运行（后台异步，前端轮询 /status 获取进度）

    Query: count — 运行前 N 题（默认 10，最大 50）
    """
    from app.eval.tasks import BENCHMARK_TASKS
    max_count = min(count, len(BENCHMARK_TASKS))

    with _bench_lock:
        if _bench_state["running"]:
            return {"status": "already_running", "message": "评测正在运行中", "progress": dict(_bench_state)}
        _bench_state["running"] = True
        _bench_state["current"] = 0
        _bench_state["total"] = max_count
        _bench_state["message"] = f"启动评测（{max_count}题）..."

    # 后端 在后台线程中运行评测（避免阻塞请求）
    def _run_in_background():
        from app.eval.benchmark import BenchmarkRunner

        async def _async_run():
            runner = BenchmarkRunner()
            runner._set_progress_callback(_on_progress)
            try:
                await runner.run_subset(max_count)
            except Exception as e:
                logger.error(f"评测运行异常: {str(e)[:200]}")
            finally:
                with _bench_lock:
                    _bench_state["running"] = False
                    _bench_state["message"] = "评测完成"

        asyncio.run(_async_run())

    threading.Thread(target=_run_in_background, daemon=True).start()
    logger.info(f"评测已在后台启动（{max_count}题）")
    return {"status": "started", "message": f"评测已开始（{max_count}题），请通过 /status 查看进度"}


def _on_progress(current: int, total: int, message: str = ""):
    """后端 评测进度回调（线程安全）"""
    with _bench_lock:
        _bench_state["current"] = current
        _bench_state["total"] = total
        _bench_state["message"] = message
