"""General Agent: 处理通用对话"""
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from ..state.agent_state import AgentState
from ..llm import get_llm


# General Agent 的 Prompt
general_prompt = ChatPromptTemplate.from_messages([
  ("system", """你是一个友好的AI助手。

你的职责:
1. 回答用户的通用问题
2. 进行日常对话和闲聊
3. 提供知识解答和建议
4. 保持友好、专业的语气

注意:
- 如果用户询问天气相关问题，提示他们可以直接问天气
- 保持回答简洁明了
- 多轮对话时要考虑上下文
"""),
  MessagesPlaceholder(variable_name="messages"),
])


def general_agent(state: AgentState) -> AgentState:
    """General Agent: 处理通用对话任务"""

    messages = state["messages"]

    print(f"[General Agent] 处理消息数量: {len(messages)}")
    for msg in messages[-3:]:  # 只打印最近3条
        print(f"  - {msg.__class__.__name__}: {msg.content[:50]}...")

    llm = get_llm()

    # 调用 LLM 生成回复
    response = llm.invoke(general_prompt.format_messages(messages=messages))

    completed_tasks = state.get("completed_tasks", [])
    completed_tasks.append("general")

    return {
        "messages": [AIMessage(content=response.content)],
        "completed_tasks": completed_tasks,
        "next_agent": "supervisor",
        "thread_id": state["thread_id"]
    }