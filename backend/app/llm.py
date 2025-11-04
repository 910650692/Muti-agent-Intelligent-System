"""LLM 初始化"""
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from .config import config


def has_image_content(messages) -> bool:
    """
    检测消息列表中是否包含图片内容

    Args:
        messages: LangChain消息列表

    Returns:
        bool: 如果包含图片返回True，否则返回False
    """
    if not messages:
        return False

    for msg in messages:
        # 检查消息内容是否为列表格式（多模态格式）
        if hasattr(msg, 'content') and isinstance(msg.content, list):
            for content_item in msg.content:
                if isinstance(content_item, dict):
                    # 检查是否有image_url类型的内容
                    if content_item.get('type') == 'image_url':
                        return True
                    # 检查是否有image类型的内容
                    if content_item.get('type') == 'image':
                        return True

    return False


def get_llm(messages=None, force_vision=False, force_text=False):
    """
    获取 LLM 实例（支持文本和多模态）

    策略：
    1. 如果 force_text=True，强制使用文本模型（优先级最高）
    2. 如果 force_vision=True，强制使用视觉模型
    3. 如果 config.USE_VISION_MODEL_ALWAYS=True，始终使用视觉模型
    4. 如果消息中包含图片，使用视觉模型
    5. 否则使用 DeepSeek 文本模型（更快更便宜）

    Args:
        messages: 消息列表，用于检测是否包含图片
        force_vision: 是否强制使用视觉模型
        force_text: 是否强制使用文本模型（优先级最高，用于Supervisor等不需要视觉的场景）

    Returns:
        LLM实例
    """
    # 决策逻辑
    if force_text:
        # 强制文本模型（用于Supervisor等结构化输出场景）
        use_vision = False
    else:
        use_vision = (
            force_vision or
            config.USE_VISION_MODEL_ALWAYS or
            (messages and has_image_content(messages))
        )

    if use_vision:
        # 使用硅基流动的多模态视觉模型
        print(f"[LLM] 使用多模态视觉模型: {config.SILICONFLOW_VISION_MODEL}")
        return ChatOpenAI(
            model=config.SILICONFLOW_VISION_MODEL,
            temperature=0.7,
            max_tokens=2048,
            api_key=config.SILICONFLOW_API_KEY,
            base_url=config.SILICONFLOW_BASE_URL,
            streaming=True,  # ✅ 启用流式输出
        )
    else:
        # 使用 DeepSeek 文本模型（纯文本对话）
        print(f"[LLM] 使用文本模型: {config.DEEPSEEK_MODEL}")
        return ChatDeepSeek(
            model=config.DEEPSEEK_MODEL,
            temperature=0.7,
            max_tokens=2048,
            api_key=config.DEEPSEEK_API_KEY,
            streaming=True,  # ✅ 启用流式输出
            # ✅ 启用并行工具调用
            model_kwargs={"parallel_tool_calls": True}
        )