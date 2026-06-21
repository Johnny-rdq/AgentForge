# 后端 LLM 客户端 — OpenAI 兼容接口，多 Provider 切换
from openai import OpenAI
from app.core.config import settings

# 后端 全局 LLM 客户端（base_url 根据 provider 自动切换）
llm_client = OpenAI(
    api_key=settings.llm_api_key,
    base_url=settings.get_base_url(),
)


def get_llm_response(messages: list, temperature: float = None, max_tokens: int = None) -> str:
    """后端 非流式调用 LLM，返回完整回复文本"""
    response = llm_client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=temperature or settings.llm_temperature,
        max_tokens=max_tokens or settings.llm_max_tokens,
        stream=False,
    )
    return response.choices[0].message.content


def get_llm_stream(messages: list, temperature: float = None, max_tokens: int = None):
    """后端 流式调用 LLM，逐 token 产出（SSE 推送用）"""
    stream = llm_client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=temperature or settings.llm_temperature,
        max_tokens=max_tokens or settings.llm_max_tokens,
        stream=True,
    )
    for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
