# 后端 自动化基准评测 — 运行 50 个标准任务，评估多 Agent 系统能力
import os
import time
import json
import asyncio
from datetime import datetime
from app.core.logger import get_logger
from app.eval.tasks import BENCHMARK_TASKS
from app.agent.state import create_initial_state
from app.graph.workflow import get_agent_graph

logger = get_logger(__name__)


class BenchmarkRunner:
    """后端 评测跑分器 — 逐个执行标准任务，统计通过率/耗时/质量，输出 JSON 报告"""

    def __init__(self):
        self.results = []
        self._progress_cb = None  # 后端 进度回调 (current, total, message)

    def _set_progress_callback(self, cb):
        """后端 设置进度回调（供 API 层注入，实时推送进度到前端）"""
        self._progress_cb = cb

    async def run_all(self) -> list[dict]:
        total = len(BENCHMARK_TASKS)
        logger.info(f"开始评测 {total} 个标准任务 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        for i, task in enumerate(BENCHMARK_TASKS):
            result = await self._run_single(task)
            self.results.append(result)
            status = "PASS" if result["passed"] else "FAIL"
            logger.info(f"{status} {task['id']}: {task['task'][:40]}... ({result['subtask_count']}子任务, {result['duration_s']:.1f}s)")
            # 后端 推送进度
            if self._progress_cb:
                self._progress_cb(i + 1, total, f"{status} {task['id']}: {task['task'][:40]}")

        self._save_report()
        return self.results

    async def run_subset(self, count: int = 10) -> list[dict]:
        """后端 只跑前 N 题（用于快速验证）"""
        tasks = BENCHMARK_TASKS[:count]
        logger.info(f"开始评测 {len(tasks)} 个标准任务（共 {len(BENCHMARK_TASKS)} 题） — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        for i, task in enumerate(tasks):
            result = await self._run_single(task)
            self.results.append(result)
            status = "PASS" if result["passed"] else "FAIL"
            logger.info(f"{status} {task['id']}: {task['task'][:40]}... ({result['subtask_count']}子任务, {result['duration_s']:.1f}s)")
            if self._progress_cb:
                self._progress_cb(i + 1, len(tasks), f"{status} {task['id']}: {task['task'][:40]}")

        self._save_report()
        return self.results

    async def _run_single(self, task: dict) -> dict:
        """后端 执行单个评测任务"""
        start_time = time.time()
        state = create_initial_state(task["task"])
        graph = get_agent_graph()
        config = {"configurable": {"thread_id": f"bench_{task['id']}"}}

        try:
            max_subtasks = 0
            final_output = ""

            async for step_output in graph.astream(state, config):
                for node_state in step_output.values():
                    sub_count = len(node_state.get("subtasks", []))
                    if sub_count > max_subtasks:
                        max_subtasks = sub_count
                    out = node_state.get("final_output", "")
                    if out:
                        final_output = out

            duration = time.time() - start_time
            quality_score = self._evaluate_quality(final_output, task)

            return {
                "task_id": task["id"],
                "category": task["category"],
                "task": task["task"],
                "passed": max_subtasks >= task["min_subtasks"] and quality_score > 0.3,
                "subtask_count": max_subtasks,
                "duration_s": round(duration, 2),
                "quality_score": round(quality_score, 3),
                "output_preview": final_output[:200],
            }
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"评测异常 {task['id']}: {str(e)[:100]}")
            return {
                "task_id": task["id"], "category": task["category"], "task": task["task"],
                "passed": False, "subtask_count": 0,
                "duration_s": round(duration, 2), "quality_score": 0.0,
                "output_preview": str(e)[:200],
            }

    def _evaluate_quality(self, output: str, task: dict) -> float:
        """后端 简单质量评分：基于长度 + 结构化 + 关联性"""
        score = 0.0
        if len(output) > 100:
            score += 0.2
        if len(output) > 500:
            score += 0.2
        if any(kw in output for kw in ["|", "#", "**", "```", "1.", "- "]):
            score += 0.2
        if task["id"] in output or task["task"][:10] in output:
            score += 0.2
        return min(score, 1.0)

    def _save_report(self) -> None:
        """后端 打印汇总 + 按分类统计 + 保存 JSON 报告"""
        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)
        avg_duration = sum(r["duration_s"] for r in self.results) / total if total > 0 else 0
        avg_quality = sum(r["quality_score"] for r in self.results) / total if total > 0 else 0

        categories = {}
        for r in self.results:
            cat = r["category"]
            if cat not in categories:
                categories[cat] = {"total": 0, "passed": 0}
            categories[cat]["total"] += 1
            if r["passed"]:
                categories[cat]["passed"] += 1

        logger.info(f"评测完成 — 通过率: {passed}/{total} ({passed/total*100:.1f}%), 平均耗时: {avg_duration:.2f}s, 平均质量: {avg_quality:.3f}")
        for cat, stats in categories.items():
            logger.info(f"  {cat}: {stats['passed']}/{stats['total']} ({stats['passed']/stats['total']*100:.0f}%)")

        report = {
            "timestamp": datetime.now().isoformat(),
            "total": total, "passed": passed,
            "pass_rate": f"{passed/total*100:.1f}%",
            "avg_duration_s": round(avg_duration, 2),
            "avg_quality_score": round(avg_quality, 3),
            "categories": categories,
            "details": self.results,
        }
        # 后端 用绝对路径，避免后台线程 CWD 不一致导致文件写入错误位置
        data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
        os.makedirs(data_dir, exist_ok=True)
        report_path = os.path.join(data_dir, f"benchmark_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"评测报告已保存: {report_path}")


def run_benchmark_cli():
    asyncio.run(BenchmarkRunner().run_all())


if __name__ == "__main__":
    run_benchmark_cli()
