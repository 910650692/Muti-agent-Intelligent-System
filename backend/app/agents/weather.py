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
2. **从对话历史中提取城市信息**（用户明确指定的城市，或Navigation Agent提供的位置）
3. **必须调用 get_weather 工具查询天气**
4. 用友好的方式返回天气信息

**重要：如何获取城市信息？**
优先级顺序：
1. 用户明确指定的城市（如"北京天气"、"上海明天天气"）
2. 从Navigation Agent的回复中提取位置信息
   - 查找包含"当前位置"、"您现在在"、"定位"等关键词的消息
   - 提取城市名称
3. 如果历史消息中找不到位置信息，询问用户

**示例：从上下文提取位置**
对话历史:
  用户: "今天天气怎么样"
  Navigation Agent: "您当前位置：北京市朝阳区xxx"

你应该: 调用 get_weather(city="beijing", days=0)

对话历史:
  用户: "上海天气"

你应该: 调用 get_weather(city="shanghai", days=0)

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
- 武汉 → wuhan
- 南京 → nanjing
- 西安 → xian
- 其他城市也需要转换为拼音

注意:
- **永远不要说"天气查询服务暂时无法使用"，直接调用工具**
- 如果对话历史中找不到位置信息且用户未指定城市，询问用户
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
    # 注意：USE_VISION_MODEL_ALWAYS=true 时，这里会使用视觉模型
    # 如果需要根据消息动态选择，应在agent调用时处理
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

    output_text = result.get("output", "")
    intermediate_steps = result.get("intermediate_steps") or []

    # 仅在成功调用工具并返回结果时标记任务完成
    completed_tasks = []
    if intermediate_steps:
        completed_tasks = ["天气查询"]
    else:
        # 如果LLM没有调用工具，通常是在询问城市等补充信息
        print("[Weather Agent] 未触发工具调用，等待用户补充位置信息")

    return {
        "messages": [AIMessage(content=output_text)],
        "completed_tasks": completed_tasks,
        # ✅ 不返回next_agent和thread_id，避免并行冲突
    }
