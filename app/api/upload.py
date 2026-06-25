# 后端 文件上传 API — 接收用户上传文件供 Agent 分析
import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.core.logger import get_logger
from app.core.session_context import get_current_thread_id
from app.models.schemas import FileUploadResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["upload"])

# 后端 上传根目录：项目根目录下的 data/uploads/
_UPLOAD_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "uploads"))


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """后端 接收用户上传文件，存入 data/uploads/{thread_id}/ 子目录（会话隔离）"""
    thread_id = get_current_thread_id()
    safe_name = os.path.basename(file.filename or "unnamed")
    upload_dir = os.path.join(_UPLOAD_ROOT, thread_id)
    os.makedirs(upload_dir, exist_ok=True)

    # 后端 归一化绝对路径（消除 ..），确保 Agent 用 read_file 时能正确定位
    save_path = os.path.join(upload_dir, safe_name)
    content = await file.read()

    with open(save_path, "wb") as f:
        f.write(content)

    logger.info(f"文件已上传: {safe_name} → {save_path} ({len(content)} bytes)")
    return FileUploadResponse(
        filename=safe_name,
        saved_path=save_path,
        size_bytes=len(content),
    )
