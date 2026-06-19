# 后端 FastAPI 主入口 — AgentForge 多Agent自主任务系统
import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .core.config import settings
from .api.chat import router as chat_router
from .api.session import router as session_router
from .api.benchmark_api import router as benchmark_router
from .tools.mcp_server import register_all_tools

@asynccontextmanager
async def lifespan(app: FastAPI):
    register_all_tools()
    print(f"[AgentForge] 启动: http://{settings.app_host}:{settings.app_port}")
    yield

app = FastAPI(
    title="AgentForge - 多Agent自主任务系统",
    description="动态Agent生成 + MCP工具协议 + 依赖感知并行调度 + 自反思修正",
    version="1.0.0",
    lifespan=lifespan,
)

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

# 后端 挂载前端静态文件
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    print(f"[AgentForge] 前端已挂载: {frontend_dist}")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )
