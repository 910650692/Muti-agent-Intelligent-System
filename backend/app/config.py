"""配置管理"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 显式加载 backend/.env 文件（确保无论从哪个目录启动都能找到）
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
print(f"[Config] 已加载环境变量文件: {env_path.absolute()}")
print(f"[Config] 文件是否存在: {env_path.exists()}")


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

    @classmethod
    def _print_config_debug(cls):
        """打印关键配置用于调试"""
        print(f"[Config] USE_VISION_MODEL_ALWAYS 环境变量原始值: {os.getenv('USE_VISION_MODEL_ALWAYS')}")
        print(f"[Config] USE_VISION_MODEL_ALWAYS 解析后: {cls.USE_VISION_MODEL_ALWAYS}")
        print(f"[Config] DEEPSEEK_MODEL: {cls.DEEPSEEK_MODEL}")
        print(f"[Config] SILICONFLOW_VISION_MODEL: {cls.SILICONFLOW_VISION_MODEL}")

    # 天气 API
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

    # MCP Server
    MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8080")

    # 数据库
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/checkpoints.db")

    # 图片配置
    MAX_IMAGE_SIZE_MB = int(os.getenv("MAX_IMAGE_SIZE_MB", "5"))
    ALLOWED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/jpg", "image/webp"]

    # Mem0 长期记忆配置
    MEM0_EMBEDDING_MODEL = os.getenv("MEM0_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    MEM0_DB_PATH = os.getenv("MEM0_DB_PATH", "./data/mem0_db")


config = Config()

# 启动时打印配置调试信息
Config._print_config_debug()