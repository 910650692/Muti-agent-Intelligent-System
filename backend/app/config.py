"""配置管理"""
import os
from dotenv import load_dotenv
load_dotenv()


class Config:
    """应用配置"""

    # DeepSeek LLM
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # 天气 API
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

    # MCP Server
    MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8080")

    # 数据库
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/checkpoints.db")


config = Config()