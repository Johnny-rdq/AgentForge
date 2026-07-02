# 后端 AgentForge Docker 镜像
FROM python:3.12-slim

WORKDIR /app

# 后端 先复制依赖文件，利用 Docker 层缓存加速构建
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 后端 复制全部源码
COPY . .

# 后端 创建运行时目录
RUN mkdir -p /app/data/uploads /app/logs /app/data/generated

EXPOSE 7860

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]