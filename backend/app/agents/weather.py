"""Weather Agent: 查询天气"""
from langchain_core.messages import AIMessage, HumanMessage
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
3. **必须调用 get_weather 工具查询天气**
4. 用友好的方式返回天气信息

**重要：你必须使用工具，不能凭记忆或猜测回答天气信息！**

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

城市名称转换规则（必须使用拼音）:
- 北京 → beijing
- 上海 → shanghai
- 广州 → guangzhou
- 深圳 → shenzhen
- 成都 → chengdu
- 杭州 → hangzhou
- 其他城市也需要转换为拼音

注意:
- **永远不要说"天气查询服务暂时无法使用"，直接调用工具**
- 如果用户没有明确说明城市，询问用户
- 城市参数必须是拼音格式
- 如果用户问未来5天以上的天气，告知只能查询未来5天内的天气
- 返回结果要简洁清晰
- 如果工具调用失败，说明具体错误原因
"""),
  MessagesPlaceholder(variable_name="messages"),
  MessagesPlaceholder(variable_name="agent_scratchpad"),
])


def create_weather_agent():
    """创建 Weather Agent"""
    llm = get_llm()
    agent = create_tool_calling_agent(llm, weather_tools, weather_prompt)
    return AgentExecutor(agent=agent, tools=weather_tools, verbose=True)


async def weather_agent(state: AgentState) -> AgentState:
    """Weather Agent: 处理天气查询任务（支持并行工具调用）"""

    messages = state["messages"]

    print(f"[Weather Agent] 处理消息数量: {len(messages)}")
    for msg in messages[-3:]:  # 只打印最近3条，避免日志过长
        print(f"  - {msg.__class__.__name__}: {msg.content[:50]}...")

    # ✅ 清理消息：只保留用户消息和最近的上下文
    cleaned_messages = []
    for msg in messages:
        # 保留所有用户消息
        if isinstance(msg, HumanMessage):
            cleaned_messages.append(msg)
        # 过滤掉其他Agent的回复（避免干扰）
        elif isinstance(msg, AIMessage):
            content = msg.content
            # 跳过Supervisor的路由消息
            if content.startswith("[Supervisor]"):
                continue
            # 跳过无关的长回复（如特朗普新闻）
            if len(content) > 500:
                continue
            # 保留简短的相关回复
            cleaned_messages.append(msg)

    # 如果清理后没有消息，至少保留最后一条用户消息
    if not cleaned_messages:
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                cleaned_messages = [msg]
                break

    print(f"[Weather Agent] 清理后消息数量: {len(cleaned_messages)}")

    agent_executor = create_weather_agent()

    # ✅ 使用 ainvoke 支持异步执行和并行工具调用
    # 如果LLM返回多个tool_calls（如查询多个城市天气），会自动并行执行
    result = await agent_executor.ainvoke({
        "messages": cleaned_messages,  # ✅ 传递清理后的消息
    })

    return {
        "messages": [AIMessage(content=result["output"])],
        "completed_tasks": ["天气查询"],  # ✅ 只返回新增任务，operator.add会自动合并
        # ✅ 不返回next_agent和thread_id，避免并行冲突
    }