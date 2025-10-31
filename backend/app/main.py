"""FastAPI 主应用"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from .api import chat, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理应用生命周期：启动时创建AsyncSqliteSaver，关闭时清理"""
    # 启动时：创建AsyncSqliteSaver并存储到app.state
    async with AsyncSqliteSaver.from_conn_string("./data/checkpoints.db") as checkpointer:
        app.state.checkpointer = checkpointer
        print("[Lifespan] AsyncSqliteSaver已启动，数据库路径: ./data/checkpoints.db")
        yield  # 应用运行期间
        # 关闭时：自动清理（async with会处理）
        print("[Lifespan] AsyncSqliteSaver已关闭")


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