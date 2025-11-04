"""单Agent ReAct 状态定义"""
from typing import TypedDict, Annotated, List
from langchain_core.messages import BaseMessage
import operator


class AgentState(TypedDict):
    """单Agent ReAct状态

    在ReAct架构中，状态非常简单：
    - 只需要维护消息历史
    - thread_id在config中传递
    - 不需要next_agent/completed_tasks等Multi-Agent字段
    """

    # 消息历史（支持累加）
    messages: Annotated[List[BaseMessage], operator.add]