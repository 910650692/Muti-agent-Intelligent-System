"""LLM 初始化"""
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from .config import config




def get_llm():
    """获取 DeepSeek LLM 实例"""
    return ChatDeepSeek(
        model=config.DEEPSEEK_MODEL,
        temperature=0.7,
        max_tokens=2048,
        api_key=config.DEEPSEEK_API_KEY
    )