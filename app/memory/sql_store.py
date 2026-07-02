# 后端 PostgreSQL 结构化记忆 — 会话 + 任务历史持久化
import psycopg2
from psycopg2 import pool
import json
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class SQLMemory:
    """后端 PostgreSQL 会话与任务历史管理器

    表结构：
    - sessions: 会话元数据（ID、标题、时间、任务数）
    - task_history: 任务执行记录（输入、子任务JSON、输出、状态）
    """

    def __init__(self):
        self._pool = pool.SimpleConnectionPool(
            minconn=2,
            maxconn=10,
            host=settings.pg_host,
            port=settings.pg_port,
            dbname=settings.pg_database,
            user=settings.pg_user,
            password=settings.pg_password,
        )
        self._init_tables()

    def _get_conn(self):
        """后端 从连接池获取一个连接"""
        return self._pool.getconn()

    def _put_conn(self, conn):
        """后端 归还连接到连接池"""
        self._pool.putconn(conn)

    def _init_tables(self) -> None:
        """后端 自动建表（已存在则跳过），兼容增量迁移"""
        conn = self._get_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                thread_id TEXT PRIMARY KEY,
                title TEXT DEFAULT '',
                created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
                updated_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
                task_count INTEGER DEFAULT 0
            )
        """)
        # 后端 迁移兼容：为旧表补齐 title 列
        cur.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS title TEXT DEFAULT ''")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_history (
                task_id TEXT PRIMARY KEY,
                thread_id TEXT,
                user_input TEXT,
                subtasks_json TEXT,
                final_output TEXT,
                status TEXT,
                elapsed_ms INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
                FOREIGN KEY (thread_id) REFERENCES sessions(thread_id)
            )
        """)
        # 后端 迁移：补齐 files_json 列
        cur.execute("ALTER TABLE task_history ADD COLUMN IF NOT EXISTS files_json TEXT DEFAULT '[]'")
        # 后端 迁移：补齐 elapsed_ms 列
        cur.execute("ALTER TABLE task_history ADD COLUMN IF NOT EXISTS elapsed_ms INTEGER DEFAULT 0")
        cur.close()
        conn.autocommit = False  # 后端 归还前重置为手动提交模式
        self._put_conn(conn)
        logger.info("PostgreSQL 数据库表已就绪")

    def create_session(self, thread_id: str, title: str = "") -> None:
        """后端 创建会话记录（ON CONFLICT DO NOTHING，重复 thread_id 不会报错也不会覆盖）"""
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sessions (thread_id, title) VALUES (%s, %s) ON CONFLICT (thread_id) DO NOTHING",
                (thread_id, title or thread_id[:20])
            )
        conn.commit()
        self._put_conn(conn)

    def update_title(self, thread_id: str, title: str) -> None:
        """后端 首条消息时设置会话标题（取前12字符），后续不再改"""
        conn = self._get_conn()
        short_title = title[:12] if len(title) > 12 else title
        short_title = short_title.replace("\n", " ").strip()  # 后端 去掉换行和多余空白
        # 后端 只在标题为空或默认值时才设置（首次消息），后续消息不改标题
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sessions SET title = %s, updated_at = to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') "
                "WHERE thread_id = %s AND (title = '' OR title = '新会话' OR title LIKE 'session_%%')",
                (short_title, thread_id)
            )
        conn.commit()
        self._put_conn(conn)

    def save_task(self, task_id: str, thread_id: str, user_input: str,
                  subtasks: list, final_output: str, status: str,
                  files_json: str = "[]", elapsed_ms: int = 0) -> None:
        """后端 保存任务记录 + 同步更新会话时间/计数"""
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO task_history (task_id, thread_id, user_input, subtasks_json, final_output, status, files_json, elapsed_ms) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (task_id) DO UPDATE SET "
                "thread_id = EXCLUDED.thread_id, user_input = EXCLUDED.user_input, "
                "subtasks_json = EXCLUDED.subtasks_json, final_output = EXCLUDED.final_output, "
                "status = EXCLUDED.status, files_json = EXCLUDED.files_json, elapsed_ms = EXCLUDED.elapsed_ms",
                (task_id, thread_id, user_input, json.dumps(subtasks, ensure_ascii=False), final_output, status, files_json, elapsed_ms)
            )
            cur.execute(
                "UPDATE sessions SET updated_at = to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'), "
                "task_count = task_count + 1 WHERE thread_id = %s",
                (thread_id,)
            )
        conn.commit()
        self._put_conn(conn)
        logger.debug(f"任务已保存: {task_id} → {thread_id} ({elapsed_ms}ms)")

    def get_history(self, thread_id: str) -> list[dict]:
        """后端 查询会话最近 20 条历史任务（含文件元数据）"""
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT task_id, user_input, final_output, status, created_at, files_json, elapsed_ms "
                "FROM task_history WHERE thread_id = %s ORDER BY created_at ASC LIMIT 20",
                (thread_id,)
            )
            rows = cur.fetchall()
        self._put_conn(conn)
        return [{"task_id": r[0], "user_input": r[1], "final_output": r[2], "status": r[3], "created_at": r[4], "files_json": r[5] or "[]", "elapsed_ms": r[6] or 0} for r in rows]

    def list_sessions(self) -> list[dict]:
        """后端 列出所有会话，按最近更新时间降序（前端侧边栏用）"""
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT thread_id, title, created_at, task_count FROM sessions ORDER BY updated_at DESC"
            )
            rows = cur.fetchall()
        self._put_conn(conn)
        return [{"thread_id": r[0], "title": r[1], "created_at": r[2], "task_count": r[3]} for r in rows]

    def delete_session(self, thread_id: str) -> None:
        """后端 删除会话及其所有关联任务历史（级联删除）"""
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM task_history WHERE thread_id = %s", (thread_id,))
            cur.execute("DELETE FROM sessions WHERE thread_id = %s", (thread_id,))
        conn.commit()
        self._put_conn(conn)


sql_memory = SQLMemory()
