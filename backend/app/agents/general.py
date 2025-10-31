"""General Agent: 处理通用对话，配备 MCP 工具"""
from datetime import datetime
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import create_tool_calling_agent, AgentExecutor

from ..state.agent_state import AgentState
from ..llm import get_llm
from ..mcp.manager import mcp_manager
from ..tools.search_tools import search_tools  # 导入搜索工具


def get_current_date_prompt() -> str:
    """获取包含当前日期的系统提示词"""
    current_date = datetime.now().strftime("%Y年%m月%d日")
    current_weekday = datetime.now().strftime("%A")
    weekday_cn = {
        "Monday": "星期一", "Tuesday": "星期二", "Wednesday": "星期三",
        "Thursday": "星期四", "Friday": "星期五", "Saturday": "星期六", "Sunday": "星期日"
    }

    return f"""你是一个友好的AI助手，配备了多种工具来帮助用户。

当前日期: {current_date} {weekday_cn.get(current_weekday, current_weekday)}

你的职责:
1. 回答用户的通用问题（知识问答、闲聊、建议等）
2. 使用工具获取最新信息（当需要时）

你有以下类型的工具可用:
- 搜索工具: 用于查询最新信息、新闻、实时数据
- 其他工具: 根据配置动态加载

使用工具的策略:
- 如果是通用知识且你有把握，可以直接回答
- **如果用户询问"最近"、"最新"、"今天"等时间相关的问题，必须使用搜索工具获取实时信息**
- 搜索时，在查询中包含当前年份（{datetime.now().year}）以确保结果的时效性
- 如果你不确定或知识可能过时，优先使用搜索工具验证
- 使用工具后，引用信息来源

**重要限制:**
- **如果用户询问天气，不要尝试搜索天气信息**
- 天气查询会由专门的天气Agent处理
- 你只需回答非天气相关的部分，如日期、其他通用问题
- 遇到天气问题时，简单说"关于天气，正在为您查询..."即可

注意:
- 你的知识截止日期是2025年1月，对于之后的信息必须使用搜索工具
- 保持回答简洁明了
- 多轮对话时要考虑上下文
- 引用搜索来源时使用具体的标题和链接
"""


# General Agent 的 Prompt（带工具版本） - 使用函数动态生成
def get_general_prompt_with_tools() -> ChatPromptTemplate:
    """获取带工具的 General Agent 提示词模板"""
    return ChatPromptTemplate.from_messages([
        ("system", get_current_date_prompt()),
        MessagesPlaceholder(variable_name="messages"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

# General Agent 的 Prompt（无工具版本）
general_prompt_no_tools = ChatPromptTemplate.from_messages([
    ("system", """你是一个友好的AI助手。

你的职责:
1. 回答用户的通用问题
2. 进行日常对话和闲聊
3. 提供知识解答和建议
4. 保持友好、专业的语气

**重要限制:**
- **如果用户询问天气，不要尝试回答天气信息**
- 天气查询会由专门的天气Agent处理
- 你只需回答非天气相关的部分
- 遇到天气问题时，简单说"关于天气，正在为您查询..."即可

注意:
- 如果需要最新信息，提醒用户你的知识截止日期是 2025年1月
- 保持回答简洁明了
- 多轮对话时要考虑上下文
"""),
    MessagesPlaceholder(variable_name="messages"),
])


def create_general_agent():
    """创建配备工具的 General Agent"""
    llm = get_llm()

    # 加载所有工具
    all_tools = []

    # 1. 加载搜索工具（SerpAPI）
    print("[General Agent] 正在加载搜索工具...")
    all_tools.extend(search_tools)
    print(f"[General Agent] 搜索工具加载完成，共 {len(search_tools)} 个工具")

    # 2. 尝试加载 MCP 工具（可选）
    try:
        print("[General Agent] 正在加载 MCP 工具...")
        mcp_tools = mcp_manager.load_all_tools()
        if mcp_tools:
            all_tools.extend(mcp_tools)
            print(f"[General Agent] MCP 工具加载完成，共 {len(mcp_tools)} 个工具")
        else:
            print("[General Agent] 未找到 MCP 工具，跳过")
    except Exception as e:
        print(f"[General Agent] MCP 工具加载失败（跳过）: {e}")

    # 如果没有任何工具，返回 None（使用普通 LLM）
    if not all_tools:
        print("[General Agent] 警告: 没有可用工具，将使用普通 LLM")
        return None

    # 打印工具列表
    print(f"[General Agent] 工具加载完成，共 {len(all_tools)} 个工具:")
    for tool in all_tools:
        print(f"  - {tool.name}: {tool.description[:60]}...")

    # 创建 Tool Calling Agent（使用动态生成的 Prompt）
    agent = create_tool_calling_agent(llm, all_tools, get_general_prompt_with_tools())

    # 创建 Agent Executor
    return AgentExecutor(
        agent=agent,
        tools=all_tools,
        verbose=True,
        handle_parsing_errors=True,  # 处理解析错误
        max_iterations=5,  # 最多5轮工具调用
    )


async def general_agent(state: AgentState) -> AgentState:
    """General Agent: 处理通用对话任务（使用搜索工具和可选的 MCP 工具，支持并行工具调用）"""

    messages = state["messages"]

    print(f"[General Agent] 处理消息数量: {len(messages)}")
    for msg in messages[-3:]:  # 只打印最近3条
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

    print(f"[General Agent] 清理后消息数量: {len(cleaned_messages)}")

    try:
        # 创建 Agent（每次都重新加载工具，确保使用最新配置）
        agent_executor = create_general_agent()

        # 如果没有工具，直接使用 LLM
        if agent_executor is None:
            print("[General Agent] 使用普通 LLM 模式（无 MCP 工具）")
            llm = get_llm()

            response = await llm.ainvoke(general_prompt_no_tools.format_messages(messages=cleaned_messages))
            final_output = response.content
        else:
            # ✅ 使用 ainvoke 支持异步执行和并行工具调用
            # 如果LLM返回多个tool_calls（如并行搜索多个关键词），会自动并行执行
            result = await agent_executor.ainvoke({
                "messages": cleaned_messages  # ✅ 传递清理后的消息
            })

            # 提取最终输出
            final_output = result.get("output", "抱歉，我无法生成回答。")

        return {
            "messages": [AIMessage(content=final_output)],
            "completed_tasks": ["通用对话"],
        }

    except Exception as e:
        print(f"[General Agent] 执行失败: {e}")
        import traceback
        traceback.print_exc()

        # 降级处理：直接使用 LLM 回答
        print("[General Agent] 降级到直接 LLM 回答")
        llm = get_llm()
        response = await llm.ainvoke(cleaned_messages)

        return {
            "messages": [AIMessage(content=response.content)],
            "completed_tasks": ["通用对话"],
        }
