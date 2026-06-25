# 后端 AgentForge Docker 镜像 — D 盘部署版（DaoCloud + 清华 + HF 镜像加速）
FROM docker.m.daocloud.io/library/python:3.12-slim

WORKDIR /app

# 后端 先复制依赖文件，利用 Docker 层缓存加速构建
COPY requirements.txt ./

# 后端 pip 安装依赖（清华镜像加速）
RUN pip install --no-cache-dir \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    -r requirements.txt

# 后端 复制全部源码（含前端 dist 和 ONNX 模型缓存）
COPY . .

# 后端 把 ONNX 模型放到 ChromaDB 期望的路径（镜像内置，运行时零等待）
RUN mkdir -p /root/.cache/chroma/onnx_models && \
    cp -r /app/docker_onnx_cache/all-MiniLM-L6-v2 /root/.cache/chroma/onnx_models/ && \
    rm -rf /app/docker_onnx_cache

# 后端 创建运行时数据目录
RUN mkdir -p /app/data/uploads /app/logs /app/data/generated

EXPOSE 7860

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
