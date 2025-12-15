"""单Agent ReAct架构实现"""
import asyncio
import json
from typing import List, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langchain_core.messages.tool import ToolCall

from ..state.agent_state import AgentState
from ..llm import get_llm
from ..mcp.manager import mcp_manager
from ..tools.weather_tools import weather_tools
from .system_prompt import get_system_prompt


class NavigationAgent:
    """导航专用的单Agent ReAct架构

    工作流程：
    1. Reasoning: LLM分析用户需求，决定是否需要工具
    2. Action: 并行执行工具（如果需要）
    3. 循环：观察工具结果，继续推理
    4. 结束：输出最终答案
    """

    def __init__(self, checkpointer=None, memory=None):
        """初始化Agent

        Args:
            checkpointer: LangGraph checkpointer实例（如AsyncSqliteSaver），用于保存会话状态
            memory: Mem0 Memory实例，用于长期记忆管理
        """
        print("[NavigationAgent] 初始化单Agent ReAct架构...")

        self.system_prompt = get_system_prompt()
        self.tools = self._load_all_tools()
        self.checkpointer = checkpointer
        self.memory = memory  # ✅ 保存memory实例
        self.app = self._build_graph()

        print(f"[NavigationAgent] 初始化完成，共加载 {len(self.tools)} 个工具")
        if self.memory:
            print("[NavigationAgent] ✅ Mem0长期记忆已启用")

    def _load_all_tools(self) -> List[BaseTool]:
        """加载所有工具"""
        tools = []

        # 1. 加载MCP工具
        print("[NavigationAgent] 正在加载MCP工具...")
        mcp_tools = mcp_manager.load_all_tools()
        tools.extend(mcp_tools)
        print(f"[NavigationAgent] 加载了 {len(mcp_tools)} 个MCP工具")

        # 2. 加载天气工具
        tools.extend(weather_tools)
        print(f"[NavigationAgent] 加载了 {len(weather_tools)} 个天气工具")

        # 3. 未来可以添加更多工具
        # tools.extend(search_tools)

        return tools

    @staticmethod
    def _sanitize_messages_for_text_model(messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        清理消息列表，将图片替换为占位符，供文本模型使用

        目的：
        - DeepSeek等文本模型不支持 image_url 格式，会报400错误
        - 但我们需要保留上下文，让文本模型知道"这里曾经有图片"

        策略：
        - 将 {"type": "image_url", ...} 替换为占位符 "[用户发送了图片]"
        - 保留所有文本内容
        - 保留消息结构和顺序

        Args:
            messages: 原始消息列表（可能包含图片）

        Returns:
            清理后的消息列表（纯文本 + 占位符）
        """
        cleaned = []

        for msg in messages:
            # 检查消息内容格式
            if hasattr(msg, 'content') and isinstance(msg.content, list):
                # 多模态格式（列表），需要提取文本并添加占位符
                texts = []
                has_image = False

                for item in msg.content:
                    if isinstance(item, dict):
                        if item.get('type') == 'text':
                            # 保留文本内容
                            texts.append(item.get('text', ''))
                        elif item.get('type') in ['image_url', 'image']:
                            # 检测到图片
                            has_image = True

                # 重建消息内容：占位符 + 文本
                text_content = ' '.join(texts).strip()
                if has_image:
                    # 在文本前添加占位符
                    text_content = "[用户发送了图片] " + text_content

                # 创建新消息（保持原消息类型）
                if text_content:
                    # ⚠️ 关键修复：如果原始消息包含 tool_calls，需要保留
                    # 否则会导致消息序列不合法（ToolMessage 前必须有对应的 tool_calls）
                    if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                        new_msg = AIMessage(content=text_content, tool_calls=msg.tool_calls)
                    else:
                        new_msg = msg.__class__(content=text_content)
                    cleaned.append(new_msg)

            else:
                # 纯文本消息或其他格式，直接保留
                cleaned.append(msg)

        return cleaned

    def _build_graph(self):
        """构建ReAct工作流

        流程：
        reasoning → (需要工具?)
            └─ 是 → action → reasoning (循环)
            └─ 否 → END
        """
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("reasoning", self.call_model)
        workflow.add_node("action", self.call_tools)

        # 设置入口点：直接从推理开始
        workflow.set_entry_point("reasoning")

        # 条件边：reasoning → 需要工具？
        workflow.add_conditional_edges(
            "reasoning",
            self.should_continue,
            {
                "action": "action",  # 需要工具
                END: END             # 不需要，结束
            }
        )

        # 循环边：action → reasoning（观察结果后继续思考）
        workflow.add_edge("action", "reasoning")

        # ✅ 编译工作流，传入checkpointer以支持会话状态持久化
        return workflow.compile(checkpointer=self.checkpointer)

    async def call_model(self, state: AgentState, config: RunnableConfig | None = None) -> dict:
        """推理节点：LLM分析和决策

        支持两种模式：
        1. 单阶段推理（纯文本）：文本模型+工具
        2. 两阶段推理（多模态）：
           - 阶段1: VL模型理解图片
           - 阶段2: 文本模型基于理解结果调用工具

        Args:
            state: 当前状态
            config: 运行配置

        Returns:
            包含新消息的字典
        """
        messages = state["messages"]

        print(f"\n[Reasoning] 开始推理，当前消息数: {len(messages)}")

        # ✅ 智能选择LLM（自动检测是否有图片）
        from ..llm import has_image_content, _extract_text_from_message, _check_message_has_image

        # ✅ 查询Mem0长期记忆
        memory_context = ""
        if self.memory and config:
            try:
                user_id = config.get("configurable", {}).get("user_id", "default")

                # 提取最新用户消息
                latest_query = ""
                for msg in reversed(messages):
                    if hasattr(msg, 'type') and msg.type == 'human':
                        latest_query = _extract_text_from_message(msg)
                        break

                if latest_query:
                    # 查询相关记忆（限制5条）
                    relevant_memories = self.memory.search(
                        query=latest_query,
                        user_id=user_id,
                        limit=5
                    )

                    # ✅ 调试：打印返回类型
                    print(f"[Memory DEBUG] 查询返回类型: {type(relevant_memories)}")
                    print(f"[Memory DEBUG] 查询返回内容: {relevant_memories}")

                    if relevant_memories:
                        # ✅ 兼容不同的返回格式
                        memory_facts = []

                        # 如果返回的是 {'results': [...]}
                        if isinstance(relevant_memories, dict) and 'results' in relevant_memories:
                            results = relevant_memories['results']

                            for m in results:
                                if isinstance(m, dict):
                                    # 尝试多个可能的字段名
                                    fact = (m.get('memory') or
                                           m.get('text') or
                                           m.get('content') or
                                           m.get('data') or
                                           str(m))
                                    if fact and fact != str(m):
                                        memory_facts.append(fact)
                                elif isinstance(m, str):
                                    memory_facts.append(m)

                        # 如果是列表（旧格式兼容）
                        elif isinstance(relevant_memories, list):
                            for m in relevant_memories:
                                if isinstance(m, dict):
                                    fact = m.get('memory', '') or m.get('text', '') or m.get('content', '')
                                    if fact:
                                        memory_facts.append(fact)
                                elif isinstance(m, str):
                                    memory_facts.append(m)

                        if memory_facts:
                            memory_context = "\n".join(f"- {fact}" for fact in memory_facts)
                            print(f"[Memory] 查询到 {len(memory_facts)} 条相关记忆")
                        else:
                            print(f"[Memory] 查询返回空结果（可能没有相关记忆或记忆未保存成功）")
            except Exception as e:
                print(f"[Memory] 查询失败（降级为无记忆模式）: {e}")
                import traceback
                traceback.print_exc()

        # 判断是否需要多模态推理
        # 条件：最新消息是 HumanMessage 且包含图片
        # 排除：ReAct循环中的 ToolMessage（工具返回结果后的推理）
        latest_message = messages[-1] if messages else None
        is_latest_human_with_image = (
            latest_message and
            hasattr(latest_message, 'type') and
            latest_message.type == 'human' and
            _check_message_has_image(latest_message)
        )

        # ==================== 两阶段推理（多模态场景） ====================
        if is_latest_human_with_image:
            print("[Reasoning] 🔄 启动智能两阶段推理")

            # === 阶段1: 视觉理解 + 意图判断 ===
            print("[Reasoning] 📷 阶段1: 使用VL模型理解图片并判断意图")
            vl_model = get_llm(messages=messages, force_vision=True)

            # 增强的System Prompt：让VL模型自主判断是否需要工具
            vision_system_prompt = """你是一个智能视觉助手。请分析图片内容并理解用户需求。

**任务：**
1. 详细描述图片中的内容（包括文字、物体、场景等关键信息）
2. 理解用户的真实意图

**意图判断：**
- 如果用户只是想了解图片内容（如"这是什么"、"识别一下"、"有几个"等），直接回答即可
- 如果用户需要执行具体操作（如"导航到这里"、"查询信息"、"帮我订票"、"搜索附近"等），请在回答最后添加标记：[NEED_TOOLS]

**示例：**
用户："这是什么？" → 回答："这是两只可爱的小猫咪"（不加标记）
用户："导航到这里" → 回答："这是延安高架虹桥枢纽出口 [NEED_TOOLS]"（添加标记）
用户："帮我查附近加油站" → 回答："图片显示当前位置在市中心区域 [NEED_TOOLS]"（添加标记）
"""
            # ✅ 注入Mem0记忆
            if memory_context:
                vision_system_prompt += f"""

**用户长期记忆**：
{memory_context}

请结合用户的长期记忆提供个性化服务。
"""

            # 构建视觉理解的消息（包含图片）
            vision_messages = [
                SystemMessage(content=vision_system_prompt),
                *messages
            ]

            # VL模型推理（不绑定工具）
            vision_chunk = None
            async for chunk in vl_model.astream(vision_messages, config=config):
                vision_chunk = chunk if vision_chunk is None else (vision_chunk + chunk)

            if vision_chunk is None:
                print("[Reasoning] ⚠️ 阶段1失败：VL模型未返回内容")
                return {
                    "messages": [AIMessage(content="抱歉，无法识别图片内容，请重新上传。")]
                }

            vision_understanding = getattr(vision_chunk, "content", "") or ""
            print(f"[Reasoning] ✅ 阶段1完成，图片理解: {vision_understanding[:100]}...")

            # 检测是否需要进入阶段2（多种检测方式）
            TOOL_MARKER = "[NEED_TOOLS]"
            # ✅ 增强检测：不仅检查标记，还检查是否包含工具调用相关关键词
            TOOL_KEYWORDS = ["<tool_call>", "tool_call", "规划路线", "搜索", "查询", "订票", "导航"]
            needs_tools = (
                TOOL_MARKER in vision_understanding or
                any(keyword in vision_understanding for keyword in TOOL_KEYWORDS)
            )

            if not needs_tools:
                # 纯图片问答，直接返回VL模型的回答
                print("[Reasoning] 💬 判断：纯图片问答，无需工具，直接返回")
                content = vision_understanding
                tool_calls = None
            else:
                # 需要工具，进入阶段2
                print("[Reasoning] 🛠️  判断：需要执行操作，进入阶段2")

                # 去掉工具相关标记和标签，保留纯净的理解结果
                import re
                vision_understanding_clean = vision_understanding.replace(TOOL_MARKER, "")
                # 去掉 <tool_call>...</tool_call> 标签
                vision_understanding_clean = re.sub(r'<tool_call>.*?</tool_call>', '', vision_understanding_clean, flags=re.DOTALL)
                vision_understanding_clean = vision_understanding_clean.strip()
                print(f"[Reasoning] 清理后的理解: {vision_understanding_clean[:100]}...")

                # === 阶段2: 任务执行（文本模型+工具） ===
                print("[Reasoning] 🛠️  阶段2: 使用文本模型+工具执行任务")
                text_model = get_llm(force_text=True)
                model_with_tools = text_model.bind_tools(self.tools)

                # 提取最新用户消息的文本部分（用户的原始问题）
                latest_user_text = ""
                for msg in reversed(messages):
                    if hasattr(msg, 'type') and msg.type == 'human':
                        latest_user_text = _extract_text_from_message(msg)
                        break

                # 构建第二阶段的消息：历史（清理图片）+ 图片理解结果 + 用户问题
                # 清理历史消息中的图片
                cleaned_history = self._sanitize_messages_for_text_model(messages[:-1]) if len(messages) > 1 else []

                # 组合消息：图片理解 + 用户需求（使用清理后的理解结果）
                enhanced_message = f"""[图片内容理解]
{vision_understanding_clean}

[用户需求]
{latest_user_text if latest_user_text else "请根据图片内容提供帮助"}"""

                # ✅ 注入Mem0记忆到system prompt
                enhanced_system_prompt = self.system_prompt
                if memory_context:
                    enhanced_system_prompt = f"""{self.system_prompt}

**用户长期记忆**：
{memory_context}

请结合用户的长期记忆提供个性化服务。
"""

                task_messages = [
                    SystemMessage(content=enhanced_system_prompt),
                    *cleaned_history,
                    HumanMessage(content=enhanced_message)
                ]

                # 文本模型推理（绑定工具）
                task_chunk = None
                async for chunk in model_with_tools.astream(task_messages, config=config):
                    task_chunk = chunk if task_chunk is None else (task_chunk + chunk)

                if task_chunk is None:
                    print("[Reasoning] ⚠️ 阶段2失败：文本模型未返回内容")
                    return {
                        "messages": [AIMessage(content=vision_understanding_clean)]
                    }

                # 提取最终结果
                content = getattr(task_chunk, "content", "") or ""
                tool_calls = getattr(task_chunk, "tool_calls", None)

                # ✅ 修复空content问题：如果LLM只返回tool_calls没有content，用VL理解填充
                if not content and tool_calls:
                    content = vision_understanding_clean
                    print("[Reasoning] ✅ 阶段2完成（LLM返回空content，使用VL理解文本）")
                else:
                    print(f"[Reasoning] ✅ 阶段2完成")

                print(f"[Reasoning DEBUG] 内容长度: {len(content)}")
                print(f"[Reasoning DEBUG] 内容预览: {content[:100] if content else '(空)'}")

        # ==================== 单阶段推理（纯文本场景） ====================
        else:
            print("[Reasoning] 📝 单阶段推理: 纯文本模式")
            text_model = get_llm(force_text=True)  # ✅ 强制使用文本模型（避免历史图片干扰）
            model_with_tools = text_model.bind_tools(self.tools)

            # 清理历史消息中的图片（如果有的话）
            messages_to_send = self._sanitize_messages_for_text_model(messages)

            # ✅ 注入Mem0记忆到system prompt
            enhanced_system_prompt = self.system_prompt
            if memory_context:
                enhanced_system_prompt = f"""{self.system_prompt}

**用户长期记忆**：
{memory_context}

请结合用户的长期记忆提供个性化服务。
"""

            # 构建完整的消息
            full_messages = [
                SystemMessage(content=enhanced_system_prompt),
                *messages_to_send
            ]

            # 推理
            print(f"[Reasoning DEBUG] 发送消息给LLM，消息数: {len(full_messages)}")
            # 打印消息内容摘要
            for i, msg in enumerate(full_messages):
                msg_type = msg.__class__.__name__
                content_preview = str(msg.content)[:100] if hasattr(msg, 'content') else "N/A"
                print(f"[Reasoning DEBUG]   [{i}] {msg_type}: {content_preview}...")

            merged_chunk = None
            try:
                async for chunk in model_with_tools.astream(full_messages, config=config):
                    merged_chunk = chunk if merged_chunk is None else (merged_chunk + chunk)
                print("[Reasoning DEBUG] LLM流式输出完成")
            except Exception as e:
                print(f"[Reasoning] ⚠️ LLM调用异常: {e}")
                import traceback
                traceback.print_exc()
                return {
                    "messages": [AIMessage(content=f"抱歉，处理请求时出错: {e}")]
                }

            if merged_chunk is None:
                print("[Reasoning] ⚠️ LLM未返回任何内容")
                return {}

            # 提取结果
            content = getattr(merged_chunk, "content", "") or ""
            tool_calls = getattr(merged_chunk, "tool_calls", None)

            print(f"[Reasoning DEBUG] LLM返回内容长度: {len(content)}")
            print(f"[Reasoning DEBUG] 内容预览: {content[:100] if content else '(空)'}")

        # ==================== 构建AI消息（两种模式共用） ====================
        if not content and not tool_calls:
            print("[Reasoning] ⚠️ 返回空内容")
            content = "抱歉，我无法处理这个请求。"

        ai_message = AIMessage(
            content=content,
            tool_calls=tool_calls if tool_calls else []
        )

        # 打印决策信息
        if tool_calls:
            tool_names = [call["name"] for call in tool_calls]
            print(f"[Reasoning] 🎯 决策: 需要调用 {len(tool_calls)} 个工具: {tool_names}")
        else:
            print(f"[Reasoning] 💬 决策: 直接回答用户")

        # ✅ 保存对话到Mem0（只在有实际内容且无工具调用时保存，避免保存中间状态）
        if self.memory and config and content and not tool_calls:
            try:
                user_id = config.get("configurable", {}).get("user_id", "default")

                # 构建对话上下文（最近2轮）
                conversation_text = ""
                recent_messages = messages[-2:] if len(messages) >= 2 else messages
                for msg in recent_messages:
                    if hasattr(msg, 'type'):
                        if msg.type == 'human':
                            conversation_text += f"User: {_extract_text_from_message(msg)}\n"
                        elif msg.type == 'ai':
                            msg_content = getattr(msg, 'content', '')
                            if isinstance(msg_content, str) and msg_content:
                                conversation_text += f"Assistant: {msg_content}\n"

                # 添加当前回复
                conversation_text += f"Assistant: {content}"

                # ✅ 调试：打印保存内容
                print(f"[Memory DEBUG] 准备保存，user_id={user_id}")
                print(f"[Memory DEBUG] 对话内容: {conversation_text[:200]}...")

                # 保存到Mem0（Mem0会自动提取事实）
                result = self.memory.add(
                    messages=conversation_text,
                    user_id=user_id,
                    metadata={"source": "navigation_agent", "timestamp": str(__import__('time').time())}
                )
                print(f"[Memory DEBUG] Mem0返回结果: {result}")
                print(f"[Memory] 已保存对话记忆（user_id={user_id}）")
            except Exception as e:
                print(f"[Memory] 保存失败（不影响主流程）: {e}")

        return {"messages": [ai_message]}

    async def call_tools(self, state: AgentState) -> dict:
        """执行工具节点：并行执行所有工具调用

        Args:
            state: 当前状态

        Returns:
            包含工具结果的字典
        """
        last_message = state["messages"][-1]

        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            print("[Action] ⚠️ 没有工具需要执行")
            return {}

        tools_map = {tool.name: tool for tool in self.tools}

        async def run_one(call: ToolCall) -> ToolMessage:
            """执行单个工具调用"""
            name = call["name"]
            args = call["args"]
            call_id = call["id"]

            print(f"[Action] 调用工具: {name}，参数: {args}")

            # 检查工具是否存在
            if name not in tools_map:
                error = {"error": f"未知工具 '{name}'"}
                print(f"[Action] ❌ {error['error']}")
                return ToolMessage(
                    content=json.dumps(error, ensure_ascii=False),
                    tool_call_id=call_id
                )

            tool = tools_map[name]

            try:
                # 执行工具（支持异步）
                result = await asyncio.wait_for(tool.ainvoke(args), timeout=30)

                # 转换结果为字符串
                if isinstance(result, str):
                    content = result
                else:
                    try:
                        content = json.dumps(result, ensure_ascii=False, default=str)
                    except (TypeError, ValueError):
                        content = str(result)

                print(f"[Action] ✅ 工具 {name} 执行成功")
                return ToolMessage(content=content, tool_call_id=call_id)

            except asyncio.TimeoutError:
                error = {"error": f"工具 '{name}' 执行超时（30秒）"}
                print(f"[Action] ❌ {error['error']}")
                return ToolMessage(
                    content=json.dumps(error, ensure_ascii=False),
                    tool_call_id=call_id
                )
            except Exception as e:
                error = {"error": f"工具 '{name}' 执行失败: {str(e)}"}
                print(f"[Action] ❌ {error['error']}")
                return ToolMessage(
                    content=json.dumps(error, ensure_ascii=False),
                    tool_call_id=call_id
                )

        # ✅ 并行执行所有工具调用
        print(f"[Action] 开始并行执行 {len(last_message.tool_calls)} 个工具...")
        tool_outputs = await asyncio.gather(
            *[run_one(call) for call in last_message.tool_calls]
        )

        print(f"[Action] 所有工具执行完成")
        return {"messages": tool_outputs}

    def should_continue(self, state: AgentState) -> str:
        """判断是否需要继续调用工具

        Args:
            state: 当前状态

        Returns:
            "action" 或 END
        """
        last_message = state["messages"][-1]

        # 如果最后一条消息是AI消息且包含工具调用，则执行工具
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "action"

        # 否则结束
        return END

    async def astream_events(self, initial_state: dict, config: dict):
        """流式执行Agent并返回事件

        这是一个便捷方法，用于兼容现有的API接口

        Args:
            initial_state: 初始状态
            config: 配置

        Yields:
            事件字典
        """
        async for event in self.app.astream_events(initial_state, config, version="v2"):
            yield event


def create_agent(checkpointer=None, memory=None) -> NavigationAgent:
    """创建Agent实例

    Args:
        checkpointer: LangGraph checkpointer实例
        memory: Mem0 Memory实例

    Returns:
        NavigationAgent实例
    """
    return NavigationAgent(checkpointer=checkpointer, memory=memory)
