# 后端 会话管理 API — 会话和消息历史的 CRUD
import json
from fastapi import APIRouter
from app.core.logger import get_logger
from app.memory.sql_store import sql_memory

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["sessions"])


@router.get("/sessions")
async def list_sessions():
    # 后端 按最近更新时间降序返回所有会话
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
    # 后端 创建新会话
    thread_id = data.get("thread_id", f"session_{data.get('timestamp', '')}")
    title = data.get("title", thread_id[:30])
    sql_memory.create_session(thread_id, title)
    logger.info(f"会话已创建: {thread_id}")
    return {"id": thread_id, "status": "created"}


@router.get("/sessions/{thread_id}/messages")
async def get_messages(thread_id: str):
    # 后端 获取会话的历史消息（页面刷新后恢复对话，含文件元数据）
    history = sql_memory.get_history(thread_id)
    messages = []
    for h in history:
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
    # 后端 删除会话及关联任务
    import sqlite3
    conn = sqlite3.connect(sql_memory.db_path)
    conn.execute("DELETE FROM task_history WHERE thread_id = ?", (thread_id,))
    conn.execute("DELETE FROM sessions WHERE thread_id = ?", (thread_id,))
    conn.commit()
    conn.close()
    logger.info(f"会话已删除: {thread_id}")
    return {"status": "deleted"}
