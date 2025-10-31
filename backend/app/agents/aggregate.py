"""Aggregate Node: 汇总并行Agent的执行结果"""
from langchain_core.messages import AIMessage

from ..state.agent_state import AgentState


def aggregate_agent(state: AgentState) -> AgentState:
    """Aggregate Agent: 汇总所有并行执行的Agent结果，返回Supervisor继续决策

    这个节点的作用:
    1. 收集所有并行agents的执行结果（已经在messages中）
    2. 简单地将控制权返回给Supervisor
    3. Supervisor会检查是否所有任务完成，决定是否finish或继续路由
    """

    messages = state["messages"]
    completed_tasks = state.get("completed_tasks", [])

    print(f"[Aggregate] 汇总并行执行结果，当前消息数: {len(messages)}")
    print(f"[Aggregate] 已完成任务: {completed_tasks}")

    # 不需要做任何特殊处理，只是作为同步点
    # 所有并行agents的结果已经通过messages字段累加到state中
    # 直接返回state，让workflow路由回supervisor

    return {
        "messages": [],  # 不添加额外消息
        "next_agent": "supervisor",  # 用于workflow路由（aggregate不是并行节点）
    }
