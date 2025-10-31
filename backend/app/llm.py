"""LLM 初始化"""
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from .config import config


def get_llm():
    """获取 DeepSeek LLM 实例（启用流式输出和并行工具调用）"""
    return ChatDeepSeek(
        model=config.DEEPSEEK_MODEL,
        temperature=0.7,
        max_tokens=2048,
        api_key=config.DEEPSEEK_API_KEY,
        streaming=True,  # ✅ 启用流式输出
        # ✅ 启用并行工具调用（DeepSeek默认支持，显式设置以提高可读性）
        # 允许LLM在一次调用中返回多个tool_calls，大幅降低延迟
        model_kwargs={"parallel_tool_calls": True}
    )