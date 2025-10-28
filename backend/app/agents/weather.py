"""Weather Agent: 查询天气"""
from langchain_core.messages import AIMessage
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from ..state.agent_state import AgentState
from ..tools.weather_tools import weather_tools
from ..llm import get_llm

# Weather Agent 的 Prompt
weather_prompt = ChatPromptTemplate.from_messages([
  ("system", """你是一个天气查询专家。

你的职责:
1. 理解用户的天气查询需求
2. 提取城市名称和时间范围
3. 调用 get_weather 工具查询天气
4. 用友好的方式返回天气信息

工具说明:
- get_weather(city: str, days: int = 0)
  - city: 城市名称（拼音格式，如 beijing, shanghai）
  - days: 查询未来第几天 (0=今天, 1=明天, 2=后天, 3=第3天, 4=第4天)

时间识别规则:
- "今天" / "现在" / "当前" → days=0
- "明天" → days=1
- "后天" → days=2
- "大后天" / "第3天" → days=3
- "第4天" → days=4

注意:
- 如果用户没有明确说明城市，询问用户
- 查询的城市参数必须是拼音格式，例如：beijing, shanghai
- 如果用户问未来5天以上的天气，告知只能查询未来5天内的天气
- 返回结果要简洁清晰
"""),
  MessagesPlaceholder(variable_name="messages"),
  MessagesPlaceholder(variable_name="agent_scratchpad"),
])


def create_weather_agent():
    """创建 Weather Agent"""
    llm = get_llm()
    agent = create_tool_calling_agent(llm, weather_tools, weather_prompt)
    return AgentExecutor(agent=agent, tools=weather_tools, verbose=True)


def weather_agent(state: AgentState) -> AgentState:
    """Weather Agent: 处理天气查询任务"""

    agent_executor = create_weather_agent()

    result = agent_executor.invoke({
        "messages": state["messages"],
    })

    completed_tasks = state.get("completed_tasks", [])
    completed_tasks.append("weather")

    return {
        "messages": [AIMessage(content=result["output"])],
        "completed_tasks": completed_tasks,
        "next_agent": "supervisor",
        "thread_id": state["thread_id"]
    }