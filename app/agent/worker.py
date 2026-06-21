# 后端 Worker Agent — 执行子任务（直接模式 1 轮 LLM / 复杂任务 function calling 多轮）
import json
import queue
import re
from datetime import datetime
from app.core.logger import get_logger
from app.core.llm import llm_client, get_llm_stream
from app.core.config import settings
from app.core.mcp_manager import mcp_manager

logger = get_logger(__name__)

# 后端 线程安全的 token 队列（chat.py 设置，Worker 线程写入，主协程消费）
_token_bridge: queue.Queue | None = None

WORKER_SYSTEM_PROMPT = """你是 {agent_type} 专家。

当前日期：{current_date}

{context}

规则：
- 用 Markdown 格式输出：标题 + 列表 + 链接
- 每条信息 1-2 句话，附来源链接
- 控制在 500 字以内，只讲重点
- 严格基于提供的资料回复，不编造"""

ROLE_DESCRIPTIONS = {
    "data_cleaner": "清洗和预处理数据，处理缺失值、异常值、格式统一。",
    "analyst": "对数据进行统计分析，计算关键指标，发现趋势和规律。",
    "visualizer": "生成数据可视化图表。使用 matplotlib 绘图并保存。",
    "coder": "编写可运行的 Python 代码来完成任务，代码要完整可直接执行。",
    "executor": "在安全沙箱中执行 Python 代码，返回执行结果。",
    "tester": "编写单元测试和集成测试代码，验证功能正确性，输出测试报告。",
    "reviewer": "审查代码质量和安全性，检查命名规范、逻辑漏洞和性能问题。",
    "researcher": "搜索并整理最新信息。必须调用 search_internet 工具。用 Markdown 列表输出，每条附链接。",
    "writer": "将前面的分析结果整合成结构化的文档报告，输出 Markdown 格式。",
    "translator": "将文本翻译为目标语言，保持原意的同时确保语句自然流畅。",
}

# 后端 按 Agent 类型决定 function calling 最大轮数
_FC_ROUNDS = {
    "researcher": 2, "data_cleaner": 2, "analyst": 2, "visualizer": 2,
    "executor": 2, "tester": 2, "reviewer": 2,
    "coder": 1, "writer": 1, "translator": 1,
}

# 后端 Agent 工具白名单
_AGENT_TOOLS = {
    "researcher": {"search_internet", "fetch_weather", "read_file"},
    "coder": {"execute_python", "install_package", "read_file", "list_files"},
    "executor": {"execute_python", "install_package"},
    "visualizer": {"execute_python"},
    "analyst": {"execute_python", "read_file", "search_internet"},
    "data_cleaner": {"execute_python", "read_file"},
    "writer": {"read_file"},
    "reviewer": {"read_file"},
    "tester": {"execute_python", "read_file"},
    "translator": set(),
}


def get_available_agent_types() -> list[str]:
    return list(ROLE_DESCRIPTIONS.keys())


def _extract_file_path(text: str) -> str | None:
    """后端 从用户输入中提取文件路径"""
    # 后端 匹配「路径」或直接路径
    m = re.search(r'路径[「「]([^」」]+)[」」]', text)
    if m:
        return m.group(1).strip()
    m = re.search(r'(?:saved_path|路径)[：:]\s*([^\s,\n]+)', text)
    if m:
        return m.group(1).strip()
    m = re.search(r'(data/uploads/[^\s\n）)]+)', text)
    if m:
        return m.group(1).strip()
    return None


def _stream_response(messages: list, max_tokens: int = 2048) -> str:
    """后端 流式生成最终回复（有 _token_bridge 时逐 token 推送）"""
    if _token_bridge is not None:
        try:
            full = ""
            for token in get_llm_stream(messages, temperature=0.3, max_tokens=max_tokens):
                full += token
                try:
                    _token_bridge.put(token)
                except Exception:
                    pass
            if full:
                return full
        except Exception as e:
            logger.warning(f"流式生成失败: {str(e)[:80]}")
    # 后端 降级：非流式
    try:
        resp = llm_client.chat.completions.create(
            model=settings.llm_model, messages=messages,
            temperature=0.3, max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        logger.warning(f"LLM 调用失败: {str(e)[:100]}")
        return str(e)


def execute_subtask(subtask: dict) -> str:
    """后端 Worker 执行子任务

    快速通道（直接模式）：根据意图预判工具→直接调用→1轮 LLM 总结（省 1 轮 function calling）
    复杂任务：走 function calling 多轮
    """
    agent_type = subtask["agent_type"]
    role_desc = ROLE_DESCRIPTIONS.get(agent_type, "完成分配的子任务。")
    max_rounds = _FC_ROUNDS.get(agent_type, 2)
    intent = subtask.get("_intent", "")
    user_input = subtask["description"]

    now = datetime.now()
    date_str = now.strftime("%Y年%m月%d日")

    # 后端 对话上下文（前置子任务结果等）
    dep_context = ""
    if subtask.get("depends_on"):
        dep_results = subtask.get("_dep_results", "")
        if dep_results:
            dep_context += f"前置子任务输出：\n{dep_results}\n\n"

    # 后端 按 Agent 类型过滤工具白名单
    allowed_tools = _AGENT_TOOLS.get(agent_type, set())
    all_tools = mcp_manager.get_schemas()
    tools = [t for t in all_tools if t["function"]["name"] in allowed_tools] if allowed_tools else []

    # ===== 直接模式：简单单意图任务，预判工具 → 直接调用 → 1 轮 LLM =====
    direct_result = _try_direct_mode(intent, user_input, agent_type, dep_context, date_str)
    if direct_result is not None:
        return direct_result

    # ===== Function Calling 模式：复杂/模糊任务 =====
    context = f"用户总体目标：{intent}\n\n" if intent else ""
    system_prompt = WORKER_SYSTEM_PROMPT.format(
        agent_type=agent_type, current_date=date_str, context="",
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{dep_context}{context}请完成子任务：{user_input}"},
    ]

    tool_results_collected = []

    for round_idx in range(max_rounds):
        is_last_round = (round_idx == max_rounds - 1)

        if is_last_round:
            return _stream_response(messages) or None

        try:
            response = llm_client.chat.completions.create(
                model=settings.llm_model, messages=messages,
                temperature=0.3, max_tokens=2048,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
            )
        except Exception as e:
            logger.warning(f"LLM 调用失败 ({agent_type}): {str(e)[:100]}")
            if tool_results_collected:
                return "\n\n".join(tool_results_collected)
            return str(e)

        msg = response.choices[0].message

        if not msg.tool_calls:
            return _stream_response(messages) or msg.content or ""

        messages.append(msg)

        for tc in msg.tool_calls:
            tool_name = tc.function.name
            try:
                tool_args = json.loads(tc.function.arguments)
                tool_result = str(mcp_manager.call(tool_name, tool_args))
                tool_results_collected.append(tool_result)
            except Exception as e:
                tool_result = f"工具调用失败: {str(e)}"

            messages.append({
                "role": "tool", "tool_call_id": tc.id, "content": tool_result,
            })


def _try_direct_mode(intent: str, user_input: str, agent_type: str,
                     dep_context: str, date_str: str) -> str | None:
    """后端 直接模式：预判工具 → 直接调用 → 1 轮 LLM 总结

    返回 None 表示不适合直接模式，走 function calling
    """
    # 后端 读文件意图：直接读 → 一次性总结
    if "读取并分析文件" in intent or "读文件" in intent:
        file_path = _extract_file_path(user_input)
        if not file_path:
            return None  # 后端 提取不到路径，走 function calling 让 LLM 找
        logger.info(f"⚡ 直接模式 读文件: {file_path}")
        file_content = mcp_manager.call("read_file", {"file_path": file_path})
        system_prompt = WORKER_SYSTEM_PROMPT.format(
            agent_type=agent_type, current_date=date_str, context="你正在分析一份文件。",
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{dep_context}请分析以下文件内容并回答用户问题。\n\n用户问题：{user_input}\n\n文件内容：\n{file_content}"},
        ]
        return _stream_response(messages)

    # 后端 搜索意图：直接搜 → 一次性总结
    if "搜索" in intent:
        logger.info(f"⚡ 直接模式 搜索: {user_input[:40]}")
        search_result = mcp_manager.call("search_internet", {"query": user_input})
        system_prompt = WORKER_SYSTEM_PROMPT.format(
            agent_type=agent_type, current_date=date_str, context="你正在整理搜索结果。",
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{dep_context}请根据以下搜索结果整理回复。\n\n用户问题：{user_input}\n\n搜索结果：\n{search_result}"},
        ]
        return _stream_response(messages)

    # 后端 翻译意图：不需要工具，直接 LLM 翻译
    if "翻译" in intent:
        logger.info(f"⚡ 直接模式 翻译: {user_input[:40]}")
        system_prompt = WORKER_SYSTEM_PROMPT.format(
            agent_type=agent_type, current_date=date_str, context="你是专业翻译。",
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{dep_context}请翻译以下内容：\n\n{user_input}"},
        ]
        return _stream_response(messages)

    # 后端 编程意图：不需要工具（纯生成代码）
    if "编写代码" in intent or "写代码" in intent:
        logger.info(f"⚡ 直接模式 编程: {user_input[:40]}")
        system_prompt = WORKER_SYSTEM_PROMPT.format(
            agent_type=agent_type, current_date=date_str, context="你是编程专家，直接输出可运行代码。",
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{dep_context}{user_input}"},
        ]
        return _stream_response(messages)

    return None  # 后端 不适合直接模式，走 function calling
