# 后端 Worker Agent 工厂 — 动态生成执行Agent（支持 function calling）
import json
from ..core.llm import llm_client
from ..core.config import settings
from ..core.mcp_manager import mcp_manager

WORKER_SYSTEM_PROMPT = """你是一个 {agent_type} 专家。你的职责：{role_description}

重要规则：
- 涉及联网搜索/查天气/读文件/执行代码等操作时，必须调用对应工具获取真实数据
- 不要编造数据，工具返回什么就用什么
- 输出最终结果即可，不要解释过程"""

ROLE_DESCRIPTIONS = {
    "data_cleaner": "清洗和预处理数据，处理缺失值、异常值、格式统一。",
    "analyst": "对数据进行统计分析，计算关键指标，发现趋势和规律。",
    "visualizer": "生成数据可视化图表。使用 matplotlib 绘图。",
    "coder": "编写可运行的 Python 代码来完成任务，代码要完整可直接执行。",
    "researcher": "搜索并整理最新信息。必须调用 search_internet 工具获取实时数据。",
    "writer": "将前面的分析结果整合成结构化的文档报告，输出 Markdown。",
    "executor": "在安全沙箱中执行 Python 代码，返回执行结果。",
}

def execute_subtask(subtask: dict) -> str:
    # 后端 Worker Agent 执行子任务（function calling 模式）
    agent_type = subtask["agent_type"]
    role_desc = ROLE_DESCRIPTIONS.get(agent_type, "完成分配的子任务。")

    system_prompt = WORKER_SYSTEM_PROMPT.format(
        agent_type=agent_type,
        role_description=role_desc,
    )

    # 后端 构建上下文
    context = ""
    if subtask.get("depends_on"):
        dep_results = subtask.get("_dep_results", "")
        if dep_results:
            context = f"前置子任务输出：\n{dep_results}\n\n"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{context}请完成子任务：{subtask['description']}"},
    ]

    # 后端 function calling 循环（最多3轮）
    tools = mcp_manager.get_schemas()
    for _ in range(3):
        response = llm_client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=0.3,
            max_tokens=4096,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
        )

        msg = response.choices[0].message

        # 后端 模型直接返回文本 → 最终答案
        if not msg.tool_calls:
            return msg.content or ""

        # 后端 模型要求调工具 → 逐个执行并追加结果到对话
        messages.append(msg)
        for tc in msg.tool_calls:
            tool_name = tc.function.name
            try:
                tool_args = json.loads(tc.function.arguments)  # 后端 解析工具参数
                tool_result = str(mcp_manager.call(tool_name, tool_args))  # 后端 实际执行
            except Exception as e:
                tool_result = f"工具调用失败: {str(e)}"

            messages.append({  # 后端 工具结果追加到上下文
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_result,
            })

    # 后端 超过最大轮数 → 强制生成最终回答（不带工具）
    final_resp = llm_client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=0.3,
        max_tokens=4096,
    )
    return final_resp.choices[0].message.content or ""
