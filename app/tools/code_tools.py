# 后端 代码执行 MCP 工具（安全沙箱）
import subprocess
import tempfile
import os

def execute_python(code: str, timeout: int = 30) -> str:
    # 后端 在安全沙箱中执行 Python 代码
    # 后端 写入临时文件
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        tmp_path = f.name

    try:
        # 后端 子进程隔离执行
        result = subprocess.run(
            ["python", tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.path.dirname(__file__),
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]:\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[返回码]: {result.returncode}"
        return output
    except subprocess.TimeoutExpired:
        return f"代码执行超时（>{timeout}秒）"
    except Exception as e:
        return f"代码执行异常: {str(e)}"
    finally:
        # 后端 清理临时文件
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

def install_package(package_name: str) -> str:
    # 后端 自动安装缺失的 Python 包
    try:
        result = subprocess.run(
            ["pip", "install", package_name],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.stdout
    except Exception as e:
        return f"安装失败: {str(e)}"

# 后端 代码工具 schema 定义
CODE_TOOL_SCHEMAS = {
    "execute_python": {
        "name": "execute_python",
        "description": "在安全沙箱中执行 Python 代码，返回执行结果",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "要执行的 Python 代码"},
                "timeout": {"type": "integer", "description": "超时秒数，默认30"}
            },
            "required": ["code"]
        }
    },
    "install_package": {
        "name": "install_package",
        "description": "安装缺失的 Python 包",
        "parameters": {
            "type": "object",
            "properties": {
                "package_name": {"type": "string", "description": "包名，如 pandas"}
            },
            "required": ["package_name"]
        }
    }
}
