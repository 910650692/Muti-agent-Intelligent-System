"""FastAPI 主应用"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import chat, health

# 创建 FastAPI 应用
app = FastAPI(
  title="Muti Agent Chat API",
  description="Multi-Agent 导航聊天系统 API",
  version="0.1.0"
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