"""LangGraph Workflow 构建"""
from langgraph.graph import StateGraph, END
from langgraph.constants import Send  # ✅ 正确的导入路径
from typing import Union, List

from ..state.agent_state import AgentState
from ..agents.supervisor import supervisor_agent
from ..agents.weather import weather_agent
from ..agents.general import general_agent
from ..agents.train import train_agent
from ..agents.aggregate import aggregate_agent  # 导入aggregate节点

def create_workflow(checkpointer):
    """创建 Multi-Agent Workflow（支持并行Agent执行）

    Args:
        checkpointer: LangGraph checkpointer实例（如AsyncSqliteSaver）

    Returns:
        编译后的workflow应用
    """

    # 创建 StateGraph
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("supervisor", supervisor_agent)
    workflow.add_node("weather", weather_agent)
    workflow.add_node("general", general_agent)
    workflow.add_node("train", train_agent)
    workflow.add_node("aggregate", aggregate_agent)  # ✅ 添加aggregate节点

    # 设置入口点
    workflow.set_entry_point("supervisor")

    # ✅ Supervisor 的条件路由（支持Send API并行执行）
    def route_supervisor(state: AgentState) -> Union[List[Send], str]:
        """根据 Supervisor 的决策路由到下一个节点

        返回值:
        - 如果next_agents为空 → 返回END（finish）
        - 如果next_agents有1个 → 返回Send列表（单个agent）
        - 如果next_agents有多个 → 返回Send列表（并行执行所有agents）
        """
        next_agents = state.get("next_agents", [])

        print(f"[Workflow] route_supervisor: next_agents = {next_agents}")

        # 如果为空列表，表示finish
        if not next_agents:
            print("[Workflow] 所有任务完成，路由到 END")
            return END

        # ✅ 使用Send API创建并行任务
        # 每个agent会收到完整的state副本，并行执行
        sends = [Send(agent_name, state) for agent_name in next_agents]

        print(f"[Workflow] 创建 {len(sends)} 个并行任务: {next_agents}")
        return sends

    # ✅ 添加条件边：Supervisor → Send(agents)
    # 注意：当返回Send列表时，不需要指定路由字典
    workflow.add_conditional_edges(
        "supervisor",
        route_supervisor
    )

    # ✅ 所有Agent执行完毕后，都路由到aggregate节点进行汇总
    workflow.add_edge("weather", "aggregate")
    workflow.add_edge("general", "aggregate")
    workflow.add_edge("train", "aggregate")

    # ✅ Aggregate汇总后，回到Supervisor继续决策
    workflow.add_edge("aggregate", "supervisor")

    # 使用传入的 AsyncSqliteSaver 实现磁盘持久化
    # 数据库文件: ./data/checkpoints.db
    # 会话状态在进程重启后依然保留
    app = workflow.compile(checkpointer=checkpointer)

    return app