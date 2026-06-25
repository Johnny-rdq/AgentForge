# 后端 MCP 工具管理器 — 注册、Schema 转换、调用分发
import json
from typing import Any, Callable
from app.core.logger import get_logger

logger = get_logger(__name__)


class MCPTool:
    """后端 单个 MCP 工具：名称 + 描述 + 执行函数 + 参数 Schema"""

    def __init__(self, name: str, description: str, func: Callable, parameters: dict = None):
        self.name = name
        self.description = description
        self.func = func
        self.parameters = parameters or {}

    def to_openai_schema(self) -> dict:
        """后端 转为 OpenAI function calling 标准格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }


class MCPManager:
    """后端 MCP 工具管理器单例 — 注册、聚合 Schema、按名调用"""

    def __init__(self):
        self._tools: dict[str, MCPTool] = {}

    def register(self, tool: MCPTool) -> None:
        """后端 注册工具到管理器（同名会覆盖，用于热更新场景）"""
        self._tools[tool.name] = tool
        logger.debug(f"MCP 工具已注册: {tool.name}")

    def get_schemas(self) -> list[dict]:
        """后端 返回所有工具的 OpenAI function calling schema 列表，用于 LLM tools 参数"""
        return [t.to_openai_schema() for t in self._tools.values()]

    def get_tool_names(self) -> list[str]:
        """后端 返回所有已注册工具的名称列表（调试/日志用）"""
        return list(self._tools.keys())

    def get_descriptions(self) -> str:
        """后端 生成工具列表的文本描述，供 LLM prompt 使用"""
        lines = [f"- **{t.name}**: {t.description}" for t in self._tools.values()]
        return "\n".join(lines)

    def call(self, name: str, arguments: dict) -> Any:
        """后端 按名称调用工具，解包参数执行
        抛出 ValueError：工具未注册时（调用方应 catch 并返回友好错误给 LLM）
        """
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"工具不存在: {name}")
        logger.debug(f"MCP 调用: {name}({json.dumps(arguments, ensure_ascii=False)[:100]})")
        return tool.func(**arguments)


mcp_manager = MCPManager()
