# 后端 ChromaDB 向量记忆 — 语义搜索历史任务，辅助 Master 拆解
import chromadb
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class VectorMemory:
    """后端 Agent 语义记忆管理器（ChromaDB 持久化向量数据库）

    Master 拆解任务前搜索历史相似任务，参考成功策略
    存储时 ChromaDB 自动做 embedding，查询时用余弦相似度排序
    """

    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="agent_memory",
            metadata={"hnsw:space": "cosine"},  # 后端 余弦距离做语义相似度
        )
        logger.info("ChromaDB 向量记忆已初始化")

    def store(self, task_id: str, content: str, metadata: dict = None) -> None:
        """后端 存储任务上下文（自动向量化）"""
        self.collection.add(documents=[content], metadatas=[metadata or {}], ids=[task_id])
        logger.debug(f"向量记忆已存储: {task_id}")

    def search(self, query: str, k: int = 5) -> list[str]:
        """后端 语义搜索最相关的 k 个历史任务"""
        results = self.collection.query(query_texts=[query], n_results=k)
        return results.get("documents", [[]])[0]

    def clear(self) -> None:
        """后端 清空所有向量记忆"""
        ids = self.collection.get()["ids"]
        if ids:
            self.collection.delete(ids=ids)
            logger.info(f"向量记忆已清空: {len(ids)} 条记录")


vector_memory = VectorMemory()
