"""搜索工具：基于 SerpAPI"""
import os
from typing import List, Dict, Any
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
import requests


class SearchInput(BaseModel):
    """搜索工具的输入参数"""
    query: str = Field(description="搜索关键词")
    num_results: int = Field(default=5, description="返回结果数量，默认5条")


def search_web(query: str, num_results: int = 5) -> str:
    """
    使用 SerpAPI 搜索网页

    Args:
        query: 搜索关键词
        num_results: 返回结果数量

    Returns:
        格式化的搜索结果
    """
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        return "错误: 未配置 SERPAPI_API_KEY"

    try:
        # SerpAPI 请求参数
        params = {
            "q": query,
            "api_key": api_key,
            "num": num_results,
            "engine": "google",  # 使用 Google 搜索
            "hl": "zh-cn",  # 中文结果
            "gl": "cn"  # 中国地区
        }

        # 发送请求
        response = requests.get(
            "https://serpapi.com/search",
            params=params,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        # 提取有机搜索结果
        organic_results = data.get("organic_results", [])

        if not organic_results:
            return f"未找到关于 '{query}' 的搜索结果"

        # 格式化结果
        formatted_results = []
        for i, result in enumerate(organic_results[:num_results], 1):
            title = result.get("title", "无标题")
            link = result.get("link", "")
            snippet = result.get("snippet", "无描述")

            formatted_results.append(
                f"{i}. **{title}**\n"
                f"   链接: {link}\n"
                f"   摘要: {snippet}\n"
            )

        return "\n".join(formatted_results)

    except requests.exceptions.Timeout:
        return "搜索超时，请稍后重试"
    except requests.exceptions.RequestException as e:
        return f"搜索请求失败: {str(e)}"
    except Exception as e:
        return f"搜索出错: {str(e)}"


# 创建 LangChain Tool
search_tool = StructuredTool.from_function(
    func=search_web,
    name="search_web",
    description="搜索网页信息。当需要查询最新信息、新闻、实时数据时使用此工具。支持中英文搜索。",
    args_schema=SearchInput
)

# 导出工具列表
search_tools = [search_tool]
