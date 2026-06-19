# 后端 MCP 工具注册与管理中心
import json
from typing import Any, Callable

class MCPTool:
    # 后端 MCP 单个工具定义
    def __init__(self, name: str, description: str, func: Callable, parameters: dict = None):
        self.name = name
        self.description = description
        self.func = func
        self.parameters = parameters or {}

    def to_openai_schema(self) -> dict:
        # 后端 转为 OpenAI function calling 格式
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }

class MCPManager:
    # 后端 MCP 工具管理器 — 统一注册、发现、调用
    def __init__(self):
        self._tools: dict[str, MCPTool] = {}

    def register(self, tool: MCPTool) -> None:
        # 后端 注册工具到管理器
        self._tools[tool.name] = tool

    def get_schemas(self) -> list[dict]:
        # 后端 获取所有工具的 OpenAI function calling schema
        return [t.to_openai_schema() for t in self._tools.values()]

    def get_tool_names(self) -> list[str]:
        # 后端 获取所有工具名称
        return list(self._tools.keys())

    def get_descriptions(self) -> str:
        # 后端 生成工具列表描述文本，供 Prompt 使用
        lines = []
        for t in self._tools.values():
            lines.append(f"- **{t.name}**: {t.description}")
        return "\n".join(lines)

    def call(self, name: str, arguments: dict) -> Any:
        # 后端 调用指定工具
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"工具不存在: {name}")
        return tool.func(**arguments)

# 后端 全局单例
mcp_manager = MCPManager()
