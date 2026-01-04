"""FastAPI 主应用"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import os

from .api import chat, health, conversations
from .config import config
from .db.database import init_db
from .utils.structured_logger import setup_structured_logging, get_logger

# 获取logger
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理应用生命周期：启动时创建Agent和AsyncSqliteSaver，关闭时清理"""
    # ✅ 初始化结构化日志系统
    # 默认使用JSON格式，避免文件中出现ANSI颜色码
    setup_structured_logging(
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_dir=os.getenv("LOG_DIR", "logs"),
        enable_json=True,  # 文件使用JSON格式（无颜色码，便于查询）
        enable_console=True
    )
    logger.info("应用启动", component="lifespan")

    # ✅ 初始化 LangFuse（可选，用于追踪和可视化）
    from .langfuse_config import init_langfuse
    init_langfuse()

    # 初始化对话数据库
    await init_db()
    logger.info("数据库初始化完成", component="database")

    # 启动时：创建AsyncSqliteSaver并存储到app.state
    async with AsyncSqliteSaver.from_conn_string("./data/checkpoints.db") as checkpointer:
        app.state.checkpointer = checkpointer
        logger.info(
            "Checkpointer已启动",
            component="checkpointer",
            db_path="./data/checkpoints.db"
        )

        # 创建Agent实例
        from .agent.navigation_agent_v2 import create_agent_v2
        app.state.agent = create_agent_v2(checkpointer=checkpointer)
        logger.info("Agent已启动", component="agent", agent_type="navigation_v2")

        yield  # 应用运行期间

        # 关闭时：自动清理（async with会处理）
        logger.info("应用关闭", component="lifespan")


# 创建 FastAPI 应用
app = FastAPI(
    title="Muti Agent Chat API",
    description="Multi-Agent 导航聊天系统 API",
    version="0.1.0",
    lifespan=lifespan  # ✅ 绑定生命周期管理
)

# CORS 中间件
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],  # 生产环境应该限制具体域名
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)
# 注册路由
app.include_router(health.router, prefix="/api", tags=["健康检查"])
app.include_router(chat.router, prefix="/api", tags=["聊天"])
app.include_router(conversations.router, prefix="/api", tags=["对话管理"])


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Navigation Agent Chat API",
        "docs": "/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)