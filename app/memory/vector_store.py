# 后端 ChromaDB 向量记忆 — Agent 短期语义记忆
import chromadb
from ..core.config import settings

class VectorMemory:
    # 后端 Agent 语义记忆管理（基于 ChromaDB）
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
        )
        self.collection = self.client.get_or_create_collection(
            name="agent_memory",
            metadata={"hnsw:space": "cosine"},
        )

    def store(self, task_id: str, content: str, metadata: dict = None) -> None:
        # 后端 存储任务执行上下文
        self.collection.add(
            documents=[content],
            metadatas=[metadata or {}],
            ids=[task_id],
        )

    def search(self, query: str, k: int = 5) -> list[str]:
        # 后端 语义搜索相关历史任务
        results = self.collection.query(
            query_texts=[query],
            n_results=k,
        )
        return results.get("documents", [[]])[0]

    def clear(self) -> None:
        # 后端 清空记忆
        self.collection.delete(ids=self.collection.get()["ids"])

# 后端 全局单例
vector_memory = VectorMemory()
