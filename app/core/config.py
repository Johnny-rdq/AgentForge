# 后端 全局配置管理
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 后端 LLM 配置
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "qwen-plus")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # 后端 服务配置
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "7860"))

    # 后端 Agent 配置
    max_workers: int = int(os.getenv("MAX_WORKERS", "6"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "2"))
    reflection_enabled: bool = os.getenv("REFLECTION_ENABLED", "true").lower() == "true"
    hitl_enabled: bool = os.getenv("HITL_ENABLED", "true").lower() == "true"

    # 后端 MCP 配置
    mcp_tool_timeout: int = int(os.getenv("MCP_TOOL_TIMEOUT", "30"))

    # 后端 记忆配置
    chroma_persist_dir: str = os.path.join(os.path.dirname(__file__), "..", "..", "data", "chroma_db")
    sqlite_db_path: str = os.path.join(os.path.dirname(__file__), "..", "..", "data", "agent_memory.db")

    model_config = {"env_file": ".env", "extra": "allow"}

settings = Settings()
