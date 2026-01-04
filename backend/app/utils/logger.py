"""日志配置模块

提供统一的日志记录功能：
1. 控制台输出：方便开发调试
2. 文件保存：方便溯源和问题排查
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler


def setup_logger(name: str = "navigation_agent", log_dir: str = "logs") -> logging.Logger:
    """配置日志记录器

    Args:
        name: Logger名称
        log_dir: 日志文件目录

    Returns:
        配置好的Logger实例
    """
    # 创建logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 避免重复添加handler
    if logger.handlers:
        return logger

    # 创建日志目录
    log_path = Path(__file__).parent.parent.parent / log_dir
    log_path.mkdir(exist_ok=True)

    # 日志格式
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 1. 控制台处理器（INFO及以上）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. 文件处理器 - 所有日志（DEBUG及以上）
    today = datetime.now().strftime("%Y%m%d")
    all_log_file = log_path / f"agent_{today}.log"
    file_handler = RotatingFileHandler(
        all_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 3. 错误日志单独保存
    error_log_file = log_path / f"agent_error_{today}.log"
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    logger.info(f"日志系统初始化完成 - 日志目录: {log_path}")
    logger.info(f"  - 完整日志: {all_log_file}")
    logger.info(f"  - 错误日志: {error_log_file}")

    return logger


def log_section(logger: logging.Logger, title: str, level: str = "INFO"):
    """打印带分隔线的日志标题

    Args:
        logger: Logger实例
        title: 标题文本
        level: 日志级别（INFO/DEBUG/WARNING/ERROR）
    """
    separator = "=" * 60
    log_func = getattr(logger, level.lower())
    log_func(separator)
    log_func(title)
    log_func(separator)


# 创建全局logger实例
agent_logger = setup_logger()
