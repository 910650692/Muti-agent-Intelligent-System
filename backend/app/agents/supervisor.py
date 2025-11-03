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
- weather: 查询天气信息（天气、温度、降雨、风力等气象相关）**需要城市信息**
- train: 查询火车票信息（12306车票查询、余票、列车时刻、中转等）**需要出发地、目的地、日期**
- navigation: 车载导航服务（获取位置、搜索POI、路线规划、启动导航、回家/去公司等）
- general: 通用对话（知识问答、日常对话、闲聊等）

你的职责：
1. 分析用户的原始问题和当前对话状态
2. 判断任务的完成状态
3. **识别任务依赖关系，按正确顺序执行**
4. 决定下一步行动

**任务状态判断（核心）**：

状态1️⃣ **complete** - 任务已完成
- 用户的问题已经得到完整、满意的回答
- 示例：
  * 用户问"今天天气" → Agent返回"上海今天25°C晴天" → complete
  * 用户问"上海到杭州的车票" → Agent返回车次列表 → complete

状态2️⃣ **needs_user_input** - 需要用户补充信息
- 任务进行中，但需要用户做选择或补充信息才能继续
- Agent已经提供了部分结果，并明确询问用户
- 示例：
  * 用户问"晴天去杭州的车票" → Weather查到3个晴天 → 问用户"您想查哪天？" → needs_user_input
  * 用户问"上海到杭州" → Train问"出发日期？" → needs_user_input
  * Agent返回多个选项并询问"您比较倾向于哪个？" → needs_user_input

状态3️⃣ **continue** - 继续执行下一步
- 任务未完成，但已有足够信息，可以自动继续
- 无需用户干预，系统可以自主完成下一步
- 示例：
  * 用户问"今天天气" → Navigation获取位置"上海" → continue → Weather查询天气
  * 用户问"晴天去杭州" → Weather查到"明天晴" → continue → Train查明天车票

**关键判断逻辑**：

判断是 **continue** 还是 **needs_user_input**？
- ✅ continue: Agent只是提供了中间数据（如位置），没有询问用户，可以自动进行下一步
- ✅ needs_user_input: Agent提供了选项/结果，并明确询问用户选择或补充信息

判断是 **complete** 还是 **needs_user_input**？
- ✅ complete: Agent回答了用户的完整问题，没有遗留疑问
- ✅ needs_user_input: Agent的回复以问句结尾，或列出选项等待用户选择

**依赖关系处理（关键！）**：
- 如果任务需要多个Agent且有依赖关系 → **先执行前置Agent**，状态设为continue
- 如果任务需要多个Agent且无依赖关系 → 可以并行执行（next_agents包含多个）

**常见依赖关系**：
1. **天气查询需要位置**：
   - 用户问"今天天气" 且 对话历史中**没有**Navigation返回的位置 → 先调用navigation获取位置（status=continue）
   - 对话历史中**有**Navigation返回的位置，但**没有**Weather返回的天气数据 → 调用weather查询天气（status=continue）
   - 对话历史中**已有**Weather返回的完整天气信息（温度、湿度、天气状况等） → 任务完成（status=complete）

2. **火车票查询需要日期**：
   - 用户问"晴天去杭州的车票" → 先调用weather查询晴天日期（status=continue）
   - Weather返回晴天日期 → 调用train查询车票（status=continue）
   - 如果有多个晴天 → 询问用户选择（status=needs_user_input）

**判断当前缺少什么信息**：
- **仔细检查对话历史**中最近的AI回复内容
- 如果用户问"今天天气"：
  * 检查是否有包含"温度"、"°C"、"天气"、"晴"、"雨"等关键词的AI回复
  * 如果**有**这些关键词 → 天气已查询完成（status=complete）
  * 如果**没有**天气数据，但有"位置"、"上海"、"北京"等城市信息 → 调用weather（status=continue）
  * 如果**既没有**天气数据也没有位置 → 调用navigation（status=continue）

**路由规则：**
- 火车票、车次、12306、高铁、动车、列车等 → train
- 天气、温度、降雨、气象、晴天、下雨等 → weather
- 导航、位置、POI、搜索地点、回家、去公司、路线、目的地、附近的、加油站、充电站、停车场等 → navigation
- 其他通用问题 → general
- **多个独立需求 → 返回多个agents（并行执行）**

返回 JSON 格式:
{{
    "next_agents": ["agent1", "agent2"],  // 下一步要调用的Agent（可以为空）
    "status": "complete",                  // complete / needs_user_input / continue
    "reason": "原因说明"
}}

注意:
- **仔细分析对话历史**，理解用户的原始问题和当前进度
- **区分"Agent完成子任务"和"整体任务完成"**
- 如果status是complete或needs_user_input，next_agents应该为空
- 如果status是continue，next_agents必须包含至少一个Agent
"""),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
])


def supervisor_agent(state: AgentState) -> AgentState:
    """Supervisor: 任务分析和路由（三状态模型：complete / needs_user_input / continue）"""

    messages = state["messages"]
    completed_tasks = state.get("completed_tasks", [])
    iteration_count = state.get("iteration_count", 0)

    # 循环次数限制（防止死循环）
    MAX_ITERATIONS = 10
    if iteration_count >= MAX_ITERATIONS:
        print(f"[Supervisor] 达到最大循环次数 {MAX_ITERATIONS}，强制结束")
        return {
            "messages": [AIMessage(content="[Supervisor] 已达到最大处理次数")],
            "next_agents": [],
            "iteration_count": iteration_count,
        }

    # 获取最后一条用户消息（作为当前任务的输入）
    last_user_message = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content
            break

    if not last_user_message:
        print("[Supervisor] 未找到用户消息，结束")
        return {
            "messages": [AIMessage(content="[Supervisor] 未找到用户消息")],
            "next_agents": [],
            "iteration_count": 0,
        }

    # 获取对话历史（最近10条，排除 Supervisor 的消息）
    chat_history = []
    for msg in messages[-10:]:
        if isinstance(msg, AIMessage) and msg.content.startswith("[Supervisor]"):
            continue
        chat_history.append(msg)

    # 调试：打印Supervisor看到的对话历史
    print(f"[Supervisor DEBUG] 对话历史 (共{len(chat_history)}条):")
    for i, msg in enumerate(chat_history[-5:]):  # 只打印最后5条
        msg_type = "User" if isinstance(msg, HumanMessage) else "AI"
        content_preview = msg.content[:100].replace("\n", " ")
        print(f"  [{i}] {msg_type}: {content_preview}...")

    # 使用 LLM 进行路由决策
    llm = get_llm()

    try:
        response = llm.invoke(supervisor_prompt.format_messages(
            chat_history=chat_history,
            input=last_user_message
        ))

        # 清理LLM响应中的markdown代码块标记
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]  # 移除开头的 ```json
        if content.startswith("```"):
            content = content[3:]  # 移除开头的 ```
        if content.endswith("```"):
            content = content[:-3]  # 移除结尾的 ```
        content = content.strip()

        # 解析 JSON 响应（新格式：next_agents + status + reason）
        result = json.loads(content)
        next_agents = result.get("next_agents", [])
        status = result.get("status", "complete")  # 默认complete
        reason = result.get("reason", "未提供原因")

        print(f"[Supervisor] 路由决策 (循环: {iteration_count + 1}):")
        print(f"  - next_agents: {next_agents}")
        print(f"  - status: {status}")
        print(f"  - reason: {reason}")

        # 根据状态决定下一步
        if status == "complete" or status == "needs_user_input":
            # 任务完成或需要用户输入，停止循环
            print(f"[Supervisor] 任务状态: {status}，结束路由")
            return {
                "messages": [AIMessage(content=f"[Supervisor] 路由到: finish ({status})")],
                "next_agents": [],
                "iteration_count": 0,
            }
        elif status == "continue":
            # 继续执行下一步
            if not next_agents:
                print("[Supervisor] 警告: status=continue 但 next_agents 为空，强制结束")
                return {
                    "messages": [AIMessage(content="[Supervisor] 路由错误: continue但无agent")],
                    "next_agents": [],
                    "iteration_count": 0,
                }

            new_iteration_count = iteration_count + 1
            return {
                "messages": [AIMessage(content=f"[Supervisor] 路由到: {', '.join(next_agents)}")],
                "next_agents": next_agents,
                "iteration_count": new_iteration_count,
            }
        else:
            # 未知状态，默认结束
            print(f"[Supervisor] 未知状态: {status}，默认结束")
            return {
                "messages": [AIMessage(content=f"[Supervisor] 未知状态: {status}")],
                "next_agents": [],
                "iteration_count": 0,
            }

    except (json.JSONDecodeError, KeyError) as e:
        # 如果 LLM 返回格式不对，降级到关键词匹配
        print(f"[Supervisor] LLM 路由失败，降级到关键词匹配: {e}")
        print(f"[Supervisor] LLM 响应: {response.content[:200]}")

        # 关键词匹配（保守策略：只返回单个agent）
        weather_keywords = ["天气", "weather", "温度", "明天", "后天", "今天", "降雨", "下雨", "冷", "热", "风"]
        train_keywords = ["火车", "车票", "高铁", "动车", "列车", "12306", "余票", "车次"]
        navigation_keywords = ["导航", "位置", "poi", "搜索", "回家", "去公司", "路线", "目的地", "附近", "加油站", "充电站", "停车场"]

        # 检查是否是第一次路由（没有AI回复）
        has_ai_response = any(isinstance(msg, AIMessage) and not msg.content.startswith("[Supervisor]") for msg in messages)

        if any(keyword in last_user_message for keyword in train_keywords):
            next_agents = ["train"]
        elif any(keyword in last_user_message for keyword in weather_keywords):
            # 如果是天气查询且没有收到过AI回复，先获取位置
            if not has_ai_response:
                next_agents = ["navigation"]
            else:
                next_agents = ["weather"]
        elif any(keyword in last_user_message for keyword in navigation_keywords):
            next_agents = ["navigation"]
        else:
            next_agents = ["general"]

        print(f"[Supervisor] 降级路由: {next_agents}")

        new_iteration_count = iteration_count + 1
        return {
            "messages": [AIMessage(content=f"[Supervisor] 路由到: {', '.join(next_agents)} (关键词匹配)")],
            "next_agents": next_agents,
            "iteration_count": new_iteration_count,
        }
