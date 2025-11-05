"""LLM 初始化"""
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from .config import config


def _check_message_has_image(msg) -> bool:
    """
    检查单条消息是否包含图片

    Args:
        msg: 单条消息对象

    Returns:
        bool: 如果消息包含图片返回True
    """
    if hasattr(msg, 'content') and isinstance(msg.content, list):
        for content_item in msg.content:
            if isinstance(content_item, dict):
                if content_item.get('type') in ['image_url', 'image']:
                    return True
    return False


def _extract_text_from_message(msg) -> str:
    """
    从消息中提取纯文本内容

    Args:
        msg: 消息对象

    Returns:
        str: 提取的文本内容
    """
    if hasattr(msg, 'content'):
        content = msg.content
        # 如果是字符串，直接返回
        if isinstance(content, str):
            return content
        # 如果是列表（多模态格式），提取text类型的内容
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    texts.append(item.get('text', ''))
                elif isinstance(item, str):
                    texts.append(item)
            return ' '.join(texts)
    return ''


def has_image_content(messages) -> bool:
    """
    智能检测是否需要使用视觉模型（方案4：关键词智能检测）

    策略：
    1. 如果最新用户消息包含图片 → 返回True
    2. 如果最新用户消息包含图片相关关键词（如"图片"、"照片"、"这张图"）
       → 检测历史消息中是否有图片
    3. 否则 → 返回False

    这样可以：
    - 用户发图片 → 使用VL模型 ✅
    - 后续问"图片里有几只猫？" → 使用VL模型（关键词触发）✅
    - 后续问"今天天气怎么样？" → 使用文本模型（无关键词）✅

    Args:
        messages: LangChain消息列表

    Returns:
        bool: 如果需要使用视觉模型返回True
    """
    if not messages:
        return False

    # 图片相关关键词列表
    IMAGE_KEYWORDS = [
        # 中文关键词
        '图片', '照片', '图像', '截图', '图', '画面',
        '这张', '那张', '上面', '图中', '画中',
        '这个图', '那个图', '刚才的图', '之前的图',
        # 英文关键词
        'image', 'picture', 'photo', 'screenshot',
        'this image', 'that picture', 'the image', 'the picture'
    ]

    # 1. 找到最新的用户消息（从后往前找第一条 HumanMessage）
    latest_user_message = None
    for msg in reversed(messages):
        if hasattr(msg, 'type') and msg.type == 'human':
            latest_user_message = msg
            break

    if not latest_user_message:
        return False

    # 2. 检测最新消息是否直接包含图片
    if _check_message_has_image(latest_user_message):
        return True

    # 3. 提取最新消息的文本内容
    latest_text = _extract_text_from_message(latest_user_message).lower()

    # 4. 检测是否包含图片相关关键词
    has_keyword = any(keyword.lower() in latest_text for keyword in IMAGE_KEYWORDS)

    # 5. 如果有关键词，检测历史消息中是否有图片
    if has_keyword:
        for msg in messages:
            if _check_message_has_image(msg):
                print(f"[LLM] 检测到图片相关关键词且历史中有图片，使用视觉模型")
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