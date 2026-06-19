# 后端 Master Agent — 任务拆解与Agent分配（带记忆增强）
import json
import uuid
from ..core.llm import get_llm_response
from ..core.mcp_manager import mcp_manager
from ..memory.vector_store import vector_memory

MASTER_SYSTEM_PROMPT = """你是一个任务拆解专家。用户会给你一个复杂任务，你需要：

1. 分析任务，拆解为 2-6 个子任务
2. 为每个子任务分配合适的 Agent 类型（从可用类型中选择）
3. 标明子任务之间的依赖关系（A 的输出是 B 的输入时，B 依赖 A）

可用 Agent 类型：
{agent_types}

可用工具列表：
{tool_list}

{memory_context}

返回格式（严格 JSON）：
{{
  "subtasks": [
    {{
      "id": "sub_1",
      "description": "子任务描述（中文）",
      "agent_type": "从可用类型中选择",
      "depends_on": []
    }}
  ]
}}

规则：
- 没有依赖的子任务可以并行执行，有依赖的必须串行
- Agent 类型必须从可用类型中选，不要编造
- 参考历史经验中的成功策略，避免失败策略
- 子任务相互独立，边界清晰，不要重叠"""

def decompose_task(user_input: str) -> list[dict]:
    # 后端 Master Agent 拆解任务（带记忆增强）
    agent_types = [
        "data_cleaner",
        "analyst",
        "visualizer",
        "coder",
        "researcher",
        "writer",
        "executor",
    ]

    # 后端 搜索相似历史任务作为参考
    memory_context = ""
    try:
        similar_tasks = vector_memory.search(user_input, k=3)
        if similar_tasks and any(similar_tasks):
            memory_context = "历史相似任务经验（参考其拆解策略，但根据当前任务调整）：\n"
            for i, mem in enumerate(similar_tasks, 1):
                if mem:
                    memory_context += f"{i}. {mem[:300]}\n"
    except Exception:
        pass

    messages = [
        {"role": "system", "content": MASTER_SYSTEM_PROMPT.format(
            agent_types="\n".join(f"- {t}" for t in agent_types),
            tool_list=mcp_manager.get_descriptions(),
            memory_context=memory_context if memory_context else "",
        )},
        {"role": "user", "content": f"请拆解以下任务：\n{user_input}"},
    ]

    response = get_llm_response(messages, temperature=0.1)
    # 后端 清理 markdown 代码块包裹
    response = response.strip()
    if response.startswith("```"):
        response = response.split("\n", 1)[1]
        if response.endswith("```"):
            response = response[:-3]

    try:
        plan = json.loads(response)
        subtasks = plan.get("subtasks", [])
        # 后端 确保每个子任务有唯一 id
        for i, task in enumerate(subtasks):
            task["id"] = task.get("id", f"sub_{i+1}")
            task["status"] = "pending"
            task["result"] = None
            task["retries"] = 0
        return subtasks
    except json.JSONDecodeError:
        # 后端 解析失败时创建单个兜底任务
        return [{
            "id": "sub_1",
            "description": user_input,
            "agent_type": "coder",
            "depends_on": [],
            "status": "pending",
            "result": None,
            "retries": 0,
        }]
