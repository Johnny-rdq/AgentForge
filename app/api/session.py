# 后端 会话管理 API
from fastapi import APIRouter
from ..memory.sql_store import sql_memory

router = APIRouter(prefix="/api/v1", tags=["sessions"])

@router.get("/sessions")
async def list_sessions():
    # 后端 获取会话列表
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
    return {"id": thread_id, "status": "created"}

@router.get("/sessions/{thread_id}/messages")
async def get_messages(thread_id: str):
    # 后端 获取会话消息历史
    history = sql_memory.get_history(thread_id)
    messages = []
    for h in history:
        messages.append({"id": h["task_id"], "role": "user", "content": h["user_input"]})
        if h["final_output"]:
            messages.append({"id": h["task_id"] + "_ai", "role": "assistant", "content": h["final_output"]})
    return {"messages": messages}

@router.delete("/sessions/{thread_id}")
async def delete_session(thread_id: str):
    # 后端 删除会话
    import sqlite3
    conn = sqlite3.connect(sql_memory.db_path)
    conn.execute("DELETE FROM task_history WHERE thread_id = ?", (thread_id,))
    conn.execute("DELETE FROM sessions WHERE thread_id = ?", (thread_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}
