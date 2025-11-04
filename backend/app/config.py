"""配置管理"""
import os
from dotenv import load_dotenv
load_dotenv()


class Config:
    """应用配置"""

    # DeepSeek LLM
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # 硅基流动 (SiliconFlow) - 多模态视觉模型
    SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY")
    SILICONFLOW_BASE_URL = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    SILICONFLOW_VISION_MODEL = os.getenv("SILICONFLOW_VISION_MODEL", "Qwen/Qwen3-VL-8B-Instruct")

    # LLM 选择策略：是否对所有请求使用视觉模型
    # True: 所有请求都用视觉模型（可处理图片和文本）
    # False: 根据消息内容自动选择（有图片用视觉模型，纯文本用DeepSeek）
    USE_VISION_MODEL_ALWAYS = os.getenv("USE_VISION_MODEL_ALWAYS", "true").lower() == "true"

    # 天气 API
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

    # MCP Server
    MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8080")

    # 数据库
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/checkpoints.db")

    # 图片配置
    MAX_IMAGE_SIZE_MB = int(os.getenv("MAX_IMAGE_SIZE_MB", "5"))
    ALLOWED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/jpg", "image/webp"]


config = Config()