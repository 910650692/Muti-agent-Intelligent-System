"""Train Agent: 查询火车票信息"""
from langchain_core.messages import AIMessage, HumanMessage
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from ..state.agent_state import AgentState
from ..llm import get_llm
from ..mcp.manager import mcp_manager


# Train Agent 的 Prompt
train_prompt = ChatPromptTemplate.from_messages([
    ("system", """你是一个火车票查询专家，可以帮助用户查询12306火车票信息。

你的职责:
1. 理解用户的火车票查询需求
2. 提取出发站、到达站、出发日期等信息
3. 调用12306工具查询车票信息
4. 用友好的方式返回查询结果

可用工具说明:
- query_tickets: 查询余票信息
- query_transfer: 查询中转方案
- query_train_schedule: 查询列车时刻表
- search_stations: 搜索车站信息

注意:
- 如果用户没有明确说明出发站或到达站，询问用户
- 如果用户没有说明日期，默认查询今天或明天的车票
- 返回结果要简洁清晰，突出重点信息（车次、出发/到达时间、价格）
- 如果没有直达车票，可以提示查询中转方案
"""),
    MessagesPlaceholder(variable_name="messages"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])


def create_train_agent():
    """创建 Train Agent"""
    llm = get_llm()

    # 加载12306 MCP工具
    print("[Train Agent] 正在加载 12306 工具...")
    tools = mcp_manager.load_all_tools()

    # 过滤出12306相关工具
    train_tools = [tool for tool in tools if "12306" in tool.name.lower() or any(
        keyword in tool.description.lower()
        for keyword in ["火车", "车票", "列车", "12306", "train", "ticket"]
    )]

    if not train_tools:
        print("[Train Agent] 警告: 未找到12306工具")
        return None

    print(f"[Train Agent] 12306 工具加载完成，共 {len(train_tools)} 个工具")
    for tool in train_tools:
        print(f"  - {tool.name}: {tool.description[:60]}...")

    agent = create_tool_calling_agent(llm, train_tools, train_prompt)
    return AgentExecutor(agent=agent, tools=train_tools, verbose=True)


async def train_agent(state: AgentState) -> AgentState:
    """Train Agent: 处理火车票查询任务（支持并行工具调用）"""

    messages = state["messages"]

    print(f"[Train Agent] 处理消息数量: {len(messages)}")
    for msg in messages[-3:]:
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
            # 跳过无关的长回复
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

    print(f"[Train Agent] 清理后消息数量: {len(cleaned_messages)}")

    try:
        agent_executor = create_train_agent()

        if agent_executor is None:
            return {
                "messages": [AIMessage(content="抱歉，火车票查询服务暂时不可用")],
                "completed_tasks": ["火车票查询"],
            }

        # ✅ 使用 ainvoke 支持异步执行和并行工具调用
        # 如果LLM返回多个tool_calls（如查询多个车次），会自动并行执行
        result = await agent_executor.ainvoke({
            "messages": cleaned_messages,  # ✅ 传递清理后的消息
        })

        return {
            "messages": [AIMessage(content=result["output"])],
            "completed_tasks": ["火车票查询"],
        }

    except Exception as e:
        print(f"[Train Agent] 执行失败: {e}")
        import traceback
        traceback.print_exc()

        return {
            "messages": [AIMessage(content=f"抱歉，火车票查询出现错误：{str(e)}")],
            "completed_tasks": ["火车票查询"],
        }
