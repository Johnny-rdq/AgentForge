# 后端 MCP Server — 工具注册入口，启动时将所有工具注册到 MCP Manager
from ..core.mcp_manager import MCPTool, mcp_manager
from .file_tools import read_file, write_file, list_files, FILE_TOOL_SCHEMAS
from .code_tools import execute_python, install_package, CODE_TOOL_SCHEMAS
from .search_tools import search_internet, fetch_weather, SEARCH_TOOL_SCHEMAS

def register_all_tools():
    # 后端 注册所有 MCP 工具到管理器

    # 后端 文件操作工具
    mcp_manager.register(MCPTool(
        name="read_file",
        description="读取文件内容，支持 txt/csv/json/md 等文本格式",
        func=read_file,
        parameters=FILE_TOOL_SCHEMAS["read_file"]["parameters"],
    ))
    mcp_manager.register(MCPTool(
        name="write_file",
        description="将生成的内容写入文件保存",
        func=write_file,
        parameters=FILE_TOOL_SCHEMAS["write_file"]["parameters"],
    ))

    # 后端 代码执行工具
    mcp_manager.register(MCPTool(
        name="execute_python",
        description="在安全沙箱中执行 Python 代码并返回结果，超时30秒",
        func=execute_python,
        parameters=CODE_TOOL_SCHEMAS["execute_python"]["parameters"],
    ))
    mcp_manager.register(MCPTool(
        name="install_package",
        description="安装 Python 包到当前环境",
        func=install_package,
        parameters=CODE_TOOL_SCHEMAS["install_package"]["parameters"],
    ))

    # 后端 搜索工具
    mcp_manager.register(MCPTool(
        name="search_internet",
        description="使用 DuckDuckGo 联网搜索信息",
        func=search_internet,
        parameters=SEARCH_TOOL_SCHEMAS["search_internet"]["parameters"],
    ))
    mcp_manager.register(MCPTool(
        name="fetch_weather",
        description="查询城市实时天气信息",
        func=fetch_weather,
        parameters=SEARCH_TOOL_SCHEMAS["fetch_weather"]["parameters"],
    ))

    print(f"[MCP] 已注册 {len(mcp_manager._tools)} 个工具: {mcp_manager.get_tool_names()}")
