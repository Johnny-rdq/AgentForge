# 后端 文件操作工具 — 读取/写入/目录浏览
import os
import json
import base64
import io
import time
from app.core.logger import get_logger
from app.core.config import settings

logger = get_logger(__name__)


def _ocr_pdf_pages(doc, page_count: int, max_pages: int = 3) -> str:
    """后端 腾讯云 OCR：对已打开的 PDF 逐页识别（只渲染→编码→API，无多余操作）"""
    if not settings.tencent_secret_id or not settings.tencent_secret_key:
        return ""

    try:
        from tencentcloud.common import credential
        from tencentcloud.ocr.v20181119 import ocr_client, models

        cred = credential.Credential(settings.tencent_secret_id, settings.tencent_secret_key)
        client = ocr_client.OcrClient(cred, "ap-guangzhou")

        text_parts = []
        pages_to_ocr = min(page_count, max_pages)

        for i in range(pages_to_ocr):
            page = doc[i]
            t0 = time.time()
            # 后端 120 DPI 足够 OCR 识别，比 150/200 快
            pix = page.get_pixmap(dpi=120)
            img_bytes = pix.tobytes("png")
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")
            t1 = time.time()
            logger.debug(f"  第{i+1}页 渲染+编码 {(t1-t0)*1000:.0f}ms, 图片 {len(img_bytes)//1024}KB")

            req = models.GeneralBasicOCRRequest()
            req.ImageBase64 = img_base64
            resp = client.GeneralBasicOCR(req)
            t2 = time.time()
            logger.debug(f"  第{i+1}页 API 调用 {(t2-t1)*1000:.0f}ms")

            page_text_parts = []
            for item in resp.TextDetections:
                page_text_parts.append(item.DetectedText)
            if page_text_parts:
                text_parts.append(f"--- 第{i+1}页 ---\n" + "\n".join(page_text_parts))

        return "\n\n".join(text_parts)

    except Exception as e:
        logger.warning(f"腾讯云 OCR 失败: {str(e)[:100]}")
        return ""


def read_file(file_path: str) -> str:
    """后端 读取文件内容（PDF 智能策略，限制 5000 字）"""
    if not os.path.exists(file_path):
        return f"文件不存在: {file_path}"

    ext = os.path.splitext(file_path)[1].lower()

    # 后端 PDF：打开一次，先秒提文字，不够才 OCR
    if ext == ".pdf":
        t_start = time.time()
        try:
            import fitz
            doc = fitz.open(file_path)
            page_count = len(doc)

            # 后端 秒提文字（一次遍历，不重复打开）
            text_parts = []
            for page in doc:
                t = page.get_text()
                if t and t.strip():
                    text_parts.append(t.strip())
            fitz_text = "\n".join(text_parts)
            t_extract = time.time()
            logger.info(f"📄 PDF {os.path.basename(file_path)}: PyMuPDF {(t_extract-t_start)*1000:.0f}ms, {len(fitz_text)}字/{page_count}页")

            # 后端 文字≥100字 且 平均每页≥50字 → 直接返回（秒级）
            if fitz_text.strip() and len(fitz_text) >= 100 and (len(fitz_text) / max(page_count, 1)) >= 50:
                doc.close()
                logger.info(f"   ✅ 文字型 PDF，直接返回 ({len(fitz_text[:5000])}字)")
                return fitz_text[:5000]

            # 后端 图片型 PDF → OCR
            reason = "无文字" if not fitz_text.strip() else f"仅{len(fitz_text)}字"
            logger.info(f"   🔍 {reason}，启用 OCR（最多{min(page_count, 3)}页）")
            ocr_text = _ocr_pdf_pages(doc, page_count, max_pages=3)
            doc.close()
            t_total = time.time()

            if ocr_text.strip():
                logger.info(f"   ✅ OCR 完成 总耗时{(t_total-t_start)*1000:.0f}ms, {len(ocr_text)}字")
                return ocr_text[:5000]

            # 后端 OCR 也空 → PyMuPDF 残量兜底
            if fitz_text.strip():
                return fitz_text[:5000]
            return "⚠️ 无法从该 PDF 提取文字（文字提取和 OCR 均失败）。你必须如实告知用户此文件无法解析，严禁编造任何内容。"
        except Exception as e:
            logger.warning(f"PDF 解析失败: {file_path} - {str(e)[:100]}")
            return f"PDF 解析失败: {str(e)[:200]}"

    # 后端 .docx 用 python-docx 提取文字
    if ext == ".docx":
        try:
            from docx import Document
            doc = Document(file_path)
            content = "\n".join(p.text for p in doc.paragraphs)
            logger.debug(f"DOCX 已解析: {file_path} ({len(content)} 字)")
            return content[:5000] if content else "DOCX 文件内容为空"
        except Exception as e:
            logger.warning(f"DOCX 解析失败: {file_path} - {e}")
            return f"DOCX 解析失败: {str(e)}"

    # 后端 普通文本文件
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    logger.debug(f"文件已读取: {file_path} ({len(content)} 字)")
    return content[:5000]


def write_file(file_path: str, content: str) -> str:
    """后端 写入文件到 completed_tasks 目录（仅取 basename 防路径穿越）"""
    base_dir = os.path.join(os.path.dirname(__file__), "..", "..", "completed_tasks")
    full_path = os.path.join(base_dir, os.path.basename(file_path))
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"文件已保存: {full_path}")
    return f"文件已保存: {full_path}"


def list_files(directory: str = ".") -> str:
    """后端 列出目录内容，返回 JSON"""
    try:
        files = os.listdir(directory)
        return json.dumps(files, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"列出目录失败: {directory} - {e}")
        return f"列出目录失败: {str(e)}"


FILE_TOOL_SCHEMAS = {
    "read_file": {
        "name": "read_file",
        "description": "读取文件内容（支持 txt/md/py/json/csv/html 等文本文件、PDF、DOCX，最多 5000 字符）",
        "parameters": {
            "type": "object",
            "properties": {"file_path": {"type": "string", "description": "文件路径"}},
            "required": ["file_path"]
        }
    },
    "write_file": {
        "name": "write_file",
        "description": "将内容写入文件保存到 completed_tasks 目录",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件名"},
                "content": {"type": "string", "description": "要写入的内容"}
            },
            "required": ["file_path", "content"]
        }
    },
    "list_files": {
        "name": "list_files",
        "description": "列出指定目录的内容，返回 JSON 格式的文件名列表",
        "parameters": {
            "type": "object",
            "properties": {"directory": {"type": "string", "description": "目录路径，默认当前目录"}},
            "required": []
        }
    }
}
