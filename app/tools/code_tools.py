# 后端 代码执行工具 — AST 安全沙箱 + 子进程隔离执行
import ast
import subprocess
import tempfile
import os
import sys
from app.core.logger import get_logger
from app.core.config import settings

logger = get_logger(__name__)

# 后端 (模块, 函数) 危险调用黑名单 — AST 扫描时拦截
_DANGEROUS_CALLS = {
    ("os", "system"), ("os", "popen"),
    ("subprocess", "run"), ("subprocess", "Popen"), ("subprocess", "call"), ("subprocess", "check_output"),
    ("sys", "exit"),
    ("builtins", "eval"), ("builtins", "exec"), ("builtins", "__import__"),
    ("shutil", "rmtree"), ("shutil", "move"),
}

# 后端 pip install 白名单 — 只允许安装常见数据科学/Web 包
_ALLOWED_PACKAGES = {
    "numpy", "pandas", "matplotlib", "scipy", "scikit-learn",
    "requests", "beautifulsoup4", "lxml", "pillow", "openpyxl",
    "seaborn", "plotly", "jupyter", "ipython", "sympy", "statsmodels",
    "flask", "fastapi", "pydantic", "sqlalchemy", "redis", "pymongo",
}


def _check_code_safety(code: str) -> tuple[bool, str]:
    """后端 AST 静态扫描：遍历语法树，拦截危险模块导入和函数调用"""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"代码语法错误: {str(e)}"

    forbidden_imports = {"os", "subprocess", "shutil", "ctypes", "socket"}

    for node in ast.walk(tree):
        # 拦截 import os / import subprocess 等
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in forbidden_imports:
                    return False, f"安全拦截：禁止导入模块 '{alias.name}'"

        # 拦截 from os import system 等
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in forbidden_imports:
                return False, f"安全拦截：禁止从 '{node.module}' 导入"

        # 拦截函数调用
        if isinstance(node, ast.Call):
            # 裸调 eval/exec/compile/__import__
            if isinstance(node.func, ast.Name):
                if node.func.id in ("eval", "exec", "__import__", "compile"):
                    return False, f"安全拦截：禁止调用 '{node.func.id}'"

            # 模块.函数调用（如 os.system / subprocess.run）
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    if (node.func.value.id, node.func.attr) in _DANGEROUS_CALLS:
                        return False, f"安全拦截：禁止调用 '{node.func.value.id}.{node.func.attr}'"

    return True, ""


def execute_python(code: str, timeout: int = None) -> str:
    """后端 在隔离子进程中执行用户 Python 代码"""
    if timeout is None:
        timeout = settings.mcp_tool_timeout
    # AST 安全检查
    safe, error_msg = _check_code_safety(code)
    if not safe:
        logger.warning(f"代码被安全拦截: {error_msg[:100]}")
        return f"[安全拦截] {error_msg}"

    # 后端 工作目录：data/generated/（图表等产出物可通过 /generated/ 访问）
    gen_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "generated")
    os.makedirs(gen_dir, exist_ok=True)

    # 写入临时文件
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        tmp_path = f.name

    try:
        # 子进程隔离执行（独立进程，超时自动杀死）
        result = subprocess.run(
            [sys.executable, tmp_path],  # 后端 用当前 Python 解释器，确保包一致
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",  # 后端 强制 UTF-8，避免 Windows GBK 乱码
            timeout=timeout,
            cwd=gen_dir,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]:\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[返回码]: {result.returncode}"

        logger.info(f"代码执行完成，返回码: {result.returncode}")
        return output

    except subprocess.TimeoutExpired:
        logger.warning(f"代码执行超时（>{timeout}秒）")
        return f"代码执行超时（>{timeout}秒）"
    except Exception as e:
        logger.error(f"代码执行异常: {str(e)[:100]}")
        return f"代码执行异常: {str(e)}"
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def install_package(package_name: str) -> str:
    """后端 安装 Python 包（仅白名单内的包）"""
    if package_name.lower() not in _ALLOWED_PACKAGES:
        logger.warning(f"包安装被拒绝（不在白名单）: {package_name}")
        return f"安全拦截：包 '{package_name}' 不在白名单中。可安装: {', '.join(sorted(_ALLOWED_PACKAGES))}"

    try:
        logger.info(f"安装 Python 包: {package_name}")
        result = subprocess.run(
            ["pip", "install", package_name],
            capture_output=True, text=True, timeout=120,
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        return f"安装超时（>120秒）: {package_name}"
    except Exception as e:
        return f"安装失败: {str(e)}"


CODE_TOOL_SCHEMAS = {
    "execute_python": {
        "name": "execute_python",
        "description": "在安全沙箱中执行 Python 代码并返回结果，超时 30 秒。禁止危险操作。",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "要执行的 Python 代码"},
                "timeout": {"type": "integer", "description": "超时秒数，默认 30"}
            },
            "required": ["code"]
        }
    },
    "install_package": {
        "name": "install_package",
        "description": "安装 Python 包（仅限白名单内的数据科学/Web 框架包）",
        "parameters": {
            "type": "object",
            "properties": {
                "package_name": {"type": "string", "description": "包名，如 pandas、numpy"}
            },
            "required": ["package_name"]
        }
    }
}
