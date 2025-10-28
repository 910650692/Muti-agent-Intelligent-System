"""测试完整的 LangGraph Workflow"""
from langchain_core.messages import HumanMessage
from app.graph.workflow import create_workflow


def test_workflow():
    """测试完整的 Multi-Agent Workflow"""

    print("=" * 60)
    print("测试 LangGraph Multi-Agent Workflow")
    print("=" * 60)

    # 创建 Workflow
    app = create_workflow()
    mermaid_graph = app.get_graph().draw_mermaid()

    # 保存为文件或直接打印
    with open("workflow.mmd", "w", encoding="utf-8") as f:
        f.write(mermaid_graph)
    # 测试用例
    test_cases = [
        "北京今天天气怎么样？",
        "上海的天气如何？",
    ]

    for i, user_input in enumerate(test_cases, 1):
        print(f"\n{'=' * 60}")
        print(f"测试 {i}: {user_input}")
        print('=' * 60)

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
                print(f"{msg.__class__.__name__}: {msg.content}")
            print("-" * 60)

        except Exception as e:
            print(f"❌ 错误: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    test_workflow()