# 后端 LLM 客户端 — OpenAI 兼容接口，多 Provider 切换
# 后端 provider 切换机制：settings.llm_provider 决定 base_url（agnes/dashscope/openai/deepseek）
# 后端   也可在 .env 中直接设 LLM_BASE_URL 覆盖任何自动匹配
from openai import OpenAI
from app.core.config import settings

# 后端 全局 LLM 客户端（base_url 根据 provider 自动切换，见 config.py:get_base_url()）
llm_client = OpenAI(
    api_key=settings.llm_api_key,
    base_url=settings.get_base_url(),
)


def get_llm_response(messages: list, temperature: float = None, max_tokens: int = None) -> str:
    """后端 非流式调用 LLM，阻塞等待完整回复后返回（用于需要完整结果才能继续的场景，如修复代码）"""
    response = llm_client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=temperature or settings.llm_temperature,
        max_tokens=max_tokens or settings.llm_max_tokens,
        stream=False,
    )
    return response.choices[0].message.content


def get_llm_stream(messages: list, temperature: float = None, max_tokens: int = None):
    """后端 流式调用 LLM，返回生成器逐 token 产出（Worker 用，token 通过队列推 SSE）
    注意：调用方需用 for token in get_llm_stream(...): 来消费，不要 list() 一次性收集
    """
    stream = llm_client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=temperature or settings.llm_temperature,
        max_tokens=max_tokens or settings.llm_max_tokens,
        stream=True,
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
