# 后端 文件上传 API — 接收用户上传文件供 Agent 分析
import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.core.logger import get_logger
from app.models.schemas import FileUploadResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["upload"])

# 后端 上传目录：项目根目录下的 data/uploads/（归一化去掉 ..）
_UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "uploads"))


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """后端 接收用户上传文件，存入 data/uploads/ 供 Agent 读取分析"""
    safe_name = os.path.basename(file.filename or "unnamed")
    os.makedirs(_UPLOAD_DIR, exist_ok=True)

    # 后端 归一化绝对路径（消除 ..），确保 Agent 用 read_file 时能正确定位
    save_path = os.path.join(_UPLOAD_DIR, safe_name)
    content = await file.read()

    with open(save_path, "wb") as f:
        f.write(content)

    logger.info(f"文件已上传: {safe_name} ({len(content)} bytes)")
    return FileUploadResponse(
        filename=safe_name,
        saved_path=save_path,
        size_bytes=len(content),
    )
