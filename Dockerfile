# 后端 Docker 多阶段构建 — AgentForge
FROM python:3.11-slim

WORKDIR /code

# 后端 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# 后端 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 后端 复制项目代码
COPY . .

# 后端 创建数据目录
RUN mkdir -p data completed_tasks

EXPOSE 7860

CMD ["python", "-m", "app.main"]
