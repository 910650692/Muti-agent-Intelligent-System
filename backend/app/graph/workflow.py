"""LangGraph Workflow 构建"""
from langgraph.graph import StateGraph, END
import sqlite3

from ..state.agent_state import AgentState
from ..agents.supervisor import supervisor_agent
from ..agents.weather import weather_agent
from langgraph.checkpoint.sqlite import SqliteSaver

def create_workflow():
  """创建 Multi-Agent Workflow"""

  # 创建 StateGraph
  workflow = StateGraph(AgentState)

  # 添加节点
  workflow.add_node("supervisor", supervisor_agent)
  workflow.add_node("weather", weather_agent)

  # 设置入口点
  workflow.set_entry_point("supervisor")

  # Supervisor 的条件路由
  def route_supervisor(state: AgentState) -> str:
    """根据 Supervisor 的决策路由到下一个节点"""
    next_agent = state.get("next_agent", "finish")

    if next_agent == "weather":
      return "weather"
    else:
      return "finish"

  workflow.add_conditional_edges(
    "supervisor",
    route_supervisor,
    {
      "weather": "weather",
      "finish": END,
    }
  )

  # Weather Agent 完成后回到 Supervisor
  workflow.add_edge("weather", "supervisor")

  # 创建 Checkpointing（持久化对话状态）
  # 使用 with 语句正确初始化 SqliteSaver
  conn = sqlite3.connect("data/checkpoints.db", check_same_thread=False)
  memory = SqliteSaver(conn)

  # 编译 Workflow 并启用 Checkpointing
  app = workflow.compile(checkpointer=memory)

  return app