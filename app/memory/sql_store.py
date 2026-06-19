# 后端 SQLite 结构化记忆 — 会话与任务历史持久化
import sqlite3
import json
from datetime import datetime
from ..core.config import settings

class SQLMemory:
    # 后端 会话与任务历史管理
    def __init__(self):
        self.db_path = settings.sqlite_db_path
        self._init_tables()

    def _init_tables(self) -> None:
        # 后端 初始化数据表
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                thread_id TEXT PRIMARY KEY,
                title TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                task_count INTEGER DEFAULT 0
            )
        """)
        # 后端 兼容旧表（无 title 列时自动添加）
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN title TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_history (
                task_id TEXT PRIMARY KEY,
                thread_id TEXT,
                user_input TEXT,
                subtasks_json TEXT,
                final_output TEXT,
                status TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (thread_id) REFERENCES sessions(thread_id)
            )
        """)
        conn.commit()
        conn.close()

    def create_session(self, thread_id: str, title: str = "") -> None:
        # 后端 创建新会话
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT OR IGNORE INTO sessions (thread_id, title) VALUES (?, ?)",
            (thread_id, title or thread_id[:20])
        )
        conn.commit()
        conn.close()

    def update_title(self, thread_id: str, title: str) -> None:
        # 后端 更新会话标题（取前20字）
        conn = sqlite3.connect(self.db_path)
        short_title = title[:20] if len(title) > 20 else title
        conn.execute(
            "UPDATE sessions SET title = ? WHERE thread_id = ? AND (title = '' OR title = thread_id)",
            (short_title, thread_id)
        )
        conn.commit()
        conn.close()

    def save_task(self, task_id: str, thread_id: str, user_input: str,
                  subtasks: list, final_output: str, status: str) -> None:
        # 后端 保存任务执行记录
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO task_history (task_id, thread_id, user_input, subtasks_json, final_output, status) VALUES (?, ?, ?, ?, ?, ?)",
            (task_id, thread_id, user_input, json.dumps(subtasks, ensure_ascii=False), final_output, status)
        )
        conn.execute(
            "UPDATE sessions SET updated_at = datetime('now'), task_count = task_count + 1 WHERE thread_id = ?",
            (thread_id,)
        )
        conn.commit()
        conn.close()

    def get_history(self, thread_id: str) -> list[dict]:
        # 后端 获取会话历史
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT task_id, user_input, final_output, status, created_at FROM task_history WHERE thread_id = ? ORDER BY created_at DESC LIMIT 20",
            (thread_id,)
        ).fetchall()
        conn.close()
        return [
            {"task_id": r[0], "user_input": r[1], "final_output": r[2], "status": r[3], "created_at": r[4]}
            for r in rows
        ]

# 后端 全局单例
sql_memory = SQLMemory()
