"""Chat API 接口"""
from fastapi import APIRouter, Request
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
async def chat(chat_request: ChatRequest, request: Request):
  """标准 Chat 接口（非流式）"""

  # ✅ 从 app.state 获取全局 checkpointer
  checkpointer = request.app.state.checkpointer

  # 创建 Workflow（传入checkpointer）
  app = create_workflow(checkpointer)

  # 配置 Checkpointing（使用 thread_id）
  config = {"configurable": {"thread_id": chat_request.thread_id}}

  # 构造初始状态
  initial_state = {
      "messages": [HumanMessage(content=chat_request.message)],
      "next_agent": "",
      "completed_tasks": [],
      "thread_id": chat_request.thread_id,
      "iteration_count": 0  # 初始化循环计数器
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
async def chat_stream(chat_request: ChatRequest, request: Request):
  """SSE 流式 Chat 接口 - 真正的LLM流式输出"""

  # ✅ 从 app.state 获取全局 checkpointer
  checkpointer = request.app.state.checkpointer

  user_message = chat_request.message
  thread_id = chat_request.thread_id

  async def event_generator():
      """生成 SSE 事件"""
      try:
          # 发送开始事件
          yield f"data: {json.dumps({'type': 'start', 'message': '开始处理...'}, ensure_ascii=False)}\n\n"

          # ✅ 创建 Workflow（传入checkpointer）
          app = create_workflow(checkpointer)

          # 配置 Checkpointing（使用 thread_id）
          config = {"configurable": {"thread_id": thread_id}}

          # 构造初始状态
          initial_state = {
              "messages": [HumanMessage(content=user_message)],
              "next_agent": "",
              "completed_tasks": [],
              "thread_id": thread_id,
              "iteration_count": 0  # 初始化循环计数器
          }

          # 状态跟踪
          current_node = None
          current_message = ""
          seen_nodes = set()  # 用于节点事件去重（仅用于node_start消息）

          def detect_node(event, fallback=None):
              """根据事件元数据提取当前节点名称"""
              metadata = event.get("metadata", {}) or {}
              tags = event.get("tags", []) or []

              node_name = metadata.get("langgraph_node") or metadata.get("node")
              if node_name:
                  return node_name

              for tag in tags:
                  if tag.startswith("langgraph_node:"):
                      return tag.split(":", 1)[1]

              return fallback

          # ✅ 使用 astream_events 获取真正的流式输出
          async for event in app.astream_events(initial_state, config, version="v2"):
              event_type = event["event"]
              event_name = event.get("name", "")

              # 获取当前节点名称（从 metadata 或 tags 中）
              metadata = event.get("metadata", {})
              tags = event.get("tags", [])

              # 从事件中解析节点名称
              node_from_tags = detect_node(event)

              # 1. 节点开始事件
              if event_type == "on_chain_start" and node_from_tags:
                  # ✅ 总是更新 current_node（即使节点重复进入）
                  current_node = node_from_tags
                  current_message = ""

                  # ✅ 只在第一次进入时发送 node_start 事件（避免重复通知）
                  if node_from_tags not in seen_nodes:
                      seen_nodes.add(node_from_tags)
                      # 不发送 Supervisor 的节点事件（对用户无意义）
                      if node_from_tags != "supervisor":
                          yield f"data: {json.dumps({'type': 'node_start', 'node': current_node}, ensure_ascii=False)}\n\n"

              # 2. LLM token流式输出 ⭐ 核心功能
              elif event_type == "on_chat_model_stream":
                  try:
                      # ✅ 优先从事件中提取节点名称，必要时回退到当前节点
                      event_node = detect_node(event, fallback=current_node)

                      # ✅ 如果是supervisor节点的token，直接跳过（不处理、不累积、不发送）
                      if event_node == "supervisor":
                          continue

                      chunk_data = event.get("data", {}).get("chunk", {})

                      # 提取 token 内容
                      if hasattr(chunk_data, "content"):
                          token = chunk_data.content
                      elif isinstance(chunk_data, dict):
                          token = chunk_data.get("content", "")
                      else:
                          token = str(chunk_data) if chunk_data else ""

                      if not token:
                          continue

                      # 额外保护：过滤 supervisor 决策输出来防止误判
                      stripped_token = token.strip()
                      if stripped_token.startswith("{") and "\"agent\"" in stripped_token:
                          continue

                      current_message += token

                      # 额外保护：过滤以 [Supervisor] 开头的消息
                      is_supervisor_msg = current_message.strip().startswith("[Supervisor]")
                      if is_supervisor_msg:
                          current_message = ""
                          continue

                      # 发送有效的 token 到前端
                      yield f"data: {json.dumps({'type': 'token', 'content': token, 'node': event_node or 'unknown'}, ensure_ascii=False)}\n\n"

                  except Exception as token_error:
                      print(f"[Stream] Token处理错误: {token_error}")

              # 3. 工具调用开始
              elif event_type == "on_tool_start":
                  tool_name = event_name
                  yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name}, ensure_ascii=False)}\n\n"

              # 4. 工具调用完成
              elif event_type == "on_tool_end":
                  tool_name = event_name
                  tool_output = event.get("data", {}).get("output", "")

                  # 限制工具输出长度
                  tool_result = str(tool_output)[:200] if tool_output else ""

                  yield f"data: {json.dumps({'type': 'tool_end', 'tool': tool_name, 'result': tool_result}, ensure_ascii=False)}\n\n"

              # 5. 节点完成事件
              elif event_type == "on_chain_end" and node_from_tags:
                  if node_from_tags == current_node:
                      # ✅ 不发送 Supervisor 的节点完成事件
                      if node_from_tags != "supervisor":
                          yield f"data: {json.dumps({'type': 'node_end', 'node': current_node}, ensure_ascii=False)}\n\n"
                      current_message = ""

          # 发送完成事件
          yield f"data: {json.dumps({'type': 'done', 'message': '处理完成'}, ensure_ascii=False)}\n\n"

      except Exception as e:
          import traceback
          error_detail = traceback.format_exc()
          print(f"[Stream] 错误: {error_detail}")
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