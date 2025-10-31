"""Multi-Agent 共享状态定义"""
from typing import TypedDict, Annotated, Sequence, List
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    """Multi-Agent 共享状态"""

    # 消息历史（支持并行累加）
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # 下一个要执行的 Agent（兼容旧版）
    next_agent: str

    # ✅ 下一批要并行执行的 Agents（新增）
    next_agents: List[str]

    # ✅ 已完成的任务列表（支持并行累加）
    completed_tasks: Annotated[list, operator.add]

    # 会话 ID
    thread_id: str

    # 循环计数器（防止死循环）
    iteration_count: int