# 后端 Milvus 向量记忆 — 语义搜索历史任务，辅助 Master 拆解
import numpy as np
from pymilvus import MilvusClient, CollectionSchema, FieldSchema, DataType
from pymilvus.milvus_client.index import IndexParams  # 后端 pymilvus 2.5+ 索引参数对象
from app.core.config import settings
from app.core.logger import get_logger
import dashscope
from dashscope import TextEmbedding
import os
import json

logger = get_logger(__name__)


class VectorMemory:
    """后端 Agent 语义记忆管理器（Milvus 向量数据库）

    Master 拆解任务前搜索历史相似任务，参考成功策略
    使用 DashScope embedding，Milvus 做向量存储和检索，查询时用余弦相似度排序
    """

    def __init__(self):
        # 后端 检查是否启用 Milvus
        self.use_local = False
        self.local_file = settings.vector_db_path

        if os.environ.get("SKIP_MILVUS", "false").lower() == "true":
            logger.info("跳过 Milvus 连接，使用本地存储")
            os.makedirs(os.path.dirname(self.local_file), exist_ok=True)
            return

        try:
            # 后端 连接到 Milvus（优先 Zilliz Cloud，其次本地 Docker）
            if settings.milvus_uri and settings.milvus_token:
                # 后端 Zilliz Cloud 托管模式（推荐，无需 Docker）
                self.client = MilvusClient(
                    uri=settings.milvus_uri,
                    token=settings.milvus_token,
                    timeout=30
                )
                logger.info(f"已连接到 Zilliz Cloud: {settings.milvus_uri}")
            else:
                # 后端 本地 Docker Milvus
                self.client = MilvusClient(
                    uri=f"http://{settings.milvus_host}:{settings.milvus_port}",
                    timeout=30
                )
                logger.info(f"已连接到 Milvus: {settings.milvus_host}:{settings.milvus_port}")
        except Exception as e:
            logger.warning(f"无法连接到 Milvus: {e}，将使用本地存储")
            self.use_local = True
            os.makedirs(os.path.dirname(self.local_file), exist_ok=True)
            return  # 后端 连接失败则跳过后续 Milvus 操作，直接使用本地存储

        # 后端 检查集合是否存在，不存在则创建
        collection_name = "agent_memory"
        if not self.client.has_collection(collection_name):
            # 后端 定义字段结构
            schema = CollectionSchema(
                fields=[
                    FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=256, is_primary=True),
                    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                    FieldSchema(name="thread_id", dtype=DataType.VARCHAR, max_length=256),
                    FieldSchema(name="metadata", dtype=DataType.JSON),
                    FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=1536)  # DashScope embedding 维度
                ],
                description="Agent 语义记忆"
            )

            # 后端 创建集合
            self.client.create_collection(collection_name, schema=schema)

            # 后端 创建索引（pymilvus 2.5+ 使用 IndexParams 对象）
            index_params = IndexParams()
            index_params.add_index(
                field_name="vector", index_type="HNSW",
                metric_type="IP", M=8, ef_construction=64
            )  # 后端 内积度量，归一化后等同于余弦相似度
            self.client.create_index(collection_name=collection_name, index_params=index_params)
            # 后端 加载集合到内存，否则无法搜索
            self.client.load_collection(collection_name)
            logger.info("Milvus 向量记忆集合已创建")
        else:
            logger.info("Milvus 向量记忆已初始化")

    def store(self, task_id: str, content: str, metadata: dict = None) -> None:
        """后端 存储任务上下文（手动向量化），metadata 含 thread_id 用于会话隔离"""
        meta = metadata or {}

        # 后端 调用 DashScope embedding API 生成向量
        try:
            response = TextEmbedding.call(
                model='text-embedding-v1',
                input=[content]
            )
            vector = response['output']['embeddings'][0]['embedding']  # 后端 取 embedding 向量 1536维
        except Exception as e:
            logger.error(f"生成 embedding 失败: {e}")
            # 后端 失败时使用零向量
            vector = np.zeros(1536).tolist()

        data = {
            "id": task_id,
            "content": content,
            "thread_id": meta.get("thread_id", ""),
            "metadata": json.dumps(meta, ensure_ascii=False) if meta else "{}",
            "vector": vector
        }

        if self.use_local:
            # 后端 本地文件存储
            try:
                # 读取现有数据
                if os.path.exists(self.local_file):
                    with open(self.local_file, 'r', encoding='utf-8') as f:
                        memories = json.load(f)
                else:
                    memories = []

                # 添加新记忆
                memories.append(data)

                # 保存到文件
                with open(self.local_file, 'w', encoding='utf-8') as f:
                    json.dump(memories, f, ensure_ascii=False, indent=2)

                logger.debug(f"本地向量记忆已存储: {task_id}")
            except Exception as e:
                logger.error(f"本地存储失败: {e}")
        else:
            self.client.insert(collection_name="agent_memory", data=[data])
            logger.debug(f"向量记忆已存储: {task_id}")

    def search(self, query: str, k: int = 5, thread_id: str = "") -> list[str]:
        """后端 语义搜索最相关的 k 个历史任务，仅搜索指定 thread_id 的会话"""
        # 后端 调用 DashScope embedding API 生成查询向量
        try:
            response = TextEmbedding.call(
                model='text-embedding-v1',
                input=[query]
            )
            query_vector = response['output']['embeddings'][0]['embedding']  # 后端 取 embedding 向量 1536维
        except Exception as e:
            logger.error(f"生成查询 embedding 失败: {e}")
            # 后端 失败时使用空列表
            return []

        # 后端 构建搜索条件
        search_params = {
            "metric_type": "IP",
            "params": {"ef": 16}
        }

        # 后端 构建过滤条件
        expr = f'thread_id == "{thread_id}"' if thread_id else None

        if self.use_local:
            # 后端 本地文件搜索
            try:
                if not os.path.exists(self.local_file):
                    return []

                with open(self.local_file, 'r', encoding='utf-8') as f:
                    memories = json.load(f)

                # 简单的关键词匹配（因为没有向量计算）
                filtered = []
                for mem in memories:
                    if thread_id and mem.get("thread_id") != thread_id:
                        continue
                    # 检查查询内容是否在记忆中
                    query_lower = query.lower()
                    content = mem.get("content", "").lower()
                    if query_lower in content:
                        filtered.append(mem.get("content"))

                # 返回前 k 个结果
                return filtered[:k]
            except Exception as e:
                logger.error(f"本地搜索失败: {e}")
                return []
        else:
            results = self.client.search(
                collection_name="agent_memory",
                data=[query_vector],
                anns_field="vector",
                search_params=search_params,  # 后端 MilvusClient 参数名
                limit=k,
                filter=expr,  # 后端 MilvusClient 用 filter 而非 expr
                output_fields=["content"]
            )
            return [hit["entity"]["content"] for hit in results[0]]

    def clear(self) -> None:
        """后端 清空所有向量记忆"""
        if self.use_local:
            # 后端 清空本地文件
            try:
                with open(self.local_file, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
                logger.info("本地向量记忆已清空")
            except Exception as e:
                logger.error(f"清空本地存储失败: {e}")
        else:
            # 后端 删除集合再重建
            self.client.drop_collection("agent_memory")

            # 重新创建集合和索引
            schema = CollectionSchema(
                fields=[
                    FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=256, is_primary=True),
                    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                    FieldSchema(name="thread_id", dtype=DataType.VARCHAR, max_length=256),
                    FieldSchema(name="metadata", dtype=DataType.JSON),
                    FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=1536)
                ],
                description="Agent 语义记忆"
            )
            self.client.create_collection("agent_memory", schema=schema)

            index_params = IndexParams()
            index_params.add_index(
                field_name="vector", index_type="HNSW",
                metric_type="IP", M=8, ef_construction=64
            )  # 后端 内积度量，归一化后等同于余弦相似度
            self.client.create_index("agent_memory", index_params)
            # 后端 重新加载集合到内存
            self.client.load_collection("agent_memory")

            logger.info("向量记忆已清空")


# 后端 延迟初始化，避免启动时强制连接
_vector_memory_instance = None

def get_vector_memory():
    """后端 获取向量记忆实例，延迟初始化"""
    global _vector_memory_instance
    if _vector_memory_instance is None:
        _vector_memory_instance = VectorMemory()
    return _vector_memory_instance