# 后端 AgentForge Docker 镜像 — 多阶段构建
FROM python:3.12-slim

WORKDIR /app

# 后端 先复制依赖文件，利用 Docker 层缓存加速构建
COPY requirements.txt ./

# 后端 pip 安装依赖（清华镜像加速）
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 后端 复制全部源码（含前端 dist）
COPY . .

# 后端 创建运行时数据目录
RUN mkdir -p /app/data/uploads /app/logs

EXPOSE 7860

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
