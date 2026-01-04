"""结构化日志系统 - 基于 structlog"""
import structlog
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
import contextvars

# 上下文变量：用于在整个请求链路中传递追踪信息
request_id_var = contextvars.ContextVar("request_id", default=None)
conversation_id_var = contextvars.ContextVar("conversation_id", default=None)
user_id_var = contextvars.ContextVar("user_id", default=None)


def add_context_info(logger, method_name, event_dict):
    """添加上下文信息到日志"""
    request_id = request_id_var.get()
    conversation_id = conversation_id_var.get()
    user_id = user_id_var.get()

    if request_id:
        event_dict["request_id"] = request_id
    if conversation_id:
        event_dict["conversation_id"] = conversation_id
    if user_id:
        event_dict["user_id"] = user_id

    return event_dict


def setup_structured_logging(
    log_level: str = "INFO",
    log_dir: str = "logs",
    enable_json: bool = True,
    enable_console: bool = True
):
    """
    配置结构化日志系统

    Args:
        log_level: 日志级别（DEBUG/INFO/WARNING/ERROR）
        log_dir: 日志目录
        enable_json: 是否输出JSON格式（生产环境推荐）
        enable_console: 是否输出到控制台（开发环境推荐）
    """
    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # 生成日志文件名（按日期）
    from datetime import datetime
    date_str = datetime.now().strftime("%Y%m%d")
    log_file = log_path / f"app_{date_str}.log"
    error_log_file = log_path / f"app_error_{date_str}.log"

    # 配置标准库logging（作为底层）
    # 清除现有handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # 添加控制台handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        root_logger.addHandler(console_handler)

    # 添加文件handler（所有级别）
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
    root_logger.addHandler(file_handler)

    # 添加错误日志handler（只记录ERROR及以上）
    error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)

    # 设置root logger级别（根据配置）
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # ✅ 静默第三方库的调试日志（减少噪音）
    noisy_loggers = [
        'aiosqlite',           # AsyncSqliteSaver的数据库日志
        'sqlite3',             # SQLite日志
        'httpx',               # HTTP客户端日志
        'httpcore',            # HTTP核心日志
        'urllib3',             # URL库日志
        'asyncio',             # 异步IO日志
        'langchain',           # LangChain基础日志（保留重要的）
        'openai',              # OpenAI SDK日志
        'anthropic',           # Anthropic SDK日志
    ]

    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # LangGraph特定日志（只记录WARNING及以上）
    logging.getLogger('langgraph').setLevel(logging.WARNING)
    logging.getLogger('langchain_core').setLevel(logging.WARNING)

    # 配置structlog处理器链
    shared_processors = [
        # 添加日志级别
        structlog.stdlib.add_log_level,
        # 添加时间戳
        structlog.processors.TimeStamper(fmt="iso"),
        # 添加上下文信息
        add_context_info,
        # 添加调用栈信息（文件名、行号、函数名）
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
                structlog.processors.CallsiteParameter.FUNC_NAME,
            }
        ),
    ]

    # 🎨 控制台用彩色格式，文件用JSON格式
    # 为标准库logging配置JSON格式（文件输出）
    json_formatter = logging.Formatter(
        '%(message)s',
        style='%'
    )
    file_handler.setFormatter(json_formatter)
    error_handler.setFormatter(json_formatter)

    # 控制台用彩色格式
    if enable_console:
        console_handler.setFormatter(json_formatter)

    # 配置structlog
    # 根据环境选择渲染器
    if enable_json:
        # 文件输出：JSON格式（便于查询）
        processors = shared_processors + [structlog.processors.JSONRenderer()]
    else:
        # 控制台输出：彩色格式（便于阅读）
        processors = shared_processors + [structlog.dev.ConsoleRenderer(colors=True)]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    print(f"[Structured Logging] 已启用结构化日志")
    print(f"[Structured Logging] 日志级别: {log_level}")
    print(f"[Structured Logging] 日志目录: {log_path.absolute()}")
    print(f"[Structured Logging] 普通日志: {log_file.name}")
    print(f"[Structured Logging] 错误日志: {error_log_file.name}")
    print(f"[Structured Logging] 输出格式: {'JSON' if enable_json else '彩色文本'}")


def get_logger(name: str = None) -> structlog.BoundLogger:
    """
    获取结构化日志记录器

    Args:
        name: 日志器名称（通常是模块名）

    Returns:
        structlog.BoundLogger实例
    """
    return structlog.get_logger(name)


class LogContext:
    """日志上下文管理器 - 用于在代码块中设置追踪信息"""

    def __init__(
        self,
        request_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.request_id = request_id
        self.conversation_id = conversation_id
        self.user_id = user_id

        # 保存旧值（用于恢复）
        self._old_request_id = None
        self._old_conversation_id = None
        self._old_user_id = None

    def __enter__(self):
        """进入上下文"""
        # 保存旧值
        self._old_request_id = request_id_var.get()
        self._old_conversation_id = conversation_id_var.get()
        self._old_user_id = user_id_var.get()

        # 设置新值
        if self.request_id:
            request_id_var.set(self.request_id)
        if self.conversation_id:
            conversation_id_var.set(self.conversation_id)
        if self.user_id:
            user_id_var.set(self.user_id)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        # 恢复旧值
        request_id_var.set(self._old_request_id)
        conversation_id_var.set(self._old_conversation_id)
        user_id_var.set(self._old_user_id)


# 示例用法
if __name__ == "__main__":
    # 1. 初始化（在应用启动时调用）
    setup_structured_logging(
        log_level="INFO",
        enable_json=False,  # 开发环境用False，生产环境用True
        enable_console=True
    )

    # 2. 获取logger
    logger = get_logger("example")

    # 3. 基础日志
    logger.info("应用启动", version="1.0.0", port=8000)

    # 4. 带上下文的日志
    with LogContext(
        request_id="req_123",
        conversation_id="conv_456",
        user_id="user_001"
    ):
        logger.info(
            "推理开始",
            component="reasoning",
            iteration=1,
            message_count=3,
            tool_calls=0
        )

        logger.warning(
            "工具调用超时",
            tool_name="search_poi",
            timeout=30,
            retry_count=1
        )

        logger.error(
            "工具调用失败",
            tool_name="search_poi",
            error="Connection timeout",
            stack_info=True
        )

    # 5. 性能指标日志
    logger.info(
        "请求完成",
        method="POST",
        path="/api/chat/stream",
        status_code=200,
        duration_ms=1250,
        llm_tokens=450,
        tool_calls=2
    )
