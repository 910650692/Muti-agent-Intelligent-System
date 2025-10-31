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

**新特性：支持并行执行多个Agent**
如果用户的问题需要多个Agent协作完成，你可以一次性返回多个Agent，它们会并行执行！

路由逻辑:
1. **首先检查最后一条消息是否是用户消息（HumanMessage）**
   - 如果最后一条是AI回复（AIMessage）→ 说明Agent刚回复完成
     - 如果AI回复包含核心数据（车次、天气等）→ finish，等待用户反馈
     - 如果AI回复只是询问缺失信息（如"请问出发城市？"）→ finish，等待用户补充
   - 如果最后一条是用户消息（HumanMessage）→ 需要判断是否需要路由
     - 明确满意："好的"、"谢谢"、"不用了" → finish
     - 追问细化："虹桥的"、"便宜点的"、"下午的" → 路由到对应Agent
     - 补充信息："上海"、"明天" → 路由到对应Agent
     - 新需求："还有..."、"再查..." → 路由到对应Agent

2. **关键判断：如何识别Agent是在"等待用户输入"？**
   - ✅ Agent回复以问句结尾（"您比较倾向于..."、"需要预订吗？"）→ finish
   - ✅ Agent已提供核心数据（车次列表、天气信息）→ finish
   - ❌ Agent回复没有提供核心数据，只是说"正在查询..." → 不应该出现，需要检查Agent实现

3. **什么时候继续路由？**
   - 仅当用户有新问题/追问/补充信息时
   - 用户明确不满意或要求细化筛选时

**重要：如何识别用户的多个需求？**
分析用户的**完整意图**，而不是只看表面关键词：

示例1 - 复合需求（并行）：
用户: "晴天从上海去杭州玩，下午到达"
分析:
  - "晴天" → 需要查天气判断是否晴天
  - "下午到达" → 需要查火车票筛选下午到达的车次
结果: {{"agents": ["weather", "train"], "reason": "需要同时查询天气和火车票"}}

示例2 - 复合需求（并行）：
用户: "明天上海会下雨吗？如果下雨我就坐高铁去南京"
分析:
  - "明天上海会下雨吗" → 查天气
  - "坐高铁去南京" → 查火车票
结果: {{"agents": ["weather", "train"], "reason": "需要天气信息和火车票信息"}}

示例3 - 单一需求（天气agent内部并行）：
用户: "上海、北京、深圳的天气"
分析: 只需要天气信息，weather agent会自动并行查询多个城市
结果: {{"agents": ["weather"], "reason": "查询多个城市天气"}}

示例4 - Agent询问等待用户（finish）：
用户: "虹桥站出发的车次"
历史: [Train Agent回复: "找到以下虹桥站出发的车次...G99、G1499等。您比较倾向于哪个时间段和票价范围呢？"]
当前状态: 最后一条是AI回复，且包含问句
分析:
  - ✅ 最后一条是AI回复
  - ✅ Agent已提供核心数据（车次列表）
  - ✅ Agent询问用户偏好（等待用户输入）
结果: {{"agents": [], "reason": "Agent已回复并等待用户选择，finish"}}

示例5 - 用户追问细化（继续路由）：
用户最初: "上海到杭州的火车票"
历史: [Train Agent回复: "找到车次...您比较倾向于哪个时间段？"]
用户追问: "下午的"
当前状态: 最后一条是用户消息
分析:
  - ✅ 最后一条是用户消息（追问）
  - 用户提供了筛选条件（"下午的"）
  - 需要重新查询满足条件的车次
结果: {{"agents": ["train"], "reason": "用户追问细化需求，重新查询"}}

示例6 - 用户满意（finish）：
用户: "上海到杭州的火车票"
历史: [Train Agent回复: "为您查到以下车次: G7533..., G99..."]
用户: "好的，谢谢"
分析:
  - 用户明确表示满意（"好的"、"谢谢"）
  - 没有新的查询需求
结果: {{"agents": [], "reason": "用户满意，对话结束"}}

示例7 - AI回复完成（finish）：
用户: "今天几号？"
历史: [General Agent回复: "今天是2025年10月31日"]
当前状态: 最后一条是AI回复
分析:
  - ✅ 最后一条是AI回复
  - ✅ 问题已完整回答
结果: {{"agents": [], "reason": "AI已回复完成，等待用户反馈"}}

**路由规则：**
- 火车票、车次、12306、高铁、动车、列车等 → train
- 天气、温度、降雨、气象、晴天、下雨等 → weather
- 其他通用问题 → general
- **多个独立需求 → 返回多个agents（并行执行）**

返回 JSON 格式:
{{"agents": ["agent1", "agent2", ...], "reason": "原因"}}

注意:
- agents 是数组，可以包含0个（finish）、1个或多个agent名称
- **最后一条消息类型是关键：AI回复→finish，用户消息→判断是否路由**
- **Agent询问用户时（问句结尾）→ finish，等待用户回复**
- 区分"Agent等待用户选择"和"用户追问细化"
- 仔细分析用户的**完整意图**，识别所有需求
"""),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
])


def supervisor_agent(state: AgentState) -> AgentState:
    """Supervisor: 任务分析和路由（支持并行Agent执行）"""

    messages = state["messages"]
    completed_tasks = state.get("completed_tasks", [])
    iteration_count = state.get("iteration_count", 0)

    # 循环次数限制（防止死循环）
    MAX_ITERATIONS = 10
    if iteration_count >= MAX_ITERATIONS:
        print(f"[Supervisor] 达到最大循环次数 {MAX_ITERATIONS}，强制结束")
        return {
            "messages": [AIMessage(content="[Supervisor] 已达到最大处理次数")],
            "next_agents": [],  # ✅ 返回空列表表示finish
            "completed_tasks": completed_tasks,
            "thread_id": state["thread_id"],
            "iteration_count": iteration_count,
        }

    # ✅ 检查最后一条消息类型
    last_message = messages[-1] if messages else None
    is_last_human = isinstance(last_message, HumanMessage)

    # 如果最后一条是AI回复，说明Agent刚完成回复，应该finish等待用户
    if not is_last_human:
        print(f"[Supervisor] 最后一条是AI回复，finish等待用户")
        return {
            "messages": [AIMessage(content="[Supervisor] 路由到: finish")],
            "next_agents": [],
            "iteration_count": 0,
        }

    # 获取最后一条用户消息（用于路由决策）
    last_user_message = last_message.content

    # 获取对话历史（最近10条，排除 Supervisor 的消息）
    chat_history = []
    for msg in messages[-10:]:
        if isinstance(msg, AIMessage) and msg.content.startswith("[Supervisor]"):
            continue
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
        next_agents = result.get("agents", [])  # ✅ 获取agents列表
        reason = result.get("reason", "未提供原因")

        print(f"[Supervisor] 路由决策: {next_agents} (循环: {iteration_count + 1})")
        print(f"[Supervisor] 原因: {reason}")

    except (json.JSONDecodeError, KeyError) as e:
        # 如果 LLM 返回格式不对，降级到关键词匹配
        print(f"[Supervisor] LLM 路由失败，降级到关键词匹配: {e}")

        # 关键词匹配（保守策略：只返回单个agent）
        weather_keywords = ["天气", "weather", "温度", "明天", "后天", "今天", "降雨", "下雨", "冷", "热", "风"]
        train_keywords = ["火车", "车票", "高铁", "动车", "列车", "12306", "余票", "车次"]

        if any(keyword in last_user_message for keyword in train_keywords):
            next_agents = ["train"]
            reason = "关键词匹配（火车票）"
        elif any(keyword in last_user_message for keyword in weather_keywords):
            next_agents = ["weather"]
            reason = "关键词匹配（天气）"
        else:
            next_agents = ["general"]
            reason = "默认路由"

        print(f"[Supervisor] 降级路由: {next_agents}")

    # 如果决策是空列表（finish），重置计数器和任务列表；否则递增
    if not next_agents:  # ✅ 空列表表示finish
        return {
            "messages": [AIMessage(content="[Supervisor] 路由到: finish")],
            "next_agents": [],
            "iteration_count": 0,
        }
    else:
        new_iteration_count = iteration_count + 1

        # ✅ 额外检查：避免重复路由到已完成的agent
        # 如果所有next_agents都已经在completed_tasks中，强制finish
        if all(
            any(agent in task for task in completed_tasks)
            for agent in next_agents
        ):
            print(f"[Supervisor] 警告：所有agents {next_agents} 已执行过，强制finish避免循环")
            return {
                "messages": [AIMessage(content="[Supervisor] 路由到: finish (避免重复)")],
                "next_agents": [],
                "iteration_count": 0,
            }

        return {
            "messages": [AIMessage(content=f"[Supervisor] 路由到: {', '.join(next_agents)}")],
            "next_agents": next_agents,
            "iteration_count": new_iteration_count,
        }
