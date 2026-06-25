# 后端 MCP 工具注册入口 — 应用启动时（lifespan）调用 register_all_tools()
# 后端 注册顺序：文件操作 → 代码执行 → 网络搜索（按功能分组，便于维护）
# 后端 每个工具的 Schema 参数从各模块的 *_TOOL_SCHEMAS 字典取，避免重复定义
from app.core.logger import get_logger
from app.core.mcp_manager import MCPTool, mcp_manager
from app.tools.file_tools import read_file, write_file, list_files, FILE_TOOL_SCHEMAS
from app.tools.code_tools import execute_python, install_package, CODE_TOOL_SCHEMAS
from app.tools.search_tools import search_internet, fetch_weather, SEARCH_TOOL_SCHEMAS

logger = get_logger(__name__)


def register_all_tools():
    """后端 注册所有 MCP 工具到全局管理器（FastAPI lifespan 启动时调用一次）"""

    mcp_manager.register(MCPTool(
        name="read_file", description="读取文件内容，支持 txt/csv/json/md 等文本格式",
        func=read_file, parameters=FILE_TOOL_SCHEMAS["read_file"]["parameters"],
    ))
    mcp_manager.register(MCPTool(
        name="write_file", description="将生成的内容写入文件保存",
        func=write_file, parameters=FILE_TOOL_SCHEMAS["write_file"]["parameters"],
    ))
    mcp_manager.register(MCPTool(
        name="list_files", description="列出指定目录内容，返回 JSON 格式的文件名列表",
        func=list_files, parameters=FILE_TOOL_SCHEMAS["list_files"]["parameters"],
    ))

    mcp_manager.register(MCPTool(
        name="execute_python", description="在安全沙箱中执行 Python 代码并返回结果，超时 30 秒。危险操作已被拦截。",
        func=execute_python, parameters=CODE_TOOL_SCHEMAS["execute_python"]["parameters"],
    ))
    mcp_manager.register(MCPTool(
        name="install_package", description="安装 Python 包（仅限白名单内的数据科学/Web 框架常用包）",
        func=install_package, parameters=CODE_TOOL_SCHEMAS["install_package"]["parameters"],
    ))

    mcp_manager.register(MCPTool(
        name="search_internet", description="使用 DuckDuckGo 联网搜索最新信息（免费无需 API Key），返回标题+链接+摘要",
        func=search_internet, parameters=SEARCH_TOOL_SCHEMAS["search_internet"]["parameters"],
    ))
    mcp_manager.register(MCPTool(
        name="fetch_weather", description="查询指定城市的实时天气信息（温度/天气/湿度/风速）",
        func=fetch_weather, parameters=SEARCH_TOOL_SCHEMAS["fetch_weather"]["parameters"],
    ))

    logger.info(f"MCP 已注册 {len(mcp_manager._tools)} 个工具: {mcp_manager.get_tool_names()}")
