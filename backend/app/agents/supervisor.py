"""Supervisor Agent: 任务调度和路由"""
import json
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from ..state.agent_state import AgentState
from ..llm import get_llm

# Supervisor 的 Prompt
supervisor_prompt = ChatPromptTemplate.from_messages([
    ("system", """你是任务路由专家，负责分析用户需求并协调多个专业 Agent。

可用的 Agent:
- weather: 查询天气信息（天气、温度、降雨、风力等气象相关）
- train: 查询火车票信息（12306车票查询、余票、列车时刻、中转等）
- general: 通用对话（知识问答、日常对话、闲聊等）
- finish: 所有任务已完成

路由逻辑:
1. **查看最近的对话历史，检查 Agent 是否已经回答了用户的问题**
2. 如果用户的问题已经得到完整回答 → 返回 finish
3. 如果还有未回答的问题 → 路由到对应的 Agent

**重要：如何判断问题是否已回答？**
- 查看对话历史中最近的 Agent 回复
- 如果回复内容直接针对用户问题，且给出了具体答案 → 已回答
- 如果回复内容与用户问题无关，或没有给出答案 → 未回答

**路由规则：**
- 火车票、车次、12306、高铁、动车、列车等 → train
- 天气、温度、降雨、气象等 → weather
- 其他通用问题 → general

**示例：**
用户: "今天几号？"
Agent 回复: "今天是2025年10月30日"
判断: 已完整回答 → finish

用户: "明天北京到上海的火车票"
判断: 火车票查询 → train

返回 JSON 格式:
{{"agent": "weather/train/general/finish", "reason": "原因"}}
"""),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
])


def supervisor_agent(state: AgentState) -> AgentState:
    """Supervisor: 任务分析和路由"""

    messages = state["messages"]
    completed_tasks = state.get("completed_tasks", [])
    iteration_count = state.get("iteration_count", 0)

    # 循环次数限制（防止死循环）
    MAX_ITERATIONS = 10
    if iteration_count >= MAX_ITERATIONS:
        print(f"[Supervisor] 达到最大循环次数 {MAX_ITERATIONS}，强制结束")
        return {
            "messages": [AIMessage(content="[Supervisor] 已达到最大处理次数")],
            "next_agent": "finish",
            "completed_tasks": completed_tasks,  # 保持不变
            "thread_id": state["thread_id"],
            "iteration_count": iteration_count,
        }

    # 获取最后一条用户消息
    last_user_message = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content
            break

    # 获取对话历史（最近10条，排除 Supervisor 的消息）
    chat_history = []
    for msg in messages[-10:]:
        if isinstance(msg, AIMessage) and msg.content.startswith("[Supervisor]"):
            continue  # 跳过 Supervisor 的路由消息
        chat_history.append(msg)

    # 使用 LLM 进行路由决策
    llm = get_llm()

    try:
        response = llm.invoke(supervisor_prompt.format_messages(
            chat_history=chat_history,
            input=last_user_message
        ))

        # 解析 JSON 响应
        result = json.loads(response.content)
        next_agent = result.get("agent", "general")
        reason = result.get("reason", "未提供原因")

        print(f"[Supervisor] 路由决策: {next_agent} (循环: {iteration_count + 1})")
        print(f"[Supervisor] 原因: {reason}")

    except (json.JSONDecodeError, KeyError) as e:
        # 如果 LLM 返回格式不对，降级到关键词匹配
        print(f"[Supervisor] LLM 路由失败，降级到关键词匹配: {e}")

        # 关键词匹配
        weather_keywords = ["天气", "weather", "温度", "明天", "后天", "今天", "降雨", "下雨", "冷", "热", "风"]
        train_keywords = ["火车", "车票", "高铁", "动车", "列车", "12306", "余票", "车次"]

        if any(keyword in last_user_message for keyword in train_keywords):
            next_agent = "train"
            reason = "关键词匹配（火车票）"
        elif any(keyword in last_user_message for keyword in weather_keywords):
            next_agent = "weather"
            reason = "关键词匹配（天气）"
        else:
            next_agent = "general"
            reason = "默认路由"

        print(f"[Supervisor] 降级路由: {next_agent}")

    # 如果决策是 finish，重置计数器和任务列表；否则递增
    if next_agent == "finish":
        new_iteration_count = 0
        new_completed_tasks = []
    else:
        new_iteration_count = iteration_count + 1
        new_completed_tasks = completed_tasks  # 保持累加

    return {
        "messages": [AIMessage(content=f"[Supervisor] 路由到: {next_agent}")],  # 供LLM参考，会被API层过滤
        "next_agent": next_agent,
        "completed_tasks": new_completed_tasks,
        "thread_id": state["thread_id"],
        "iteration_count": new_iteration_count,
    }
