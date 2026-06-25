# 后端 SQLite 结构化记忆 — 会话 + 任务历史持久化
import sqlite3
import json
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class SQLMemory:
    """后端 SQLite 会话与任务历史管理器

    表结构：
    - sessions: 会话元数据（ID、标题、时间、任务数）
    - task_history: 任务执行记录（输入、子任务JSON、输出、状态）
    """

    def __init__(self):
        self.db_path = settings.sqlite_db_path
        self._init_tables()

    def _init_tables(self) -> None:
        """后端 自动建表（已存在则跳过）"""
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
        # 后端 迁移兼容：为旧表补齐 title 列
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
                elapsed_ms INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (thread_id) REFERENCES sessions(thread_id)
            )
        """)
        # 后端 迁移：补齐 files_json 列
        try:
            conn.execute("ALTER TABLE task_history ADD COLUMN files_json TEXT DEFAULT '[]'")
        except sqlite3.OperationalError:
            pass
        # 后端 迁移：补齐 elapsed_ms 列
        try:
            conn.execute("ALTER TABLE task_history ADD COLUMN elapsed_ms INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        conn.commit()
        conn.close()
        logger.info("SQLite 数据库表已就绪")

    def create_session(self, thread_id: str, title: str = "") -> None:
        """后端 创建会话记录（INSERT OR IGNORE，重复 thread_id 不会报错也不会覆盖）"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT OR IGNORE INTO sessions (thread_id, title) VALUES (?, ?)", (thread_id, title or thread_id[:20]))
        conn.commit()
        conn.close()

    def update_title(self, thread_id: str, title: str) -> None:
        """后端 首条消息时设置会话标题（取前12字符），后续不再改"""
        conn = sqlite3.connect(self.db_path)
        short_title = title[:12] if len(title) > 12 else title
        short_title = short_title.replace("\n", " ").strip()  # 后端 去掉换行和多余空白
        # 后端 只在标题为空或默认值时才设置（首次消息），后续消息不改标题
        conn.execute(
            "UPDATE sessions SET title = ?, updated_at = datetime('now') WHERE thread_id = ? AND (title = '' OR title = '新会话' OR title LIKE 'session_%')",
            (short_title, thread_id)
        )
        conn.commit()
        conn.close()

    def save_task(self, task_id: str, thread_id: str, user_input: str,
                  subtasks: list, final_output: str, status: str,
                  files_json: str = "[]", elapsed_ms: int = 0) -> None:
        """后端 保存任务记录 + 同步更新会话时间/计数"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO task_history (task_id, thread_id, user_input, subtasks_json, final_output, status, files_json, elapsed_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (task_id, thread_id, user_input, json.dumps(subtasks, ensure_ascii=False), final_output, status, files_json, elapsed_ms)
        )
        conn.execute("UPDATE sessions SET updated_at = datetime('now'), task_count = task_count + 1 WHERE thread_id = ?", (thread_id,))
        conn.commit()
        conn.close()
        logger.debug(f"任务已保存: {task_id} → {thread_id} ({elapsed_ms}ms)")

    def get_history(self, thread_id: str) -> list[dict]:
        """后端 查询会话最近 20 条历史任务（含文件元数据）"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT task_id, user_input, final_output, status, created_at, files_json, elapsed_ms FROM task_history WHERE thread_id = ? ORDER BY created_at ASC LIMIT 20",
            (thread_id,)
        ).fetchall()
        conn.close()
        return [{"task_id": r[0], "user_input": r[1], "final_output": r[2], "status": r[3], "created_at": r[4], "files_json": r[5] or "[]", "elapsed_ms": r[6] or 0} for r in rows]


sql_memory = SQLMemory()
