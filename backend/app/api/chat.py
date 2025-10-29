"""Chat API 接口"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
import json
import asyncio

from ..graph.workflow import create_workflow

router = APIRouter()


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    thread_id: str = "default"


class ChatResponse(BaseModel):
    """聊天响应"""
    response: str
    thread_id: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
  """标准 Chat 接口（非流式）"""

  # 创建 Workflow
  app = create_workflow()

  # 配置 Checkpointing（使用 thread_id）
  config = {"configurable": {"thread_id": request.thread_id}}

  # 构造初始状态
  initial_state = {
      "messages": [HumanMessage(content=request.message)],
      "next_agent": "",
      "completed_tasks": [],
      "thread_id": request.thread_id
  }

  # 运行 Workflow（传入 config）
  final_state = app.invoke(initial_state, config)

  # 提取最终响应（排除 Supervisor 的消息）
  response_messages = []
  for msg in final_state["messages"]:
      content = msg.content
      if not content.startswith("[Supervisor]"):
          response_messages.append(content)

  final_response = "\n\n".join(response_messages)

  return ChatResponse(
      response=final_response,
      thread_id=request.thread_id
  )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
  """SSE 流式 Chat 接口"""

  user_message = request.message
  thread_id = request.thread_id

  async def event_generator():
      """生成 SSE 事件"""
      try:
          # 发送开始事件
          yield f"data: {json.dumps({'type': 'start', 'message': '开始处理...'}, ensure_ascii=False)}\n\n"

          # 创建 Workflow
          app = create_workflow()

          # 配置 Checkpointing（使用 thread_id）
          config = {"configurable": {"thread_id": thread_id}}

          # 构造初始状态
          initial_state = {
              "messages": [HumanMessage(content=user_message)],
              "next_agent": "",
              "completed_tasks": [],
              "thread_id": thread_id
          }

          # 运行 Workflow 并流式输出（传入 config）
          for output in app.stream(initial_state, config):
              for node_name, node_output in output.items():
                  # 发送节点开始事件
                  yield f"data: {json.dumps({'type': 'node_start', 'node': node_name}, ensure_ascii=False)}\n\n"

                  # 发送消息内容（打字机效果）
                  if "messages" in node_output and node_output["messages"]:
                      last_message = node_output["messages"][-1]
                      content = last_message.content

                      # 过滤掉 Supervisor 的内部消息
                      if not content.startswith("[Supervisor]"):
                          # 逐字符发送，实现打字机效果
                          for char in content:
                              yield f"data: {json.dumps({'type': 'token', 'content': char, 'node': node_name}, ensure_ascii=False)}\n\n"
                              await asyncio.sleep(0.02)  # 每个字符延迟 20ms

                  # 发送节点完成事件
                  yield f"data: {json.dumps({'type': 'node_end', 'node': node_name}, ensure_ascii=False)}\n\n"

          # 发送完成事件
          yield f"data: {json.dumps({'type': 'done', 'message': '处理完成'}, ensure_ascii=False)}\n\n"

      except Exception as e:
          yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

  return StreamingResponse(
      event_generator(),
      media_type="text/event-stream",
      headers={
          "Cache-Control": "no-cache",
          "Connection": "keep-alive",
          "X-Accel-Buffering": "no",
      }
  )