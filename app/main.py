# 后端 FastAPI 主入口
import os
import uvicorn
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.logger import app_logger
from app.api.chat import router as chat_router
from app.api.session import router as session_router
from app.api.benchmark_api import router as benchmark_router
from app.api.upload import router as upload_router
from app.tools.mcp_server import register_all_tools


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 后端 启动时注册 MCP 工具，关闭时清理资源
    register_all_tools()
    app_logger.info(f"AgentForge 启动: http://localhost:{settings.app_port}")
    yield
    app_logger.info("AgentForge 关闭")


app = FastAPI(
    title="AgentForge - 多Agent自主任务系统",
    description="动态Agent生成 + MCP工具协议 + 依赖感知并行调度 + 自反思修正",
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

# 后端 生产模式下挂载前端 SPA 静态文件
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    app_logger.info(f"前端已挂载: {frontend_dist}")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=True)
