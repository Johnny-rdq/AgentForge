# 后端 LLM 实例化（DashScope 兼容 OpenAI 接口）
from openai import OpenAI
from .config import settings

llm_client = OpenAI(
    api_key=settings.dashscope_api_key,
    base_url=settings.llm_base_url,
)

def get_llm_response(messages: list, temperature: float = None, max_tokens: int = None) -> str:
    # 后端 调用大模型获取回复
    response = llm_client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=temperature or settings.llm_temperature,
        max_tokens=max_tokens or settings.llm_max_tokens,
        stream=False,
    )
    return response.choices[0].message.content

def get_llm_stream(messages: list, temperature: float = None, max_tokens: int = None):
    # 后端 流式调用大模型
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
