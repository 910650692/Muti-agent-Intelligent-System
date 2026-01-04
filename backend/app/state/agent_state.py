"""单Agent ReAct 状态定义"""
from typing import TypedDict, Annotated, List, Optional, Any, Dict
from langchain_core.messages import BaseMessage
import operator


class AgentState(TypedDict):
    """单Agent ReAct状态

    在ReAct架构中，状态非常简单：
    - 只需要维护消息历史
    - thread_id在config中传递
    - 不需要next_agent/completed_tasks等Multi-Agent字段
    """

    # 消息历史（支持累加）
    messages: Annotated[List[BaseMessage], operator.add]

    # 循环计数器（用于限制最大循环次数）
    iteration_count: int

    # 工具调用计数器（全局）
    total_tool_calls: int

    # 强制终止标记（用于重复调用等异常场景）
    force_terminate: bool

    # ===== HITL (Human-in-the-Loop) 相关字段 =====

    # 待确认的工具调用（执行前确认）
    # 格式: {"tool_name": str, "args": dict, "type": "confirmation" | "selection" | "ask_params"}
    pending_action: Optional[Dict[str, Any]]

    # 候选列表（执行后选择）
    # 格式: [{"id": int, "name": str, "description": str, ...}, ...]
    candidates: Optional[List[Dict[str, Any]]]

    # 中断类型
    # "confirmation" - 高风险操作确认
    # "selection" - 候选列表选择
    # "ask_params" - 缺参追问
    # "save_memory" - 记忆保存确认 (Phase 2)
    interrupt_type: Optional[str]

    # 中断消息（显示给用户的提示）
    interrupt_message: Optional[str]

    # ===== Step 1: Agent推理结果 =====

    # Agent推理输出（标准化格式）
    # 格式: {
    #   "think": "推理过程",
    #   "actions": [{"name": "工具名", "args": {...}}],
    #   "response": "给用户的回复",
    #   "is_complete": bool
    # }
    decision: Optional[Dict[str, Any]]

    # 工具执行结果（Observation）
    # 格式: [
    #   {"tool": "工具名", "status": "success/error", "result": ...},
    #   ...
    # ]
    action_results: Optional[List[Dict[str, Any]]]

    # ===== Phase 2: 记忆提取 =====

    # Agent检测到的可保存记忆（批量）
    # 格式: [
    #   {
    #     "type": "profile" | "relationship" | "preference",
    #     "data": {...},  # 具体数据根据type不同而不同
    #     "confidence": "high" | "medium" | "low"  # 可选：置信度
    #   },
    #   ...
    # ]
    detected_memories: Optional[List[Dict[str, Any]]]
