"""Supervisor Agent: 任务调度和路由"""
import json
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from ..state.agent_state import AgentState
from ..llm import get_llm

# Supervisor 的 Prompt
supervisor_prompt = ChatPromptTemplate.from_messages([
    ("system", """你是一个智能任务路由专家。

你的职责:
1. 分析用户的需求
2. 判断需要调用哪个 Agent
3. 决定任务执行顺序
4. 判断任务是否已完成

可用的 Agent:
- weather: 查询天气信息（包括天气、温度、降雨、风力等所有气象相关信息）
- general: 通用对话（闲聊、知识问答、日常对话等非天气类问题）
- finish: 所有任务已完成，返回最终结果

已完成的任务: {completed_tasks}

分析用户消息，返回 JSON 格式的路由决策:
{{"agent": "weather/general/finish", "reason": "选择该 Agent 的原因"}}

重要规则:
1. 只有当刚完成一个任务后，才考虑返回 finish
2. 如果是新的用户问题，必须路由到 weather 或 general
3. 天气相关（天气、温度、降雨、冷热等）→ weather
4. 其他所有问题 → general
"""),
    ("human", "用户消息: {input}"),
])


def supervisor_agent(state: AgentState) -> AgentState:
    """Supervisor: 任务分析和路由"""

    messages = state["messages"]
    completed_tasks = state.get("completed_tasks", [])

    # 获取最后一条用户消息
    last_user_message = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content
            break

    if not last_user_message:
        last_user_message = messages[-1].content if messages else ""

    # 检查本轮对话是否已经完成了任务
    recent_messages = messages[-5:] if len(messages) >= 5 else messages
    has_agent_response = any(
        msg.content and not msg.content.startswith("[Supervisor]")
        for msg in recent_messages
        if isinstance(msg, AIMessage)
    )

    # 如果刚刚完成了任务，则结束
    if completed_tasks and has_agent_response:
        print(f"[Supervisor] 任务 {completed_tasks} 已完成，准备结束")
        return {
            "messages": [AIMessage(content="[Supervisor] 所有任务已完成")],
            "next_agent": "finish",
            "completed_tasks": [],  # 重置 completed_tasks
            "thread_id": state["thread_id"],
        }

    # 使用 LLM 进行路由决策
    llm = get_llm()

    try:
        response = llm.invoke(supervisor_prompt.format_messages(
            completed_tasks=completed_tasks,
            input=last_user_message
        ))

        # 解析 JSON 响应
        result = json.loads(response.content)
        next_agent = result.get("agent", "general")
        reason = result.get("reason", "未提供原因")

        print(f"[Supervisor] LLM 路由决策: {next_agent}")
        print(f"[Supervisor] 决策原因: {reason}")

    except (json.JSONDecodeError, KeyError) as e:
        # 如果 LLM 返回格式不对，降级到关键词匹配
        print(f"[Supervisor] LLM 路由失败，降级到关键词匹配: {e}")

        weather_keywords = ["天气", "weather", "温度", "明天", "后天", "今天", "降雨", "下雨", "冷", "热", "风"]
        if any(keyword in last_user_message for keyword in weather_keywords):
            next_agent = "weather"
            reason = "关键词匹配（降级）"
        else:
            next_agent = "general"
            reason = "默认路由（降级）"

        print(f"[Supervisor] 降级路由: {next_agent}, 原因: {reason}")

    return {
        "messages": [AIMessage(content=f"[Supervisor] 路由到: {next_agent} ({reason})")],
        "next_agent": next_agent,
        "completed_tasks": [],  # 重置，为下次对话做准备
        "thread_id": state["thread_id"],
    }
