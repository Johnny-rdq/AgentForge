# 后端 AgentForge Docker 镜像
FROM python:3.12-slim

WORKDIR /app

# 后端 安装 uv（比 pip 快 10-100 倍），清华镜像加速
RUN pip install uv --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple

# 后端 先复制依赖文件，利用 Docker 层缓存加速构建
COPY pyproject.toml ./

# 后端 依赖安装（uv 优先，失败回退到 pip）
RUN uv pip install --system -r pyproject.toml 2>/dev/null || \
    pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
    fastapi uvicorn[standard] openai pydantic-settings langgraph langchain-core \
    chromadb==0.5.23 sse-starlette duckduckgo-search

COPY . .

# 后端 创建运行时目录
RUN mkdir -p /app/data /app/logs

EXPOSE 7860

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
