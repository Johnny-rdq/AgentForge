# 后端 评测报告 API — 报告列表 + 单篇详情查询
import os
import json
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/benchmark", tags=["benchmark"])

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")


@router.get("/reports")
async def list_reports():
    """后端 列出所有评测报告，按时间倒序"""
    reports = []
    if os.path.exists(DATA_DIR):
        for f in sorted(os.listdir(DATA_DIR), reverse=True):
            if f.startswith("benchmark_report_") and f.endswith(".json"):
                path = os.path.join(DATA_DIR, f)
                try:
                    with open(path, "r", encoding="utf-8") as fp:
                        data = json.load(fp)
                    reports.append({
                        "filename": f,
                        "timestamp": data.get("timestamp", ""),
                        "total": data.get("total", 0),
                        "passed": data.get("passed", 0),
                        "pass_rate": data.get("pass_rate", "0%"),
                        "avg_duration_s": data.get("avg_duration_s", 0),
                        "avg_quality_score": data.get("avg_quality_score", 0),
                    })
                except Exception:
                    pass  # 跳过损坏文件
    return {"reports": reports}


@router.get("/reports/{filename}")
async def get_report(filename: str):
    """后端 获取单个评测报告完整内容"""
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return {"error": "报告不存在"}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
