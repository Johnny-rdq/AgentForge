# 后端 Reflector — 反思审查 + 自动修正循环
import json
from app.core.logger import get_logger
from app.core.llm import get_llm_response

logger = get_logger(__name__)

REFLECTOR_PROMPT = """你是一个严格的质量审查员。检查以下子任务执行结果，判断是否合格。

审查标准：
1. 完整性：是否完成了子任务描述中的所有要求
2. 准确性：结果是否正确，有无明显错误
3. 可用性：输出是否可以直接被后续步骤使用
4. 格式：输出格式是否清晰、结构良好

如果合格，返回：
{{"pass": true, "comment": "简要说明"}}

如果不合格，返回：
{{"pass": false, "issues": ["问题1", "问题2"], "fix_suggestion": "具体修改建议"}}

子任务描述：{task_description}

执行结果：
{result}

请审查："""

FIX_PROMPT = """你之前执行的结果未通过审查。请根据以下反馈修正你的输出。

审查反馈：
{issues}

修改建议：
{fix_suggestion}

原始任务：
{task_description}

原始输出：
{original_result}

请输出修正后的完整结果，不要解释修改了什么，直接输出最终结果。"""


def reflect_on_result(task_description: str, result: str) -> dict:
    """后端 质量审查：让 LLM 评估执行结果是否合格"""
    messages = [{"role": "user", "content": REFLECTOR_PROMPT.format(
        task_description=task_description, result=result,
    )}]
    response = get_llm_response(messages, temperature=0.1)

    # 后端 清理 markdown 代码块
    response = response.strip()
    if response.startswith("```"):
        response = response.split("\n", 1)[1]
        if response.endswith("```"):
            response = response[:-3]

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        logger.warning("反思审查 JSON 解析失败，默认通过")
        return {"pass": True, "comment": "格式解析异常，默认通过"}


def fix_result(task_description: str, original_result: str, issues: list[str], fix_suggestion: str) -> str:
    """后端 根据审查反馈修正不合格结果"""
    messages = [{"role": "user", "content": FIX_PROMPT.format(
        issues="\n".join(f"- {i}" for i in issues),
        fix_suggestion=fix_suggestion,
        task_description=task_description,
        original_result=original_result,
    )}]
    return get_llm_response(messages, temperature=0.3, max_tokens=4096)


def reflect_and_fix(subtask: dict, max_retries: int = 2) -> tuple[str, int]:
    """后端 反思+修正循环：最多重试 max_retries 次直到审查通过"""
    result = subtask.get("result", "")
    task_desc = subtask.get("description", "")

    for attempt in range(max_retries):
        review = reflect_on_result(task_desc, result)

        if review.get("pass", False):
            logger.info(f"反思通过 (尝试 {attempt+1}/{max_retries})")
            return result, attempt

        # 后端 不合格 → 调 LLM 修正
        logger.info(f"反思未通过，第 {attempt+1} 次修正...")
        result = fix_result(
            task_desc, result,
            review.get("issues", []),
            review.get("fix_suggestion", ""),
        )

    logger.warning(f"反思修正耗尽最大重试次数 ({max_retries})")
    return result, max_retries
