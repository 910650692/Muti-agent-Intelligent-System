"""Supervisor Agent: 任务调度和路由"""
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from ..state.agent_state import AgentState
from ..llm import get_llm

# Supervisor 的 Prompt
supervisor_prompt = ChatPromptTemplate.from_messages([
    ("system", """你是一个智能任务调度专家。

 你的职责:
 1. 分析用户的需求
 2. 判断需要调用哪个 Agent
 3. 决定任务执行顺序
 4. 判断任务是否已完成

 可用的 Agent:
 - weather: 查询天气信息（用于天气相关的问题）
 - finish: 所有任务已完成，返回最终结果

 已完成的任务: {completed_tasks}

 请分析用户需求，返回下一个要调用的 Agent 名称。
 如果所有任务已完成，返回 "finish"。

 重要：只返回 Agent 名称（weather 或 finish），不要返回其他内容。
 """),
    ("human", "{input}"),
])


def supervisor_agent(state: AgentState) -> AgentState:
    """Supervisor: 任务分析和路由"""

    messages = state["messages"]
    completed_tasks = state.get("completed_tasks", [])

    # 检查是否已经完成了 weather 任务
    if "weather" in completed_tasks:
        print("[Supervisor] 天气任务已完成，准备结束")
        return {
            "messages": [AIMessage(content="[Supervisor] 所有任务已完成")],
            "next_agent": "finish",
            "completed_tasks": completed_tasks,
            "thread_id": state["thread_id"],
        }

    # 获取最后一条用户消息
    last_user_message = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content
            break

    if not last_user_message:
        last_user_message = messages[-1].content if messages else ""

    # 简单逻辑：如果提到天气且未完成，调用 weather
    if "天气" in last_user_message or "weather" in last_user_message.lower():
        next_agent = "weather"
    else:
        next_agent = "finish"

    print(f"[Supervisor] 决定调用: {next_agent}")

    return {
        "messages": [AIMessage(content=f"[Supervisor] 决定调用: {next_agent}")],
        "next_agent": next_agent,
        "completed_tasks": completed_tasks,
        "thread_id": state["thread_id"],
    }
