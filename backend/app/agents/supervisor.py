"""Supervisor Agent: 任务调度和路由"""
import json
from typing import Optional
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from ..state.agent_state import AgentState
from ..llm import get_llm

# Supervisor 的 Prompt
supervisor_prompt = ChatPromptTemplate.from_messages([
    ("system", """你是多智能体调度员，负责根据对话上下文安排下一步代理。

可用代理：
- weather：天气查询
- train：火车票查询
- navigation：定位与导航
- general：通用问答

输出 JSON：
{{
  "status": "complete | continue | needs_user_input",
  "next_agents": ["agent_name", ...],
  "reason": "简短中文说明"
}}

当 status 不是 "continue" 时，next_agents 必须为空；当 status 为 "continue" 时，按顺序列出需要执行的代理名称，可包含多个。
"""),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
])


def _extract_text(message: Optional[AIMessage]) -> str:
    """Safely extract string content from an AI message."""
    if message is None:
        return ""

    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content.strip()

    # 对于其他类型（如列表多模态内容）统一转为字符串
    return str(content).strip()


def _classify_last_ai_message(message: Optional[AIMessage]) -> Optional[str]:
    """根据最后一条AI消息内容判断任务状态."""
    text = _extract_text(message)
    if not text:
        return None

    question_suffixes = ("?", "？")
    user_input_hints = (
        "请提供", "需要您", "告诉我", "麻烦提供", "请选择", "想了解哪",
        "您希望我", "请问", "还想查询", "需要更多", "方便告知", "哪一天", "哪个时间",
    )
    error_hints = (
        "无法", "不可用", "失败", "未能", "出错", "错误", "很遗憾",
        "暂时不能", "暂时无法", "暂时不可用", "暂未", "没有找到", "未找到",
    )
    intermediate_hints = (
        "当前位置", "当前定位", "定位到", "位置：", "位置:", "经度", "纬度", "坐标",
        "正在为您查询", "正在查询", "继续为您", "正在获取", "正在处理", "处理中",
        "等待片刻", "稍等片刻", "马上为您", "准备查询", "正在搜索", "下一步", "继续处理",
        "继续为您办理", "已获取位置信息", "保持连接",
    )
    navigation_done_hints = (
        "导航已启动", "开始导航", "路线已经规划", "已为您规划路线", "已为您开始导航",
        "导航已经开始", "导航已为您启动",
    )
    weather_answer_hints = (
        "天气", "气温", "温度", "°", "℃", "摄氏度", "相对湿度", "风力", "风速",
        "降雨", "降水", "晴", "多云", "小雨", "阴", "空气质量", "紫外线",
    )
    train_answer_hints = (
        "车次", "列车", "余票", "发车", "到达", "票价", "硬座", "软卧", "二等座",
        "一等座", "商务座", "候补", "直达", "中转",
    )

    # 需要用户补充信息
    if text.endswith(question_suffixes):
        return "needs_user_input"
    if any(hint in text for hint in user_input_hints):
        return "needs_user_input"
    if any(hint in text for hint in error_hints):
        return "needs_user_input"

    # 中间步骤信息，继续执行
    if any(hint in text for hint in intermediate_hints):
        return "continue"
    if text.startswith("正在") or text.startswith("稍等"):
        return "continue"

    # 领域特定的完成信号
    if any(hint in text for hint in navigation_done_hints):
        return "complete"
    if any(hint in text for hint in weather_answer_hints):
        return "complete"
    if any(hint in text for hint in train_answer_hints):
        return "complete"

    # 默认视为完成，避免重复调用
    return "complete"


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
            # 支持多模态消息：如果content是列表，提取文本部分
            if isinstance(msg.content, str):
                last_user_message = msg.content
            elif isinstance(msg.content, list):
                # 提取所有文本部分
                text_parts = [item.get("text", "") for item in msg.content if isinstance(item, dict) and item.get("type") == "text"]
                last_user_message = " ".join(text_parts) if text_parts else "用户发送了图片"
            else:
                last_user_message = str(msg.content)
            break

    if not last_user_message:
        print("[Supervisor] 未找到用户消息，结束")
        return {
            "messages": [AIMessage(content="[Supervisor] 未找到用户消息")],
            "next_agents": [],
            "iteration_count": 0,
        }

    # 获取对话历史（最近10条，排除 Supervisor 的消息）
    # 注意：需要将多模态消息转换为纯文本，因为Supervisor使用DeepSeek（不支持image_url）
    chat_history = []
    for msg in messages[-10:]:
        if isinstance(msg, AIMessage) and isinstance(msg.content, str) and msg.content.startswith("[Supervisor]"):
            continue

        # 将多模态消息转换为纯文本消息（DeepSeek不支持image_url）
        if isinstance(msg.content, list):
            # 提取文本部分
            text_parts = [item.get("text", "") for item in msg.content if isinstance(item, dict) and item.get("type") == "text"]
            text_content = " ".join(text_parts) if text_parts else "[用户发送了图片]"

            # 创建纯文本消息
            if isinstance(msg, HumanMessage):
                chat_history.append(HumanMessage(content=text_content))
            else:
                chat_history.append(AIMessage(content=text_content))
        else:
            chat_history.append(msg)

    # 调试：打印Supervisor看到的对话历史
    print(f"[Supervisor DEBUG] 对话历史 (共{len(chat_history)}条):")
    for i, msg in enumerate(chat_history[-5:]):  # 只打印最后5条
        msg_type = "User" if isinstance(msg, HumanMessage) else "AI"

        # 安全地提取内容预览（支持多模态消息）
        if isinstance(msg.content, str):
            content_preview = msg.content[:100].replace("\n", " ")
        elif isinstance(msg.content, list):
            # 多模态消息，只提取文本部分
            text_parts = [item.get("text", "") for item in msg.content if isinstance(item, dict) and item.get("type") == "text"]
            content_preview = " ".join(text_parts)[:100].replace("\n", " ") if text_parts else "[包含图片]"
        else:
            content_preview = str(msg.content)[:100]

        print(f"  [{i}] {msg_type}: {content_preview}...")

    latest_user_idx = max(
        (idx for idx, msg in enumerate(chat_history) if isinstance(msg, HumanMessage)),
        default=-1,
    )

    last_ai_message = None
    last_ai_index = -1
    for idx in range(len(chat_history) - 1, latest_user_idx, -1):
        candidate = chat_history[idx]
        if isinstance(candidate, AIMessage):
            last_ai_message = candidate
            last_ai_index = idx
            break

    last_ai_status = _classify_last_ai_message(last_ai_message) if last_ai_message else None
    last_ai_text = _extract_text(last_ai_message)
    has_ai_message = last_ai_message is not None
    has_substantive_reply = last_ai_status == "complete"

    if last_ai_message:
        print(f"[Supervisor DEBUG] 最后一条AI消息索引: {last_ai_index} | 分类: {last_ai_status} | 内容: {last_ai_text[:80]}")
    else:
        print("[Supervisor DEBUG] 未检测到最新用户提问后的AI回复")

    # 如果Agent明确向用户提问，则等待用户输入
    if last_ai_status == "needs_user_input":
        print("[Supervisor] 检测到agent正在向用户询问信息，切换为 needs_user_input")
        return {
            "messages": [AIMessage(content="[Supervisor] 等待用户补充信息")],
            "next_agents": [],
            "iteration_count": 0,
        }

    # 如果Agent已经给出有效回复，则直接结束，避免重复路由
    if last_ai_status == "complete" and iteration_count > 0:
        print("[Supervisor] 检测到有效AI回复，直接complete以避免重复调用")
        return {
            "messages": [AIMessage(content="[Supervisor] 任务已完成（检测到有效回复）")],
            "next_agents": [],
            "iteration_count": 0,
        }

    # ✅ 保护机制2：防止无限循环 - 如果已经执行过2次且有实质性回复，强制结束
    if iteration_count >= 2 and has_substantive_reply:
        print(f"[Supervisor] ⚠️ 保护机制触发：已循环{iteration_count}次且有AI回复，强制complete")
        return {
            "messages": [AIMessage(content="[Supervisor] 任务已完成（循环保护）")],
            "next_agents": [],
            "iteration_count": 0,
        }

    # ✅ 保护机制3：检查completed_tasks，如果同类任务已完成，不再重复
    task_types_done = set(completed_tasks)
    print(f"[Supervisor] 已完成任务类型: {task_types_done}")

    # ✅ 保护机制4：如果是通用对话类型且已有回复，直接complete
    is_general_query = not any(
        keyword in last_user_message
        for keyword in ["天气", "weather", "火车", "车票", "12306", "导航", "位置", "回家", "去公司"]
    )
    if is_general_query and has_substantive_reply:
        print(f"[Supervisor] ⚠️ 保护机制触发：通用对话已有回复，强制complete")
        return {
            "messages": [AIMessage(content="[Supervisor] 通用对话已完成")],
            "next_agents": [],
            "iteration_count": 0,
        }

    # ✅ 保护机制5：防止LLM幻觉 - 如果没有AI回复却返回complete，强制纠正
    # 这是最关键的保护！防止LLM在第一次就错误地判断complete
    # 使用 LLM 进行路由决策
    # 注意：Supervisor强制使用文本模型（DeepSeek更擅长JSON输出，且不需要看图片）
    llm = get_llm(force_text=True)

    response = None
    try:
        formatted_messages = supervisor_prompt.format_messages(
            chat_history=chat_history,
            input=last_user_message
        )
        response = llm.invoke(formatted_messages)

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

        # ✅ 关键保护：验证LLM的complete判断
        # 如果LLM说complete，但对话历史中没有AI回复，这是幻觉，必须纠正！
        if status == "complete" and not has_substantive_reply:
            print(f"[Supervisor] ⚠️ LLM幻觉检测：LLM判断complete但无AI回复，强制continue")
            print(f"[Supervisor] LLM的理由: {reason}")
            # 强制调用general agent
            return {
                "messages": [AIMessage(content=f"[Supervisor] 路由到: general（纠正LLM幻觉）")],
                "next_agents": ["general"],
                "iteration_count": iteration_count + 1,
            }

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
        if response is not None and isinstance(getattr(response, "content", ""), str):
            print(f"[Supervisor] LLM 响应: {response.content[:200]}")

        # 关键词匹配（保守策略：只返回单个agent）
        weather_keywords = ["天气", "weather", "温度", "明天", "后天", "今天", "降雨", "下雨", "冷", "热", "风"]
        train_keywords = ["火车", "车票", "高铁", "动车", "列车", "12306", "余票", "车次"]
        navigation_keywords = ["导航", "位置", "poi", "搜索", "回家", "去公司", "路线", "目的地", "附近", "加油站", "充电站", "停车场"]

        if any(keyword in last_user_message for keyword in train_keywords):
            next_agents = ["train"]
        elif any(keyword in last_user_message for keyword in weather_keywords):
            # 如果是天气查询且没有收到过AI回复，先获取位置
            if not has_ai_message:
                next_agents = ["navigation"]
            elif last_ai_status == "continue":
                next_agents = ["weather"]
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
