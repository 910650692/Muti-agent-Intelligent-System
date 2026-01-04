"""
Navigation Agent V2 - 简化版ReAct架构

设计目标：
1. 清晰的职责分离：Agent推理 → Execution执行 → Response响应
2. 标准化输出格式：decision JSON
3. 支持三种场景：纯对话、对话任务、主动服务
4. 易于测试和扩展
"""
import json
from typing import List, Dict, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command

from ..state.agent_state import AgentState
from ..llm import get_llm
from ..mcp.manager import mcp_manager
from ..tools.weather_tools import weather_tools
from ..memory.memory_tools import memory_tools
from ..utils.structured_logger import get_logger
from .hitl_config import (
    need_confirmation,
    need_selection,
    get_missing_param_prompt,
    get_confirmation_message,
    get_selection_message,
    is_candidate_list
)
from .prompts import CONSTITUTION, MEMORY_GUIDE

logger = get_logger(__name__)


class AgentConfig:
    """Agent运行配置"""
    MAX_ITERATIONS = 10           # 最大循环次数
    MAX_TOTAL_TOOL_CALLS = 50     # 全局最多工具调用次数（比V1更保守）


class NavigationAgentV2:
    """导航Agent V2 - 简化版"""

    def __init__(self):
        self.llm = get_llm(force_text=True)

        # 加载所有工具
        self.tools = []

        # 1. 加载MCP工具（导航相关）
        mcp_tools = mcp_manager.load_all_tools()
        self.tools.extend(mcp_tools)
        logger.info(f"MCP工具加载完成: {len(mcp_tools)} 个")

        # 2. 加载天气工具（function call）
        self.tools.extend(weather_tools)
        logger.info(f"天气工具加载完成: {len(weather_tools)} 个")

        # 3. 加载记忆工具（Phase 1: 位置+偏好记忆）
        # ⚠️ 过滤掉保存工具（这些工具由系统自动调用，Agent不应直接使用）
        excluded_tools = {"memory_save_user_profile", "memory_save_relationship"}
        filtered_memory_tools = [
            tool for tool in memory_tools
            if tool.name not in excluded_tools
        ]
        self.tools.extend(filtered_memory_tools)
        logger.info(f"记忆工具加载完成: {len(filtered_memory_tools)} 个（已过滤 {len(memory_tools) - len(filtered_memory_tools)} 个保存工具）")

        # 4. 保存完整的工具列表（包含保存工具，供execution节点使用）
        self._all_memory_tools = memory_tools

        logger.info(f"Agent V2 初始化完成，总计加载 {len(self.tools)} 个工具")

    # ==================== Node 1: Agent 推理 ====================

    async def agent_node(self, state: AgentState, config: RunnableConfig = None) -> Dict:
        """
        Agent推理节点：理解意图，决策工具调用

        输入：
        - messages: 对话历史
        - action_results: 上一轮工具执行结果（Observation）

        输出：
        - decision: {
            "think": "推理过程",
            "actions": [{"name": "工具名", "args": {...}}],
            "response": "给用户的回复",
            "is_complete": bool
          }
        """
        messages = state["messages"]
        iteration = state.get("iteration_count", 0) + 1
        action_results = state.get("action_results", [])

        # 📋 记录最新消息（可能是用户输入或上一轮的 AI 回复）
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, 'content'):
                msg_type = type(last_message).__name__
                emoji = "📥" if msg_type == "HumanMessage" else "🤖"
                logger.info(
                    f"{emoji} 最新消息",
                    iteration=iteration,
                    content=last_message.content,
                    message_type=msg_type
                )

        # 📸 Messages 快照（调试用）
        logger.debug(
            "📸 Messages 快照",
            iteration=iteration,
            messages=[
                {
                    "type": type(msg).__name__,
                    "content": msg.content[:100] if hasattr(msg, 'content') and msg.content else "",
                    "has_tool_calls": hasattr(msg, 'tool_calls') and bool(msg.tool_calls)
                }
                for msg in messages
            ]
        )

        logger.info(
            "Agent推理开始",
            iteration=iteration,
            message_count=len(messages),
            has_previous_results=bool(action_results)
        )

        # 从config中获取user_id
        user_id = "default_user"  # 默认值
        if config and "configurable" in config:
            user_id = config["configurable"].get("user_id", "default_user")

        # 构建System Prompt
        system_prompt = self._build_system_prompt(iteration, action_results, user_id)

        # 构建完整消息
        full_messages = [
            SystemMessage(content=system_prompt),
            *messages
        ]

        # 调用LLM（绑定工具）
        model_with_tools = self.llm.bind_tools(self.tools)

        try:
            response = await model_with_tools.ainvoke(full_messages, config=config)
        except Exception as e:
            logger.error("LLM调用失败", error=str(e))
            return {
                "decision": {
                    "think": f"LLM调用失败: {e}",
                    "actions": [],
                    "response": "抱歉，处理请求时出错了",
                    "is_complete": True
                },
                "messages": [AIMessage(content="抱歉，处理请求时出错了")],
                "iteration_count": iteration
            }

        # 解析LLM输出
        content = response.content or ""
        tool_calls = getattr(response, "tool_calls", [])

        # 📤 记录 LLM 原始输出
        logger.info(
            "📤 LLM 原始输出",
            iteration=iteration,
            content=content,
            tool_calls_count=len(tool_calls) if tool_calls else 0,
            has_tool_calls=bool(tool_calls)
        )

        # 构建decision
        decision = self._build_decision(content, tool_calls, iteration, action_results)

        # 📊 记录 Decision 详情
        logger.info(
            "📊 Decision 详情",
            iteration=iteration,
            think=decision.get("think", ""),
            response=decision.get("response", ""),
            actions=decision.get("actions", []),
            is_complete=decision.get("is_complete", False)
        )

        logger.info(
            "Agent推理完成",
            has_tools=bool(decision["actions"]),
            tool_count=len(decision["actions"]),
            is_complete=decision["is_complete"]
        )

        return {
            "decision": decision,
            # ✅ 保留完整的 AIMessage（包含 content），供 LLM 在下一轮迭代时阅读
            # 前端过滤由 chat.py 的流式输出逻辑控制
            "messages": [response],  # 包含 content 和 tool_calls
            "iteration_count": iteration
        }

    def _build_system_prompt(self, iteration: int, action_results: List[Dict], user_id: str) -> str:
        """构建System Prompt

        Args:
            iteration: 当前循环次数
            action_results: 上一轮工具执行结果
            user_id: 当前用户ID（从config中获取）
        """

        # 如果有上一轮的执行结果，加入Observation
        observation_text = ""
        if action_results:
            observation_text = "\n\n# 上一轮工具执行结果（Observation）\n"
            for result in action_results:
                status = result.get("status", "unknown")
                tool = result.get("tool", "unknown")
                if status == "success":
                    observation_text += f"- {tool}: ✓ 成功\n"
                elif status == "error":
                    error = result.get("error", "未知错误")
                    observation_text += f"- {tool}: ✗ 失败 ({error})\n"

            # ⚡ 增加指导：要求 LLM 在回复中确认已完成的操作
            observation_text += """\n⚠️ 重要提示：
- 如果工具执行成功，在给用户的回复中要**明确确认**已完成的操作（例如："已保存XX信息"）
- 不要只说"有什么需要帮忙的"，要让用户知道刚才的操作已成功完成
- 回复要自然、友好，让用户感受到任务确实完成了
"""

        # ⚠️ 使用分层 Prompt：CONSTITUTION（核心准则） + MEMORY_GUIDE（记忆系统详细指南）
        prompt = f"""{CONSTITUTION}

{MEMORY_GUIDE}

# 当前上下文
- 当前用户 ID: {user_id}
- 当前是第 {iteration} 轮推理
- 最大循环次数: {AgentConfig.MAX_ITERATIONS}
{observation_text}"""

        return prompt

    def _build_decision(
        self,
        content: str,
        tool_calls: List[Dict],
        iteration: int,
        action_results: List[Dict]
    ) -> Dict:
        """根据LLM输出构建标准化的decision"""

        # 转换tool_calls为actions格式
        actions = []
        if tool_calls:
            for call in tool_calls:
                actions.append({
                    "name": call.get("name"),
                    "args": call.get("args", {})
                })

        # 判断是否完成
        is_complete = False
        if not actions:
            # 没有工具调用，任务完成
            is_complete = True
        elif iteration >= AgentConfig.MAX_ITERATIONS:
            # 达到最大循环次数
            is_complete = True
            logger.warning("达到最大循环次数", iteration=iteration)

        # 构建think（推理过程）
        think = f"第{iteration}轮推理："
        if actions:
            think += f"需要调用{len(actions)}个工具"
        else:
            think += "直接回复用户"

        if action_results:
            think += f"，上轮执行了{len(action_results)}个工具"

        decision = {
            "think": think,
            "actions": actions,
            "response": content or "处理中...",
            "is_complete": is_complete
        }

        return decision

    # ==================== Node 2: Execution 执行 ====================

    async def execution_node(self, state: AgentState) -> Dict:
        """
        执行节点：调度工具执行（无LLM），集成HITL机制

        输入：
        - decision: Agent推理结果
        - messages: 需要从中提取tool_calls的tool_call_id

        输出：
        - action_results: 工具执行结果列表
        - messages: 添加ToolMessage（供下一轮Agent读取）

        HITL检查点：
        1. 执行前：检查参数完整性（缺参追问）
        2. 执行前：检查高风险操作（确认）
        3. 执行后：检查候选列表（选择）
        """
        decision = state.get("decision", {})
        actions = decision.get("actions", [])
        messages = state.get("messages", [])
        total_tool_calls = state.get("total_tool_calls", 0)

        if not actions:
            logger.info("无工具需要执行，跳过")
            return {"action_results": []}

        # 找到最后一个AIMessage，提取tool_calls
        last_ai_message = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                last_ai_message = msg
                break

        # 提取tool_calls（包含tool_call_id）
        tool_calls = getattr(last_ai_message, "tool_calls", []) if last_ai_message else []

        # ⚡ 从消息历史中提取已执行的工具ID（通过检查ToolMessage）
        executed_tool_ids = set()
        for msg in messages:
            if isinstance(msg, ToolMessage):
                executed_tool_ids.add(msg.tool_call_id)

        logger.info(
            f"📋 执行前状态检查",
            total_actions=len(actions),
            executed_count=len(executed_tool_ids),
            executed_ids=list(executed_tool_ids)
        )
        logger.info(f"开始执行 {len(actions)} 个工具（已执行: {len(executed_tool_ids)} 个）")

        # 找到第一个未执行的工具
        for i, action in enumerate(actions):
            tool_name = action.get("name")
            tool_args = action.get("args", {})
            tool_call_id = tool_calls[i].get("id") if i < len(tool_calls) else f"call_{i}"

            # 检查该工具是否已执行
            if tool_call_id in executed_tool_ids:
                logger.info(
                    "⏭️ 工具已执行，跳过",
                    tool_name=tool_name,
                    tool_call_id=tool_call_id
                )
                continue

            # 找到第一个未执行的工具
            logger.info(
                "🛠️ 工具调用",
                tool_name=tool_name,
                args=tool_args,
                tool_call_id=tool_call_id
            )

            # 执行 HITL 检查（可能会 interrupt 并阻塞，等待用户响应）
            hitl_result = await self._check_hitl_requirements(
                tool_name, tool_args, tool_call_id
            )

            # 如果用户取消
            if hitl_result == "cancelled":
                return {
                    "action_results": [{
                        "tool": tool_name,
                        "status": "cancelled",
                        "error": "用户取消"
                    }],
                    "messages": [
                        ToolMessage(content="用户取消了操作", tool_call_id=tool_call_id)
                    ]
                }

            # HITL 检查通过（或不需要），执行工具
            # hitl_result 是更新后的 tool_args（如果有缺参追问的话）
            result, tool_message = await self._execute_tool_directly(
                tool_name, hitl_result, tool_call_id
            )

            # 更新计数
            if result.get("status") in ["success", "error"]:
                total_tool_calls += 1

            logger.info(
                f"工具执行完成，本次执行 1 个，累计 {total_tool_calls}/{AgentConfig.MAX_TOTAL_TOOL_CALLS}"
            )

            # 立即返回，确保结果持久化
            return {
                "action_results": [result],
                "messages": [tool_message],
                "total_tool_calls": total_tool_calls
            }

        # 所有工具都已执行
        logger.info("所有工具都已执行，无需重复执行")
        return {"action_results": []}

    async def _check_hitl_requirements(
        self, tool_name: str, tool_args: dict, tool_call_id: str
    ):
        """检查 HITL 要求（缺参追问、高风险确认）

        Returns:
            - tool_args (dict): 更新后的参数（如果有缺参追问）
            - "cancelled": 用户取消
        """
        # ===== HITL检查点1：缺参追问 =====
        missing_params = []
        for param_name, param_value in tool_args.items():
            is_empty = (
                param_value is None or
                (isinstance(param_value, str) and not param_value.strip())
            )
            if is_empty and get_missing_param_prompt(tool_name, param_name):
                missing_params.append(param_name)

        if missing_params:
            logger.info(f"参数缺失: {missing_params}，触发追问")
            prompts = []
            for param in missing_params:
                prompt = get_missing_param_prompt(tool_name, param)
                prompts.append(prompt if prompt else f"请提供 {param}")

            user_response = interrupt({
                "type": "ask_params",
                "tool_name": tool_name,
                "missing_params": missing_params,
                "message": "\n".join(prompts),
                "current_args": tool_args
            })

            if isinstance(user_response, dict) and "params" in user_response:
                tool_args.update(user_response["params"])
                logger.info(f"用户补充参数: {user_response['params']}")
            elif user_response == "cancel":
                logger.info("用户取消操作")
                return "cancelled"

        # ===== HITL检查点2：高风险操作确认 =====
        if need_confirmation(tool_name):
            confirm_msg = get_confirmation_message(tool_name, tool_args)
            logger.info(f"高风险操作，需要确认: {tool_name}")

            user_response = interrupt({
                "type": "confirmation",
                "tool_name": tool_name,
                "args": tool_args,
                "message": confirm_msg,
                "options": ["确认", "取消"]
            })

            if user_response == "cancel" or user_response == "取消":
                logger.info("用户取消高风险操作")
                return "cancelled"

            logger.info("用户确认操作，继续执行")

        return tool_args

    async def _execute_tool_directly(
        self, tool_name: str, tool_args: dict, tool_call_id: str
    ) -> tuple[dict, ToolMessage]:
        """直接执行工具（不做 HITL 检查，但包含候选列表选择）

        Returns:
            (result_dict, tool_message): 工具执行结果和ToolMessage
        """
        try:
            tool = self._find_tool(tool_name)
            if not tool:
                error_msg = f"工具不存在: {tool_name}"
                return (
                    {"tool": tool_name, "status": "error", "error": error_msg},
                    ToolMessage(content=error_msg, tool_call_id=tool_call_id)
                )

            result = await tool.ainvoke(tool_args)
            result_str = str(result)

            logger.info(
                "🔧 工具返回值",
                tool_name=tool_name,
                result=result_str[:500] if len(result_str) > 500 else result_str,
                result_length=len(result_str)
            )

            # ===== HITL检查点3：候选列表选择 =====
            is_list, candidates = is_candidate_list(result)
            if is_list and need_selection(tool_name):
                selection_msg = get_selection_message(tool_name, len(candidates))
                logger.info(f"检测到候选列表，需要用户选择: {len(candidates)} 个")

                formatted_candidates = []
                for idx, item in enumerate(candidates):
                    if isinstance(item, dict):
                        formatted_candidates.append({
                            "id": idx + 1,
                            "name": item.get("mName", item.get("name", str(item))),
                            "description": item.get("mAddress", item.get("description", "")),
                            "raw": item
                        })
                    else:
                        formatted_candidates.append({
                            "id": idx + 1,
                            "name": str(item),
                            "description": "",
                            "raw": item
                        })

                user_response = interrupt({
                    "type": "selection",
                    "tool_name": tool_name,
                    "message": selection_msg,
                    "candidates": formatted_candidates
                })

                if isinstance(user_response, dict) and "selected" in user_response:
                    selected_item = user_response["selected"]
                    result_str = json.dumps(selected_item, ensure_ascii=False)
                    logger.info(f"用户选择: {selected_item.get('name', 'unknown')}")

            logger.info(f"工具执行成功: {tool_name}")
            return (
                {"tool": tool_name, "status": "success", "result": result_str},
                ToolMessage(content=result_str, tool_call_id=tool_call_id)
            )

        except Exception as e:
            error_msg = f"执行失败: {str(e)}"
            logger.error(f"工具执行失败: {tool_name}", error=str(e))
            return (
                {"tool": tool_name, "status": "error", "error": str(e)},
                ToolMessage(content=error_msg, tool_call_id=tool_call_id)
            )

    def _find_tool(self, tool_name: str):
        """查找工具

        优先从 self.tools 查找（Agent可用工具）
        如果是保存工具，从 _all_memory_tools 查找（execution节点专用）
        """
        # 先从标准工具列表查找
        for tool in self.tools:
            if tool.name == tool_name:
                return tool

        # 如果是保存工具，从完整记忆工具列表查找
        if tool_name in {"memory_save_user_profile", "memory_save_relationship"}:
            if hasattr(self, '_all_memory_tools'):
                for tool in self._all_memory_tools:
                    if tool.name == tool_name:
                        return tool

        return None

    # ==================== Node 3: Response 响应 ====================

    async def response_node(self, state: AgentState) -> Dict:
        """
        响应节点：格式化最终输出

        输入：
        - decision: Agent推理结果
        - action_results: 工具执行结果
        - iteration_count: 循环次数
        - total_tool_calls: 全局工具调用次数

        输出：
        - messages: 添加最终的AI回复
        """
        decision = state.get("decision", {})
        action_results = state.get("action_results", [])
        iteration_count = state.get("iteration_count", 0)
        total_tool_calls = state.get("total_tool_calls", 0)

        # 检查是否因达到限制而终止
        terminate_reason = None
        if iteration_count >= AgentConfig.MAX_ITERATIONS:
            terminate_reason = "max_iterations"
        elif total_tool_calls >= AgentConfig.MAX_TOTAL_TOOL_CALLS:
            terminate_reason = "max_tool_calls"

        # 如果是因达到限制终止，生成友好的终止消息
        if terminate_reason:
            if terminate_reason == "max_iterations":
                final_response = f"抱歉，处理您的请求时遇到了复杂情况，已超过最大推理次数（{AgentConfig.MAX_ITERATIONS}次）。请简化问题或重新提问。"
            else:  # max_tool_calls
                final_response = f"抱歉，本轮对话已达到工具调用次数上限（{AgentConfig.MAX_TOTAL_TOOL_CALLS}次）。请开始新的对话。"

            logger.warning(
                "达到限制，生成终止消息",
                reason=terminate_reason,
                iteration_count=iteration_count,
                total_tool_calls=total_tool_calls
            )
        else:
            # 正常完成，使用Agent的回复
            base_response = decision.get("response", "")

            # ⚠️ 静默工具列表（不向用户显示执行结果）
            # 这些工具的执行结果是技术性的，用户不需要看到
            SILENT_TOOLS = {
                "memory_save_location",      # 地址保存
                "memory_save_preference",    # 偏好保存
                "memory_save_user_profile",  # 用户画像保存
                "memory_save_relationship",  # 关系网络保存
            }

            # 如果有工具执行结果，只显示非静默工具的结果
            if action_results:
                # 过滤出需要显示的工具结果
                visible_results = [
                    result for result in action_results
                    if result.get("tool") not in SILENT_TOOLS
                ]

                if visible_results:
                    result_summary = "\n\n执行结果：\n"
                    for result in visible_results:
                        tool = result.get("tool")
                        status = result.get("status")
                        if status == "success":
                            result_summary += f"✓ {tool}: 成功\n"
                        else:
                            error = result.get("error", "未知错误")
                            result_summary += f"✗ {tool}: 失败 ({error})\n"

                    final_response = base_response + result_summary
                else:
                    # 所有工具都是静默的，只返回 Agent 的回复
                    final_response = base_response
            else:
                final_response = base_response

        # 📮 记录最终响应
        logger.info(
            "📮 最终响应",
            response=final_response,
            response_length=len(final_response)
        )

        logger.info("生成最终响应", response_length=len(final_response))

        return {
            "messages": [AIMessage(content=final_response)]
        }

    # ==================== 条件边 ====================

    def should_continue(self, state: AgentState) -> str:
        """
        判断是否继续ReAct循环

        返回：
        - "execution": 有工具需要执行，进入execution节点
        - "response": 任务完成，进入response节点
        """
        decision = state.get("decision", {})
        total_tool_calls = state.get("total_tool_calls", 0)

        # 检查全局工具调用次数
        if total_tool_calls >= AgentConfig.MAX_TOTAL_TOOL_CALLS:
            logger.warning(f"达到全局工具调用次数上限: {total_tool_calls}/{AgentConfig.MAX_TOTAL_TOOL_CALLS}")
            return "response"

        # 检查是否完成
        if decision.get("is_complete", False):
            logger.info("任务完成，生成最终响应")
            return "response"

        # 检查是否有工具需要执行
        actions = decision.get("actions", [])
        if actions:
            logger.info(f"有 {len(actions)} 个工具需要执行")
            return "execution"

        # 默认：完成
        return "response"

    def need_continue_after_execution(self, state: AgentState) -> str:
        """
        执行完工具后，判断是否需要继续循环

        返回：
        - "execution": 还有未执行的工具，继续执行
        - "agent": 所有工具执行完毕，返回Agent评估结果
        - "response": 任务完成，生成最终响应
        """
        iteration = state.get("iteration_count", 0)

        # 检查是否达到最大循环次数
        if iteration >= AgentConfig.MAX_ITERATIONS:
            logger.warning("达到最大循环次数，强制结束", iteration=iteration)
            return "response"

        # ⚡ 检查是否还有未执行的工具
        decision = state.get("decision", {})
        actions = decision.get("actions", [])
        messages = state.get("messages", [])

        if actions:
            # 提取已执行的 tool_call_ids
            executed_tool_ids = set()
            for msg in messages:
                if isinstance(msg, ToolMessage):
                    executed_tool_ids.add(msg.tool_call_id)

            # 提取所有 tool_call_ids
            last_ai_message = None
            for msg in reversed(messages):
                if isinstance(msg, AIMessage):
                    last_ai_message = msg
                    break

            tool_calls = getattr(last_ai_message, "tool_calls", []) if last_ai_message else []
            total_tool_call_ids = {tc.get("id") for tc in tool_calls if tc.get("id")}

            # 如果还有未执行的工具，继续执行
            pending_count = len(total_tool_call_ids - executed_tool_ids)
            if pending_count > 0:
                logger.info(f"还有 {pending_count} 个工具未执行，继续执行")
                return "execution"

        # 所有工具执行完毕，返回Agent评估是否需要继续
        logger.info("所有工具执行完成，返回Agent评估是否需要继续")
        return "agent"

    # ==================== 构建Graph ====================

    def create_graph(self, checkpointer=None):
        """创建LangGraph

        Args:
            checkpointer: 可选的checkpointer，用于持久化对话历史
        """

        graph = StateGraph(AgentState)

        # 添加节点
        graph.add_node("agent", self.agent_node)
        graph.add_node("execution", self.execution_node)
        graph.add_node("response", self.response_node)

        # 设置入口
        graph.set_entry_point("agent")

        # Agent → execution 或 response（条件边）
        graph.add_conditional_edges(
            "agent",
            self.should_continue,
            {
                "execution": "execution",
                "response": "response"
            }
        )

        # Execution → execution / agent / response（条件边）
        # - execution: 还有未执行的工具，继续执行
        # - agent: 所有工具执行完毕，返回Agent评估
        # - response: 达到循环上限
        graph.add_conditional_edges(
            "execution",
            self.need_continue_after_execution,
            {
                "execution": "execution",
                "agent": "agent",
                "response": "response"
            }
        )

        # Response → END
        graph.add_edge("response", END)

        # 编译（带checkpointer）
        if checkpointer:
            return graph.compile(checkpointer=checkpointer)
        else:
            return graph.compile()


# ==================== 创建函数（供main.py调用） ====================

def create_agent_v2(checkpointer=None):
    """创建Agent V2实例

    Args:
        checkpointer: LangGraph checkpointer

    Returns:
        编译后的graph
    """
    agent = NavigationAgentV2()
    return agent.create_graph(checkpointer=checkpointer)
