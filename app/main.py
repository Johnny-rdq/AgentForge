# 后端 FastAPI 主入口
import os
import uvicorn
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from app.core.config import settings
from app.core.logger import app_logger
from app.api.chat import router as chat_router
from app.api.session import router as session_router
from app.api.benchmark_api import router as benchmark_router
from app.api.upload import router as upload_router
from app.tools.mcp_server import register_all_tools


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 后端 创建运行时目录（同步操作，快速完成）
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "data", "uploads"), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "data", "generated"), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "logs"), exist_ok=True)
    app_logger.info(f"AgentForge 启动: http://localhost:{settings.app_port}")

    # 后端 注册 MCP 工具（等待完成后再接受请求，避免工具未就绪）
    try:
        register_all_tools()
        app_logger.info("MCP 工具注册完成")
    except Exception as e:
        app_logger.error(f"MCP 工具注册失败: {e}")

    yield
    app_logger.info("AgentForge 关闭")


app = FastAPI(
    title="AgentForge - AI 智能助手",
    description="MCP 多Agent 自主任务系统 — 自然语言驱动，自动拆解→执行→交付",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """后端 健康检查端点"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(session_router)
app.include_router(benchmark_router)
app.include_router(upload_router)

# 后端 生成文件目录（根目录，向后兼容 + 会话隔离子目录）
generated_dir = os.path.join(os.path.dirname(__file__), "..", "data", "generated")
os.makedirs(generated_dir, exist_ok=True)

# 后端 自定义路由：支持两种路径格式
# 后端   1. /generated/{thread_id}/filename.png → data/generated/{thread_id}/filename.png（会话隔离）
# 后端   2. /generated/filename.png → data/generated/filename.png（向后兼容旧数据）
@app.get("/generated/{file_path:path}")
async def serve_generated(file_path: str):
    full_path = os.path.join(generated_dir, file_path)
    # 后端 安全检查：确保路径在 generated_dir 内，防止路径穿越
    real_path = os.path.realpath(full_path)
    if not real_path.startswith(os.path.realpath(generated_dir)):
        raise HTTPException(status_code=404, detail="文件未找到")
    if not os.path.isfile(real_path):
        raise HTTPException(status_code=404, detail="文件未找到")
    return FileResponse(real_path)

# 后端 生产模式下挂载前端 SPA 静态文件
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    app_logger.info(f"前端已挂载: {frontend_dist}")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=True)
