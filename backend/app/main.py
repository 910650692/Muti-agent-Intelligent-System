"""FastAPI 主应用"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from mem0 import Memory

from .api import chat, health
from .config import config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理应用生命周期：启动时创建Agent、AsyncSqliteSaver和Mem0，关闭时清理"""
    # 启动时：创建AsyncSqliteSaver并存储到app.state
    async with AsyncSqliteSaver.from_conn_string("./data/checkpoints.db") as checkpointer:
        app.state.checkpointer = checkpointer
        print("[Lifespan] AsyncSqliteSaver已启动，数据库路径: ./data/checkpoints.db")

        # ✅ 初始化Mem0长期记忆
        print("[Lifespan] 正在初始化Mem0...")
        mem0_config = {
            "llm": {
                "provider": "deepseek",
                "config": {
                    "model": "deepseek-chat",
                    "temperature": 0.2,
                    "max_tokens": 2000,
                    "api_key": config.DEEPSEEK_API_KEY
                }
            },
            "embedder": {
                "provider": "huggingface",
                "config": {
                    "model": config.MEM0_EMBEDDING_MODEL,
                    "embedding_dims": 512  # ✅ BGE-small-zh-v1.5 的向量维度
                }
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "navigation_memory",
                    "path": config.MEM0_DB_PATH,
                    "embedding_model_dims": 512  # ✅ 明确指定向量维度
                }
            }
        }
        app.state.memory = Memory.from_config(mem0_config)
        print(f"[Lifespan] Mem0已启动（Embedding: {config.MEM0_EMBEDDING_MODEL}）")

        # 创建Agent实例（传入memory）
        from .agent.navigation_agent import create_agent
        app.state.agent = create_agent(checkpointer=checkpointer, memory=app.state.memory)
        print("[Lifespan] NavigationAgent已启动")

        yield  # 应用运行期间

        # 关闭时：自动清理（async with会处理）
        print("[Lifespan] NavigationAgent、Mem0和AsyncSqliteSaver已关闭")


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