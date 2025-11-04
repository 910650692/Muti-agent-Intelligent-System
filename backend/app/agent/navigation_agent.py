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

    def __init__(self, checkpointer=None):
        """初始化Agent

        Args:
            checkpointer: LangGraph checkpointer实例（如AsyncSqliteSaver），用于保存会话状态
        """
        print("[NavigationAgent] 初始化单Agent ReAct架构...")

        self.system_prompt = get_system_prompt()
        self.tools = self._load_all_tools()
        self.checkpointer = checkpointer
        self.app = self._build_graph()

        print(f"[NavigationAgent] 初始化完成，共加载 {len(self.tools)} 个工具")

    def _load_all_tools(self) -> List[BaseTool]:
        """加载所有工具"""
        tools = []

        # 1. 加载导航MCP工具
        print("[NavigationAgent] 正在加载MCP导航工具...")
        mcp_tools = mcp_manager.load_all_tools()
        navigation_mcp_tools = [
            tool for tool in mcp_tools
            if "sgm-navigation" in tool.name.lower() or "navi" in tool.name.lower()
        ]
        tools.extend(navigation_mcp_tools)
        print(f"[NavigationAgent] 加载了 {len(navigation_mcp_tools)} 个MCP工具")

        # 2. 加载天气工具
        tools.extend(weather_tools)
        print(f"[NavigationAgent] 加载了 {len(weather_tools)} 个天气工具")

        # 3. 未来可以添加更多工具
        # tools.extend(search_tools)

        return tools

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

        Args:
            state: 当前状态
            config: 运行配置

        Returns:
            包含新消息的字典
        """
        messages = state["messages"]

        print(f"\n[Reasoning] 开始推理，当前消息数: {len(messages)}")

        # ✅ 智能选择LLM（自动检测是否有图片）
        llm = get_llm(messages=messages)

        # ✅ 绑定所有工具
        model_with_tools = llm.bind_tools(self.tools)

        # 构建完整的消息（system + history）
        full_messages = [
            SystemMessage(content=self.system_prompt),
            *messages
        ]

        # 流式推理并收集完整响应
        merged_chunk = None
        async for chunk in model_with_tools.astream(full_messages, config=config):
            merged_chunk = chunk if merged_chunk is None else (merged_chunk + chunk)

        if merged_chunk is None:
            print("[Reasoning] ⚠️ LLM未返回任何内容")
            return {}

        # 构建AI消息
        content = getattr(merged_chunk, "content", "") or ""
        tool_calls = getattr(merged_chunk, "tool_calls", None)

        ai_message = AIMessage(
            content=content,
            tool_calls=tool_calls if tool_calls else []
        )

        # 打印决策信息
        if tool_calls:
            tool_names = [call["name"] for call in tool_calls]
            print(f"[Reasoning] 决策: 需要调用 {len(tool_calls)} 个工具: {tool_names}")
        else:
            print(f"[Reasoning] 决策: 直接回答用户")

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


def create_agent(checkpointer=None) -> NavigationAgent:
    """创建Agent实例

    Args:
        checkpointer: LangGraph checkpointer实例

    Returns:
        NavigationAgent实例
    """
    return NavigationAgent(checkpointer=checkpointer)
