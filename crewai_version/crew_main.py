# 后端 CrewAI 真实版本 — 使用 crewai 库，固定角色顺序执行
"""
运行：.venv/Scripts/python -m crewai_version.crew_main

与 AgentForge 对比：
    - CrewAI: 固定角色、顺序执行、无反思
    - AgentForge: 动态拆解、依赖感知并行、自反思
"""

import time
import sys
import os
import io

# 后端 修复 Windows GBK 终端 emoji 编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crewai import Agent, Task, Crew, Process, LLM

# 后端 读取 .env 中的 DashScope 配置
from app.core.config import settings


def crewai_execute(task_input: str, verbose: bool = False) -> dict:
    start = time.time()

    # 后端 配置 LLM（通过 settings 统一读取）
    llm = LLM(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
    )

    # 后端 3 个固定角色
    researcher = Agent(
        role="研究员",
        goal="搜索并整理与主题相关的最新信息",
        backstory="资深信息检索专家，擅长从海量数据中提取关键信息",
        allow_delegation=False,
        llm=llm,
        verbose=verbose,
    )

    analyst = Agent(
        role="分析师",
        goal="对研究结果进行深度分析，提取3-5个关键洞察",
        backstory="数据分析专家，擅长从结构化信息中发现规律和趋势",
        allow_delegation=False,
        llm=llm,
        verbose=verbose,
    )

    writer = Agent(
        role="技术文档工程师",
        goal="将分析结果整合为结构化 Markdown 报告",
        backstory="技术写作专家，擅长将复杂信息转化为清晰文档",
        allow_delegation=False,
        llm=llm,
        verbose=verbose,
    )

    # 后端 顺序任务链
    task_research = Task(
        description=f"搜索以下主题的相关信息并整理：{task_input}",
        expected_output="一份结构化的信息摘要，包含关键数据和要点",
        agent=researcher,
    )

    task_analyze = Task(
        description="基于研究结果，提取3-5个关键洞察和趋势",
        expected_output="分析报告，列出关键发现和洞察",
        agent=analyst,
        context=[task_research],
    )

    task_write = Task(
        description="基于研究和分析结果，生成一份完整的 Markdown 格式报告",
        expected_output="结构化的 Markdown 报告，含标题、小标题和要点",
        agent=writer,
        context=[task_analyze],
    )

    # 后端 组装 Crew，顺序执行
    crew = Crew(
        agents=[researcher, analyst, writer],
        tasks=[task_research, task_analyze, task_write],
        process=Process.sequential,
        verbose=verbose,
    )

    result = crew.kickoff()

    duration = time.time() - start
    output_text = result.raw if hasattr(result, "raw") else str(result)

    return {
        "method": "CrewAI-真实库-固定角色顺序执行",
        "agent_count": 3,
        "execution_mode": "sequential",
        "dynamic_scheduling": False,
        "self_reflection": False,
        "duration_s": round(duration, 2),
        "final_output": output_text,
    }


def run_comparison(task_input: str) -> dict:
    print("=" * 60)
    print("CrewAI 版本（真实库 · 固定3角色顺序执行）")
    print("=" * 60)

    result = crewai_execute(task_input)

    print(f"\n耗时: {result['duration_s']}s")
    print(f"Agent数: {result['agent_count']} (固定)")
    print(f"模式: {result['execution_mode']}")

    return result


if __name__ == "__main__":
    result = run_comparison("搜索2026年AI Agent发展趋势")
    print(f"\n最终报告预览:\n{result['final_output'][:800]}...")
