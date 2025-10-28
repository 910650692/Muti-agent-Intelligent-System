"""测试 Weather Agent"""
import asyncio
from langchain_core.messages import HumanMessage
from app.agents.weather import weather_agent
from app.state.agent_state import AgentState


async def test_weather_agent():
  """测试天气查询功能"""

  print("=" * 50)
  print("测试 Weather Agent")
  print("=" * 50)

  # 模拟用户输入
  test_message = "北京今天天气怎么样？"

  print(f"\n用户输入: {test_message}\n")

  # 构造初始状态
  initial_state: AgentState = {
      "messages": [HumanMessage(content=test_message)],
      "next_agent": "weather",
      "completed_tasks": [],
      "thread_id": "test-001"
  }

  # 调用 Weather Agent
  try:
      result_state = weather_agent(initial_state)

      print("Agent 返回结果:")
      print("-" * 50)
      print(result_state["messages"][-1].content)
      print("-" * 50)
      print(f"\n已完成任务: {result_state['completed_tasks']}")
      print(f"下一个 Agent: {result_state['next_agent']}")

  except Exception as e:
      print(f"❌ 错误: {e}")
      import traceback
      traceback.print_exc()


if __name__ == "__main__":
  asyncio.run(test_weather_agent())