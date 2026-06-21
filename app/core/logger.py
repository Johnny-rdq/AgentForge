# 后端 日志系统 — 控制台 + 按天轮转文件，7 天保留
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from app.core.config import settings

LOG_FORMAT = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 后端 文件处理器：每天午夜轮转，保留 N 天
_file_handler = TimedRotatingFileHandler(
    filename=os.path.join(LOG_DIR, "agentforge.log"),
    when="midnight",
    interval=1,
    backupCount=settings.log_retention_days,
    encoding="utf-8",
)
_file_handler.setFormatter(LOG_FORMAT)
_file_handler.setLevel(logging.DEBUG)

# 后端 控制台处理器：按配置级别输出
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(LOG_FORMAT)
_console_handler.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

_loggers: dict[str, logging.Logger] = {}


def get_logger(name: str) -> logging.Logger:
    """后端 获取模块级 logger（带缓存，自动附加 handler）"""
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # 不向上传播，避免重复

    if not logger.handlers:  # 防止热重载时累积
        logger.addHandler(_file_handler)
        logger.addHandler(_console_handler)

    _loggers[name] = logger
    return logger


# 后端 应用级全局 logger
app_logger = logging.getLogger("AgentForge")
app_logger.setLevel(logging.DEBUG)
app_logger.propagate = False
if not app_logger.handlers:
    app_logger.addHandler(_file_handler)
    app_logger.addHandler(_console_handler)
