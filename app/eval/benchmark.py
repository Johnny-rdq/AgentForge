# 后端 自动化基准评测 — 对比多Agent vs 单Agent
import time
import json
from datetime import datetime
from .tasks import BENCHMARK_TASKS
from ..agent.state import create_initial_state
from ..graph.workflow import get_agent_graph
from ..core.llm import get_llm_response

class BenchmarkRunner:
    # 后端 评测跑分器 — 运行标准任务集并对比
    def __init__(self):
        self.results = []

    def run_all(self) -> list[dict]:
        # 后端 运行全部50个标准任务
        print(f"\n{'='*60}")
        print(f"[Benchmark] 开始评测 {len(BENCHMARK_TASKS)} 个标准任务")
        print(f"[Benchmark] 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")

        for task in BENCHMARK_TASKS:
            result = self._run_single(task)
            self.results.append(result)
            status = "PASS" if result["passed"] else "FAIL"
            print(f"{status} {task['id']}: {task['task'][:40]}... "
                  f"({result['subtask_count']}子任务, {result['duration_s']:.1f}s)")

        self._print_summary()
        return self.results

    def _run_single(self, task: dict) -> dict:
        # 后端 执行单个评测任务
        start_time = time.time()
        state = create_initial_state(task["task"])
        graph = get_agent_graph()
        config = {"configurable": {"thread_id": f"bench_{task['id']}"}}

        try:
            final_state = None
            max_subtasks = 0
            final_output = ""
            for step_output in graph.stream(state, config):
                final_state = step_output
                # 后端 追踪最大子任务数（aggregate 节点不传递 subtasks）
                for node_state in step_output.values():
                    sub_count = len(node_state.get("subtasks", []))
                    if sub_count > max_subtasks:
                        max_subtasks = sub_count
                    out = node_state.get("final_output", "")
                    if out:
                        final_output = out

            duration = time.time() - start_time

            subtask_count = max_subtasks

            # 后端 质量评分（基于输出长度和结构判断）
            quality_score = self._evaluate_quality(final_output, task)

            return {
                "task_id": task["id"],
                "category": task["category"],
                "task": task["task"],
                "passed": subtask_count >= task["min_subtasks"] and quality_score > 0.3,
                "subtask_count": subtask_count,
                "duration_s": round(duration, 2),
                "quality_score": round(quality_score, 3),
                "output_preview": final_output[:200],
            }
        except Exception as e:
            duration = time.time() - start_time
            return {
                "task_id": task["id"],
                "category": task["category"],
                "task": task["task"],
                "passed": False,
                "subtask_count": 0,
                "duration_s": round(duration, 2),
                "quality_score": 0.0,
                "output_preview": str(e)[:200],
            }

    def _evaluate_quality(self, output: str, task: dict) -> float:
        # 后端 简单质量评分
        score = 0.0
        if len(output) > 100:
            score += 0.2
        if len(output) > 500:
            score += 0.2
        if any(kw in output for kw in ["|", "#", "**", "```", "1.", "- "]):
            score += 0.2  # 后端 有结构化标记
        if task["id"] in output or task["task"][:10] in output:
            score += 0.2  # 后端 有关联性
        return min(score, 1.0)

    def _print_summary(self) -> None:
        # 后端 打印评测汇总
        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)
        avg_duration = sum(r["duration_s"] for r in self.results) / total if total > 0 else 0
        avg_quality = sum(r["quality_score"] for r in self.results) / total if total > 0 else 0

        # 后端 按分类统计
        categories = {}
        for r in self.results:
            cat = r["category"]
            if cat not in categories:
                categories[cat] = {"total": 0, "passed": 0}
            categories[cat]["total"] += 1
            categories[cat]["passed"] += 1 if r["passed"] else 0

        print(f"\n{'='*60}")
        print(f"[Benchmark] 评测完成")
        print(f"[Benchmark] 总通过率: {passed}/{total} ({passed/total*100:.1f}%)")
        print(f"[Benchmark] 平均耗时: {avg_duration:.2f}s")
        print(f"[Benchmark] 平均质量分: {avg_quality:.3f}")
        print(f"[Benchmark] 分类通过率:")
        for cat, stats in categories.items():
            print(f"  - {cat}: {stats['passed']}/{stats['total']} "
                  f"({stats['passed']/stats['total']*100:.0f}%)")
        print(f"{'='*60}\n")

        # 后端 保存结果到文件
        report = {
            "timestamp": datetime.now().isoformat(),
            "total": total,
            "passed": passed,
            "pass_rate": f"{passed/total*100:.1f}%",
            "avg_duration_s": round(avg_duration, 2),
            "avg_quality_score": round(avg_quality, 3),
            "categories": categories,
            "details": self.results,
        }
        report_path = f"data/benchmark_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"[Benchmark] 报告已保存: {report_path}")

def run_benchmark_cli():
    # 后端 命令行入口：python -m app.eval.benchmark
    runner = BenchmarkRunner()
    runner.run_all()

if __name__ == "__main__":
    run_benchmark_cli()
