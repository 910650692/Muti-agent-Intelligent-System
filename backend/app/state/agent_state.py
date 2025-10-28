"""Multi-Agent 共享状态定义"""
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    """Multi-Agent 共享状态"""

    # 消息历史
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # 下一个要执行的 Agent
    next_agent: str

    # 已完成的任务列表
    completed_tasks: list

    # 会话 ID
    thread_id: str