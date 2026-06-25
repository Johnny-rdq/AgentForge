# 后端 会话管理 API — 会话和消息历史的 CRUD
import json
from fastapi import APIRouter
from app.core.logger import get_logger
from app.memory.sql_store import sql_memory

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["sessions"])


@router.get("/sessions")
async def list_sessions():
    """后端 列出所有会话，按最近更新时间降序（前端侧边栏用）"""
    # 后端 直接查 SQLite：sql_memory 没有 list 方法，且这里只需 4 个字段，没必要加封装
    import sqlite3
    conn = sqlite3.connect(sql_memory.db_path)
    rows = conn.execute(
        "SELECT thread_id, title, created_at, task_count FROM sessions ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return {
        "sessions": [
            {"id": r[0], "title": r[1] or r[0][:20], "createdAt": r[2], "taskCount": r[3]}
            for r in rows
        ]
    }


@router.post("/sessions")
async def create_session(data: dict):
    """后端 创建新会话：前端传 thread_id 和 title，后端 INSERT OR IGNORE（幂等）"""
    thread_id = data.get("thread_id", f"session_{data.get('timestamp', '')}")
    title = data.get("title", thread_id[:30])
    sql_memory.create_session(thread_id, title)
    logger.info(f"会话已创建: {thread_id}")
    return {"id": thread_id, "status": "created"}


@router.get("/sessions/{thread_id}/messages")
async def get_messages(thread_id: str):
    """后端 获取会话历史消息，返回 user/assistant 配对列表（前端刷新后恢复对话）"""
    history = sql_memory.get_history(thread_id)
    messages = []
    for h in history:
        # 后端 每次任务记录是一条 user → assistant 对
        files_data = []
        try:
            files_data = json.loads(h.get("files_json", "[]"))
        except Exception:
            pass
        messages.append({
            "id": h["task_id"], "role": "user",
            "content": h["user_input"], "files": files_data
        })
        if h["final_output"]:
            messages.append({
                "id": h["task_id"] + "_ai", "role": "assistant",
                "content": h["final_output"],
                "elapsed_ms": h.get("elapsed_ms", 0),
            })
    return {"messages": messages}


@router.delete("/sessions/{thread_id}")
async def delete_session(thread_id: str):
    """后端 删除会话及其所有关联任务历史（级联删除）"""
    # 后端 sql_memory 没有封装级联删除，直接操作 SQLite 更简洁
    import sqlite3
    conn = sqlite3.connect(sql_memory.db_path)
    conn.execute("DELETE FROM task_history WHERE thread_id = ?", (thread_id,))
    conn.execute("DELETE FROM sessions WHERE thread_id = ?", (thread_id,))
    conn.commit()
    conn.close()
    logger.info(f"会话已删除: {thread_id}")
    return {"status": "deleted"}
