# 后端 Master Agent — 任务拆解 + Agent 分配 + 向量记忆增强
import json
import re
from app.core.logger import get_logger
from app.core.llm import get_llm_response
from app.core.mcp_manager import mcp_manager
from app.memory.vector_store import vector_memory
from app.agent.worker import get_available_agent_types, ROLE_DESCRIPTIONS

logger = get_logger(__name__)

MASTER_SYSTEM_PROMPT = """你是任务拆解专家。先理解用户意图，再拆解。

可用 Agent：
{agent_types}

{memory_context}

返回 JSON（先输出 intent 再输出 subtasks）：
{{
  "intent": "用一句话概括用户要做什么",
  "keywords": ["核心关键词1", "核心关键词2"],
  "subtasks": [
    {{
      "id": "sub_1",
      "description": "子任务描述（带上关键词确保搜索准确）",
      "agent_type": "从可用类型中选",
      "depends_on": []
    }}
  ]
}}

规则：
- 先想清楚用户到底要什么（intent），再拆子任务
- description 里带上 keywords 中的关键词，确保 Worker 搜索准确
- 单一意图（搜新闻/查天气/写代码/翻译/读文件）→ 只拆 1 个
- 复合意图（搜+分析+画图）→ 最多拆 3 个
- 禁止编造 Agent 类型"""


def decompose_task(user_input: str, conversation_history: list[dict] = None) -> list[dict]:
    """后端 Master 核心：将用户任务拆解为子任务列表"""

    agent_types = get_available_agent_types()

    # 后端 向量记忆增强：搜索 3 个最相似历史任务作为参考
    memory_context = ""
    try:
        similar_tasks = vector_memory.search(user_input, k=3)
        if similar_tasks and any(similar_tasks):
            memory_context = "历史相似任务经验（参考其拆解策略，但根据当前任务调整）：\n"
            for i, mem in enumerate(similar_tasks, 1):
                if mem:
                    memory_context += f"{i}. {mem[:300]}\n"
    except Exception:
        pass  # 后端 记忆搜索失败不影响主流程

    # 后端 对话历史注入：让 Master 理解多轮上下文
    history_context = ""
    if conversation_history:
        recent = conversation_history[-5:]  # 最近 5 轮
        history_context = "对话历史（理解上下文用，不要重复执行已完成的步骤）：\n"
        for h in recent:
            history_context += f"- {h['role']}: {h['content'][:200]}\n"

    messages = [
        {"role": "system", "content": MASTER_SYSTEM_PROMPT.format(
            agent_types="\n".join(f"- {t}: {ROLE_DESCRIPTIONS.get(t, '通用任务')}" for t in agent_types),
            memory_context=(history_context + "\n" + memory_context) if history_context else memory_context,
        )},
        {"role": "user", "content": f"请拆解以下任务：\n{user_input}"},
    ]

    response = get_llm_response(messages, temperature=0.1, max_tokens=1024)

    # 后端 清理 LLM 返回的各种包裹格式
    response = response.strip()
    # 后端 去掉 ```json ... ``` 或 ``` ... ``` 包裹
    for prefix in ("```json", "```"):
        if response.startswith(prefix):
            response = response[len(prefix):].lstrip()
            break
    if response.endswith("```"):
        response = response[:-3].rstrip()

    # 后端 尝试从文本中提取 JSON 对象（处理 LLM 在 JSON 前后加废话的情况）
    if not response.startswith("{"):
        import re
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            response = json_match.group(0)

    try:
        plan = json.loads(response)
        subtasks = plan.get("subtasks", [])
        intent = plan.get("intent", user_input)

        # 后端 补全每个子任务的默认字段，注入全局意图
        for i, task in enumerate(subtasks):
            task.setdefault("id", f"sub_{i+1}")
            task["status"] = "pending"
            task["result"] = None
            task["retries"] = 0
            # 后端 让 Worker 知道总体目标，搜索时更有方向
            task["_intent"] = intent

        logger.info(f"任务拆解完成: {len(subtasks)} 个子任务, 意图: {intent[:50]}")
        return subtasks

    except json.JSONDecodeError:
        # 后端 JSON 解析失败 → 兜底用 researcher（能搜能读），不用 coder（没搜索工具会瞎编）
        logger.warning(f"Master JSON 解析失败，兜底使用 researcher: {response[:100]}")
        return [{
            "id": "sub_1", "description": user_input,
            "agent_type": "researcher", "depends_on": [],
            "status": "pending", "result": None, "retries": 0,
            "_intent": user_input[:50],
        }]
