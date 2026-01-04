"""LangFuse 配置和初始化（v3.x）"""
import os
from typing import Optional

# LangFuse v3.x 导入
from langfuse.langchain import CallbackHandler

# 全局标记：LangFuse 是否可用
_langfuse_enabled: bool = False


def init_langfuse() -> bool:
    """
    初始化 LangFuse 环境变量（v3.x）

    检查配置并设置环境变量
    CallbackHandler 会自动从环境变量读取配置

    Returns:
        bool: 如果配置完整返回 True
    """
    global _langfuse_enabled

    # 读取环境变量
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

    # 检查配置是否完整
    if not public_key or not secret_key:
        print("[LangFuse] ⚠️ 配置不完整，未启用追踪")
        print("[LangFuse] 请在 .env 文件中配置:")
        print("[LangFuse]   - LANGFUSE_PUBLIC_KEY")
        print("[LangFuse]   - LANGFUSE_SECRET_KEY")
        _langfuse_enabled = False
        return False

    # 检查是否是默认占位符
    if public_key == "your-public-key-here" or secret_key == "your-secret-key-here":
        print("[LangFuse] ⚠️ 请替换 .env 中的占位符为真实的 API Keys")
        _langfuse_enabled = False
        return False

    try:
        # v3.x: 确保环境变量已设置（CallbackHandler 会自动读取）
        os.environ["LANGFUSE_PUBLIC_KEY"] = public_key
        os.environ["LANGFUSE_SECRET_KEY"] = secret_key
        os.environ["LANGFUSE_HOST"] = host

        _langfuse_enabled = True
        print(f"[LangFuse] ✅ 已启用追踪")
        print(f"[LangFuse] 🔗 查看追踪: {host}")

        return True

    except Exception as e:
        print(f"[LangFuse] ❌ 初始化失败: {e}")
        print(f"[LangFuse] 请检查 API Keys 是否正确")
        import traceback
        traceback.print_exc()
        _langfuse_enabled = False
        return False


def create_langfuse_handler(
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    tags: Optional[list] = None,
    metadata: Optional[dict] = None
):
    """
    创建新的 LangFuse CallbackHandler 实例（v3.x）

    根据官方文档：https://langfuse.com/integrations/frameworks/langchain
    v3.x 中 CallbackHandler 无参数，session_id 和 user_id 通过 metadata 传递

    Args:
        session_id: 会话ID（对话ID）
        user_id: 用户ID
        tags: 标签列表（v3.x 中通过 metadata 传递）
        metadata: 额外元数据

    Returns:
        (handler, metadata_dict) 元组，或 (None, None) 如果未启用
    """
    if not _langfuse_enabled:
        return None, None

    try:
        # ✅ v3.x 正确方式：无参数创建 handler
        handler = CallbackHandler()

        # ✅ 构造特殊的 metadata（LangFuse v3.x 识别这些字段）
        langfuse_metadata = metadata.copy() if metadata else {}

        if session_id:
            langfuse_metadata["langfuse_session_id"] = session_id
        if user_id:
            langfuse_metadata["langfuse_user_id"] = user_id
        if tags:
            langfuse_metadata["langfuse_tags"] = tags

        return handler, langfuse_metadata

    except Exception as e:
        print(f"[LangFuse] ⚠️ 创建 handler 失败: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def is_langfuse_enabled() -> bool:
    """
    检查 LangFuse 是否已启用

    Returns:
        bool: 如果已启用返回 True
    """
    return _langfuse_enabled
