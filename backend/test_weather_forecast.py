"""测试天气预报功能（支持未来5天）"""
from langchain_core.messages import HumanMessage
from app.graph.workflow import create_workflow


def test_weather_forecast():
    """测试天气预报功能"""

    print("=" * 60)
    print("测试天气预报功能（未来5天）")
    print("=" * 60)

    # 创建 Workflow
    app = create_workflow()

    # 测试用例
    test_cases = [
        "北京今天天气怎么样？",
        "上海明天的天气如何？",
        "深圳后天天气怎么样？",
        "广州大后天天气如何？",
    ]

    for i, user_input in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"测试 {i}: {user_input}")
        print('='*60)

        # 构造初始状态
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "next_agent": "",
            "completed_tasks": [],
            "thread_id": f"test-{i}"
        }

        # 运行 Workflow
        try:
            final_state = app.invoke(initial_state)

            print("\n最终结果:")
            print("-" * 60)
            for msg in final_state["messages"]:
                content = msg.content
                if not content.startswith("[Supervisor]"):
                    print(content)
            print("-" * 60)

        except Exception as e:
            print(f"❌ 错误: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    test_weather_forecast()
