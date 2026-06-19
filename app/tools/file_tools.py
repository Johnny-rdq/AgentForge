# 后端 文件操作 MCP 工具
import os
import json

def read_file(file_path: str) -> str:
    # 后端 读取文件内容
    if not os.path.exists(file_path):
        return f"文件不存在: {file_path}"
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    return content[:5000]  # 后端 限制读取长度

def write_file(file_path: str, content: str) -> str:
    # 后端 写入文件
    base_dir = os.path.join(os.path.dirname(__file__), "..", "..", "completed_tasks")
    full_path = os.path.join(base_dir, os.path.basename(file_path))
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"文件已保存: {full_path}"

def list_files(directory: str = ".") -> str:
    # 后端 列出目录文件
    try:
        files = os.listdir(directory)
        return json.dumps(files, ensure_ascii=False)
    except Exception as e:
        return f"列出目录失败: {str(e)}"

# 后端 文件工具 schema 定义
FILE_TOOL_SCHEMAS = {
    "read_file": {
        "name": "read_file",
        "description": "读取指定文件的内容",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件路径"}
            },
            "required": ["file_path"]
        }
    },
    "write_file": {
        "name": "write_file",
        "description": "将内容写入文件",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件名"},
                "content": {"type": "string", "description": "要写入的内容"}
            },
            "required": ["file_path", "content"]
        }
    }
}
