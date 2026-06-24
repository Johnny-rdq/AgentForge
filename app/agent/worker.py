# 后端 Worker Agent — 执行子任务（直接模式 1 轮 LLM / 复杂任务 function calling 多轮）
import os
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

# 后端 本地文档分析专用 prompt：不要求来源链接
FILE_READING_PROMPT = """你是文档分析专家。

当前日期：{current_date}

你正在分析一份用户上传的本地文档。

规则：
- 用 Markdown 格式输出，结构清晰
- 只基于文档内容回答，不要编造
- 不要添加"来源"、"参考链接"等网络搜索相关的内容
- 这是本地文件，没有来源 URL，直接给出分析结果即可
- 控制在 500 字以内，只讲重点"""

# 后端 可视化专用 prompt：强制生成 matplotlib 代码并保存到 data/generated/
VISUALIZATION_PROMPT = """你是 {agent_type} 专家。

当前日期：{date_str}

你必须生成一段完整可执行的 Python 代码来创建图表。严格按以下规则：

1. 开头必须写：
   import matplotlib; matplotlib.use('Agg')
   import matplotlib.pyplot as plt
   import numpy as np

2. 中文字体设置（必须）：
   plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS', 'sans-serif']
   plt.rcParams['axes.unicode_minus'] = False

3. 保存图表用 plt.savefig，文件名用英文（如 chart.png / chart_pie.png / chart_bar.png），dpi=150, bbox_inches='tight'

4. 保存后用 print("CHART_SAVED: 文件名.png") 输出文件名，方便后续引用

5. 禁止 import os / subprocess / sys / shutil（会被安全拦截）

6. 代码要完整可直接运行，不要省略 import

7. 用 ```python ... ``` 包裹代码，只输出代码块，不要多余解释"""

ROLE_DESCRIPTIONS = {
    "data_cleaner": "清洗和预处理数据，处理缺失值、异常值、格式统一。",
    "analyst": "对数据进行统计分析，计算关键指标，发现趋势和规律。",
    "visualizer": "一站式生成数据可视化图表（自动写代码+执行+保存图片）。直接描述想要的图表即可，无需额外拆分编写/执行步骤。在回复中用 ![描述](/generated/文件名.png) 引用图片。",
    "coder": "编写可运行的 Python 代码来完成任务，代码要完整可直接执行。生成的文件（图表/HTML等）用 /generated/文件名 路径引用。",
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
    """后端 流式生成最终回复（有 _token_bridge 时逐 token 推送，结束后放哨兵）"""
    if _token_bridge is not None:
        full = ""
        try:
            for token in get_llm_stream(messages, temperature=0.3, max_tokens=max_tokens):
                full += token
                try:
                    _token_bridge.put(token)
                except Exception:
                    pass
            # 后端 哨兵：通知主循环流式输出已完成
            try:
                _token_bridge.put(None)
            except Exception:
                pass
            if full:
                return full
        except Exception as e:
            logger.warning(f"流式生成中断: {str(e)[:80]}, 已收到 {len(full)} 字符")
            # 后端 发哨兵，避免主循环死等
            try:
                _token_bridge.put(None)
            except Exception:
                pass
            if full:
                return full  # 后端 有部分内容就直接返回，不回退到非流式（省时间）
    # 后端 降级：无 bridge 或流式完全失败时才用非流式
    if _token_bridge is None:
        try:
            resp = llm_client.chat.completions.create(
                model=settings.llm_model, messages=messages,
                temperature=0.3, max_tokens=max_tokens,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.warning(f"LLM 调用失败: {str(e)[:100]}")
            return str(e)
    return full or ""  # 后端 流式已启动过，即使 full 为空也返回空字符串，不回退


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
    original_input = subtask.get("_original_input", "")  # 后端 原始用户输入（含文件路径等）

    # 后端 从原始输入 + 对话历史提取文件路径，直接读取内容 → 注入 LLM 上下文（不依赖 function calling）
    uploaded_file_path = _extract_file_path(original_input) or ""
    if not uploaded_file_path:
        # 后端 当前消息没路径 → 从对话历史中查找之前上传的文件
        for h in subtask.get("_history", []):
            if h.get("role") == "user":
                found = _extract_file_path(h.get("content", ""))
                if found:
                    uploaded_file_path = found
                    break
    uploaded_file_content = ""
    if uploaded_file_path:
        logger.info(f"📎 检测到上传文件: {uploaded_file_path}")
        uploaded_file_content = str(mcp_manager.call("read_file", {"file_path": uploaded_file_path}))
        if "文件不存在" not in uploaded_file_content and "解析失败" not in uploaded_file_content:
            uploaded_file_content = f"\n\n📄 用户上传文件「{os.path.basename(uploaded_file_path)}」的内容：\n{uploaded_file_content}\n\n请基于以上文件内容完成子任务。"
        else:
            logger.warning(f"文件读取失败: {uploaded_file_path} → {uploaded_file_content[:80]}")
            uploaded_file_content = ""

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
    direct_result = _try_direct_mode(intent, user_input, agent_type, dep_context, date_str, original_input)
    if direct_result is not None:
        return direct_result

    # ===== Function Calling 模式：复杂/模糊任务 =====
    context = f"用户总体目标：{intent}\n\n" if intent else ""
    # 后端 注入已预读的上传文件内容，确保 LLM 无需调用 read_file 也能看到内容
    file_hint = f"\n\n{uploaded_file_content}" if uploaded_file_content else ""
    system_prompt = WORKER_SYSTEM_PROMPT.format(
        agent_type=agent_type, current_date=date_str, context="",
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{dep_context}{context}请完成子任务：{user_input}{file_hint}"},
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


def _get_llm_response_sync(messages: list, temperature: float = 0.3, max_tokens: int = 2048) -> str:
    """后端 非流式 LLM 调用（用于需要完整返回才能继续的场景，如生成代码后执行）"""
    try:
        resp = llm_client.chat.completions.create(
            model=settings.llm_model, messages=messages,
            temperature=temperature, max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        logger.warning(f"LLM 非流式调用失败: {str(e)[:100]}")
        return ""


def _extract_code_block(text: str) -> str:
    """后端 从 LLM 输出中提取 Python 代码块"""
    import re
    m = re.search(r'```python\s*\n(.*?)```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r'```\s*\n(.*?)```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


def _extract_city(text: str) -> str:
    """后端 从用户输入中提取城市名（查天气用）"""
    import re
    # 后端 常见城市名模式
    cities = ["北京", "上海", "广州", "深圳", "杭州", "成都", "重庆", "武汉", "南京", "西安",
              "天津", "苏州", "长沙", "郑州", "东莞", "青岛", "沈阳", "宁波", "昆明", "大连",
              "厦门", "合肥", "佛山", "福州", "哈尔滨", "济南", "温州", "长春", "石家庄",
              "常州", "泉州", "南宁", "贵阳", "南昌", "太原", "烟台", "嘉兴", "南通", "金华",
              "珠海", "惠州", "徐州", "海口", "乌鲁木齐", "兰州", "呼和浩特", "银川", "三亚",
              "Tokyo", "London", "New York", "Paris", "Berlin", "Sydney", "Beijing", "Shanghai",
              "Shenzhen", "Guangzhou", "Hangzhou", "Chengdu", "Seoul", "Singapore", "Bangkok"]
    for city in cities:
        if city in text:
            return city
    # 后端 匹配 "XX天气" / "XX的天气" 模式
    m = re.search(r'(\S{2,4})(?:的)?天气', text)
    if m:
        return m.group(1)
    return ""


def _try_direct_mode(intent: str, user_input: str, agent_type: str,
                     dep_context: str, date_str: str, original_input: str = "") -> str | None:
    """后端 直接模式：预判工具 → 直接调用 → 1 轮 LLM 总结

    返回 None 表示不适合直接模式，走 function calling
    """
    # 后端 读文件意图：直接读 → 一次性总结
    if "读取并分析文件" in intent or "读文件" in intent:
        # 后端 先从子任务描述提取，失败则从原始用户输入提取
        file_path = _extract_file_path(user_input) or _extract_file_path(original_input)
        if not file_path:
            return None  # 后端 提取不到路径，走 function calling 让 LLM 找
        logger.info(f"⚡ 直接模式 读文件: {file_path}")
        file_content = mcp_manager.call("read_file", {"file_path": file_path})
        system_prompt = FILE_READING_PROMPT.format(current_date=date_str)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{dep_context}请分析以下文件内容并回答用户问题。\n\n用户问题：{user_input}\n\n文件内容：\n{file_content}"},
        ]
        return _stream_response(messages)

    # 后端 天气意图：直接查天气 → 一次性总结
    if "天气" in intent or "天气" in user_input or "weather" in intent.lower() or "weather" in user_input.lower():
        # 后端 从用户输入中提取城市名
        city = _extract_city(user_input)
        if city:
            logger.info(f"⚡ 直接模式 天气: {city}")
            weather_result = mcp_manager.call("fetch_weather", {"city": city})
            system_prompt = WORKER_SYSTEM_PROMPT.format(
                agent_type=agent_type, current_date=date_str, context="你正在报告天气信息。",
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{dep_context}请根据以下天气数据给出简洁报告。\n\n用户问题：{user_input}\n\n天气数据：\n{weather_result}"},
            ]
            return _stream_response(messages)

    # 后端 可视化意图：LLM 生成 matplotlib 代码 → 自动执行 → 扫描产出文件 → 引用图片
    # 后端 必须排在搜索前面！避免"根据搜索到的数据画饼图"被搜索模式抢先命中
    # 后端 agent_type=visualizer 直接走可视化模式，另加关键词兜底
    _vis_keywords = ["画", "图", "可视化", "绘图", "作图", "chart", "plot", "visualiz", "matplotlib",
                     "柱状", "折线", "饼", "散点", "热力", "直方", "曲线", "图形", "图像"]
    if agent_type == "visualizer" or any(kw in intent for kw in _vis_keywords) or any(kw in user_input for kw in _vis_keywords):
        logger.info(f"⚡ 直接模式 可视化: {user_input[:60]}")
        code_prompt = VISUALIZATION_PROMPT.format(
            agent_type=agent_type, date_str=date_str,
        )
        code_messages = [
            {"role": "system", "content": code_prompt},
            {"role": "user", "content": f"{dep_context}请根据以下需求生成 Python 绘图代码。\n\n用户需求：{user_input}"},
        ]
        # 后端 步骤1：LLM 生成代码（非流式，需要完整代码才能执行）
        code_text = _get_llm_response_sync(code_messages)
        logger.info(f"可视化代码生成: 收到 {len(code_text or '')} 字符, 含```python: {'```python' in (code_text or '')}")
        if not code_text:
            logger.warning(f"可视化代码生成为空！降级重试一次")
            # 后端 重试：换个说法再问一次
            code_messages_retry = [
                {"role": "system", "content": code_prompt},
                {"role": "user", "content": f"我需要一段完整的 Python 绘图代码。请直接输出 ```python ... ``` 代码块。\n\n需求：{user_input}"},
            ]
            code_text = _get_llm_response_sync(code_messages_retry)
            logger.info(f"可视化代码重试: 收到 {len(code_text or '')} 字符")

        code_block = _extract_code_block(code_text)
        # 后端 兜底：如果没有 ```python 标记但内容看起来像代码，直接用全文
        if not code_block and code_text and ("import matplotlib" in code_text or "plt." in code_text or "savefig" in code_text):
            code_block = code_text.strip()
            logger.info("可视化代码提取兜底：未检测到 ```python 标记，使用全文作为代码")

        if code_block:
            # 后端 步骤2：执行代码（首次尝试）
            exec_result = mcp_manager.call("execute_python", {"code": code_block})
            logger.info(f"可视化代码执行完成: {exec_result[:120]}")

            # 后端 步骤3：执行失败 → LLM 修复重试一次
            if "返回码]: 1" in exec_result or "[返回码]: 1" in exec_result or "安全拦截" in exec_result or "Traceback" in exec_result:
                logger.warning(f"可视化代码首次执行失败，尝试让 LLM 修复: {exec_result[:150]}")
                fix_messages = [
                    {"role": "system", "content": "你是 Python 专家。以下绘图代码执行失败，请修复后只输出完整代码（用 ```python 包裹）。禁止 import os/subprocess/sys/shutil。"},
                    {"role": "user", "content": f"原代码：\n```python\n{code_block}\n```\n\n错误输出：\n{exec_result}\n\n请输出修复后的完整代码。"},
                ]
                fixed_text = _get_llm_response_sync(fix_messages)
                fixed_code = _extract_code_block(fixed_text)
                if not fixed_code and fixed_text:
                    fixed_code = fixed_text.strip()
                if fixed_code and fixed_code != code_block:
                    exec_result = mcp_manager.call("execute_python", {"code": fixed_code})
                    logger.info(f"可视化代码修复后执行: {exec_result[:120]}")

            # 后端 步骤4：扫描 data/generated/ 目录，找出本次生成的图片文件
            gen_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "generated")
            image_files = []
            if os.path.isdir(gen_dir):
                for f in os.listdir(gen_dir):
                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.html')):
                        fpath = os.path.join(gen_dir, f)
                        try:
                            image_files.append((f, os.path.getmtime(fpath)))
                        except OSError:
                            image_files.append((f, 0))
                image_files.sort(key=lambda x: x[1], reverse=True)  # 后端 最新文件排前面
                image_files = [f[0] for f in image_files[:8]]  # 后端 最多取 8 个

            # 后端 步骤5：构建文件引用列表，告诉 LLM 实际生成了哪些文件
            if image_files:
                file_list = "\n".join(f"  - /generated/{f}" for f in image_files)
                file_hint = f"以下是你生成的实际文件（请用这些确切的文件名在回复中引用）：\n{file_list}"
            else:
                file_hint = "（未检测到新生成的图片文件，请根据代码执行输出判断）"

            desc_prompt = WORKER_SYSTEM_PROMPT.format(
                agent_type=agent_type, current_date=date_str,
                context="你已成功生成图表。请在回复中用 ![描述](/generated/文件名.png) 引用实际生成的图片文件。",
            )
            desc_messages = [
                {"role": "system", "content": desc_prompt},
                {"role": "user", "content": f"用户需求：{user_input}\n\n代码执行输出：\n{exec_result}\n\n{file_hint}\n\n请用 Markdown 描述图表内容，并用 ![描述](/generated/实际文件名.png) 嵌入图片。"},
            ]
            return _stream_response(desc_messages)

        # 后端 代码生成完全失败 → 降级为普通文本回复
        logger.warning(f"可视化代码生成为空，降级为文本回复")
        desc_prompt = WORKER_SYSTEM_PROMPT.format(
            agent_type=agent_type, current_date=date_str, context="请直接输出结果。",
        )
        return _stream_response([
            {"role": "system", "content": desc_prompt},
            {"role": "user", "content": f"{dep_context}{user_input}"},
        ])

    # 后端 搜索/调研意图：直接搜 → 一次性总结
    # 后端 注意：排在可视化之后，且排除含可视化关键词的描述（如"根据搜索到的数据画饼图"）
    _search_kw = ["搜索", "调研", "查找", "查询", "查", "搜", "research", "search", "最新", "趋势", "新闻"]
    _vis_kw_set = {"画", "图", "可视化", "绘图", "作图", "chart", "plot", "visualiz", "matplotlib",
                   "柱状", "折线", "饼", "散点", "热力", "直方", "曲线", "图形", "图像"}
    _has_vis = any(kw in intent for kw in _vis_kw_set) or any(kw in user_input for kw in _vis_kw_set)
    if not _has_vis and (any(kw in intent for kw in _search_kw) or any(kw in user_input for kw in _search_kw)):
        logger.info(f"⚡ 直接模式 搜索: {user_input[:60]}")
        search_result = mcp_manager.call("search_internet", {"query": user_input[:200]})
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
