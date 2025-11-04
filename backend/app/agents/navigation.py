"""Navigation Agent: 处理导航相关任务"""
from langchain_core.messages import AIMessage, HumanMessage
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from ..state.agent_state import AgentState
from ..llm import get_llm
from ..mcp.manager import mcp_manager


# Navigation Agent 的 Prompt
navigation_prompt = ChatPromptTemplate.from_messages([
    ("system", """你是一个车载导航专家，可以帮助用户进行导航、搜索地点、查看位置等操作。

你的职责:
1. 理解用户的导航需求
2. 提取目的地、途经点、搜索关键词等信息
3. 调用导航工具完成用户请求
4. 用友好、简洁的方式返回结果

**重要：当其他服务需要位置信息时**
如果用户的问题不是直接的导航请求，但可能需要位置信息（如查询天气、搜索附近的内容），你应该：
- **主动调用 get_current_location 获取位置**
- 返回简洁的位置信息，供后续服务使用

**示例场景**：
1. 用户："今天天气怎么样"
   → 调用 get_current_location，返回"您当前位置：北京市朝阳区"

2. 用户："附近有什么餐厅"
   → 调用 search_nearby_poi(keyword="餐厅")

3. 用户："导航到洛克公园"
   → 调用 search_poi(keyword="洛克公园") → start_navigation

可用工具说明:
- **位置相关**:
  - get_current_location: 获取当前车辆位置（**当需要位置信息时必须调用**）

- **搜索相关**:
  - search_poi: 搜索指定关键词的兴趣点（POI）
  - search_nearby_poi: 搜索附近的POI（如加油站、充电站、停车场）

- **导航相关**:
  - start_navigation: 启动导航到指定目的地
  - go_home: 一键回家导航
  - go_company: 一键去公司导航

- **收藏管理**:
  - add_favorite: 添加收藏地点
  - get_favorites: 获取收藏列表

注意:
- **即使用户问题不是导航，只要可能需要位置信息，就调用 get_current_location**
- 如果用户没有明确说明目的地，询问用户
- 搜索POI时，如果用户说"附近的加油站"，使用search_nearby_poi
- 如果用户说"搜索某某餐厅"，使用search_poi
- 返回结果要简洁清晰，突出重点信息（尤其是城市名称）
- 如果工具调用失败，说明具体错误原因并提供建议
"""),
    MessagesPlaceholder(variable_name="messages"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])


def create_navigation_agent():
    """创建 Navigation Agent"""
    # 注意：USE_VISION_MODEL_ALWAYS=true 时，这里会使用视觉模型
    llm = get_llm()

    # 加载导航MCP工具
    print("[Navigation Agent] 正在加载导航工具...")
    all_tools = mcp_manager.load_all_tools()

    # 过滤出导航相关工具
    navigation_tools = [tool for tool in all_tools if "sgm-navigation" in tool.name.lower() or any(
        keyword in tool.description.lower()
        for keyword in ["导航", "位置", "poi", "搜索", "navigation", "location", "search"]
    )]

    if not navigation_tools:
        print("[Navigation Agent] 警告: 未找到导航工具")
        return None

    print(f"[Navigation Agent] 导航工具加载完成，共 {len(navigation_tools)} 个工具")
    for tool in navigation_tools:
        print(f"  - {tool.name}: {tool.description[:60]}...")

    agent = create_tool_calling_agent(llm, navigation_tools, navigation_prompt)
    return AgentExecutor(agent=agent, tools=navigation_tools, verbose=True)


async def navigation_agent(state: AgentState) -> AgentState:
    """Navigation Agent: 处理导航任务（支持并行工具调用）"""

    messages = state["messages"]

    print(f"[Navigation Agent] 处理消息数量: {len(messages)}")
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

    print(f"[Navigation Agent] 清理后消息数量: {len(cleaned_messages)}")

    try:
        agent_executor = create_navigation_agent()

        if agent_executor is None:
            return {
                "messages": [
                    AIMessage(
                        content="抱歉，导航服务暂时不可用。请告诉我当前所在的城市或想查询的地点？"
                    )
                ],
                "completed_tasks": [],
            }

        # ✅ 使用 ainvoke 支持异步执行和并行工具调用
        result = await agent_executor.ainvoke({
            "messages": cleaned_messages,
        })

        return {
            "messages": [AIMessage(content=result["output"])],
            "completed_tasks": ["导航服务"],
        }

    except Exception as e:
        print(f"[Navigation Agent] 执行失败: {e}")
        import traceback
        traceback.print_exc()

        return {
            "messages": [
                AIMessage(
                    content=f"抱歉，导航服务出现错误：{str(e)}。请直接告诉我您的城市或想要查询的地点？"
                )
            ],
            "completed_tasks": [],
        }
