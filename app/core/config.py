# 后端 全局配置管理 — 环境变量 + 多 Provider 切换
import os
from pydantic_settings import BaseSettings

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_PROVIDER_BASE_URLS = {
    "agnes": "https://apihub.agnes-ai.com/v1",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
}

class Settings(BaseSettings):
    # ========== LLM ==========
    llm_api_key: str = ""
    llm_model: str = "qwen-plus"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096
    llm_base_url: str = "https://apihub.agnes-ai.com/v1"
    llm_provider: str = "agnes"

    # ========== 服务 ==========
    app_host: str = "0.0.0.0"
    app_port: int = 7860

    # ========== Agent ==========
    max_workers: int = 6
    max_retries: int = 2
    reflection_enabled: bool = False  # 后端 默认关闭，仅 analyst/data_cleaner/visualizer 需要
    hitl_enabled: bool = True
    workflow_timeout: int = 300  # 后端 整体工作流超时秒数，防止卡死

    # ========== 网络 ==========
    http_proxy: str = ""  # 后端 HTTP 代理，国内访问国际服务需要
    https_proxy: str = ""  # 后端 HTTPS 代理

    # ========== 搜索 ==========
    tavily_api_key: str = ""

    # ========== MCP ==========
    mcp_tool_timeout: int = 30

    # ========== 日志 ==========
    log_level: str = "INFO"
    log_retention_days: int = 7

    # ========== 记忆 ==========
    vector_db_path: str = os.path.join(_PROJECT_ROOT, "data", "vector_memory.json")

    # ========== 数据库 (PostgreSQL) ==========
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_database: str = "agentforge"
    pg_user: str = "agentforge"
    pg_password: str = "agentforge123"

    # ========== Milvus 向量数据库 ==========
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_uri: str = ""  # 后端 Zilliz Cloud 端点（https://xxx.api.zillizcloud.com），配了就不用 host:port
    milvus_token: str = ""  # 后端 Zilliz Cloud API Key

    # ========== 腾讯云 OCR ==========
    tencent_secret_id: str = ""
    tencent_secret_key: str = ""

    model_config = {
        "env_file": os.path.join(_PROJECT_ROOT, ".env"),
        "extra": "allow",
    }

    def get_base_url(self) -> str:
        # 后端 优先用 .env 中显式设置的 URL，否则按 provider 自动匹配
        if self.llm_base_url and self.llm_base_url != "https://apihub.agnes-ai.com/v1":
            return self.llm_base_url
        return _PROVIDER_BASE_URLS.get(self.llm_provider, self.llm_base_url)

settings = Settings()
