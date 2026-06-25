# 后端 会话上下文 — 用 contextvars 在线程/协程间透明传递 thread_id
# 后端 优势：MCP 工具函数无需修改参数签名，LLM 无感知，自动隔离
import contextvars

# 后端 ContextVar：默认 "default_session"，在 nodes.py 中由 run_one() 设置
_current_thread_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_thread_id", default="default_session"
)


def set_current_thread_id(thread_id: str) -> None:
    """后端 设置当前线程/协程的会话 ID（由 nodes.py 在 Worker 执行前调用）"""
    _current_thread_id.set(thread_id)


def get_current_thread_id() -> str:
    """后端 获取当前线程/协程的会话 ID（工具函数内部调用，获取隔离目录）"""
    return _current_thread_id.get()
