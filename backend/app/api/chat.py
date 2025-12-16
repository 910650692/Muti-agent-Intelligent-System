"""Chat API 接口"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Iterable, Dict, Set
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import json
import asyncio
import time

# Agent从app.state中获取，不需要导入
from ..config import config

router = APIRouter()


class ImageData(BaseModel):
    """图片数据"""
    type: str = Field(default="base64", description="图片类型: base64 或 url")
    data: str = Field(..., description="Base64编码的图片数据或URL")


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    thread_id: str = "default"
    user_id: str = "default"  # ✅ 新增：用户ID，用于Mem0长期记忆
    images: Optional[List[ImageData]] = Field(default=None, description="图片列表（可选）")


class ChatResponse(BaseModel):
    """聊天响应"""
    response: str
    thread_id: str


def build_message(text: str, images: Optional[List[ImageData]] = None) -> HumanMessage:
    """
    构建 LangChain 消息（支持多模态）

    Args:
        text: 文本内容
        images: 图片列表（可选）

    Returns:
        HumanMessage: LangChain 消息对象
    """
    if not images or len(images) == 0:
        # 纯文本消息
        return HumanMessage(content=text)

    # 多模态消息（图片 + 文本）
    content = []

    # 添加文本部分
    if text and text.strip():
        content.append({
            "type": "text",
            "text": text
        })

    # 添加图片部分
    for img in images:
        if img.type == "base64":
            # Base64格式
            # 确保data包含完整的data URI格式
            image_data = img.data
            if not image_data.startswith("data:"):
                # 如果没有data URI前缀，添加默认的
                image_data = f"data:image/jpeg;base64,{image_data}"

            content.append({
                "type": "image_url",
                "image_url": {
                    "url": image_data
                }
            })
        elif img.type == "url":
            # URL格式
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": img.data
                }
            })

    return HumanMessage(content=content)


def _flatten_text(value: Any) -> Iterable[str]:
    """从多种返回结构中提取纯文本，兼容 LangChain/BaseMessage、dict、list.

    注意：会自动过滤ToolMessage（工具的原始返回），只提取AIMessage的���容
    """
    if value is None:
        return []

    # ✅ LangChain Message 对象 - 跳过ToolMessage
    if isinstance(value, ToolMessage):
        return []  # 不显示工具的原始返回

    content = getattr(value, "content", None)
    if content is not None:
        if isinstance(content, str):
            return [content]
        if isinstance(content, list):
            texts: List[str] = []
            for item in content:
                texts.extend(_flatten_text(item))
            return texts
        return [str(content)]

    if isinstance(value, str):
        return [value]

    if isinstance(value, list):
        texts: List[str] = []
        for item in value:
            texts.extend(_flatten_text(item))
        return texts

    if isinstance(value, dict):
        # LangGraph 节点输出通常包含 messages / output 等字段
        if "messages" in value:
            texts: List[str] = []
            for item in value["messages"]:
                # ✅ 过滤ToolMessage
                if not isinstance(item, ToolMessage):
                    texts.extend(_flatten_text(item))
            return texts
        if "output" in value:
            return list(_flatten_text(value["output"]))
        if "content" in value:
            return list(_flatten_text(value["content"]))
        # 遍历其它字段
        texts: List[str] = []
        for item in value.values():
            texts.extend(_flatten_text(item))
        return texts

    return [str(value)]


@router.post("/chat", response_model=ChatResponse)
async def chat(chat_request: ChatRequest, request: Request):
    """标准 Chat 接口（非流式）"""

    # 从 app.state 获取Agent
    agent = request.app.state.agent

    # 配置 Checkpointing（使用 thread_id）
    config = {"configurable": {"thread_id": chat_request.thread_id}}

    # 构造初始状态（包含消息和计数器）
    initial_state = {
        "messages": [build_message(chat_request.message, chat_request.images)],
        "iteration_count": 0,      # 初始化循环计数器
        "total_tool_calls": 0,     # 初始化工具调用计数器
    }

    # 运行 Agent
    final_state = await agent.app.ainvoke(initial_state, config)

    # 提取最终响应（只保留AI消息）
    response_messages = []
    for msg in final_state["messages"]:
        # 只提取AI的回复
        if isinstance(msg, AIMessage):
            content = msg.content

            # 处理多模态消息（content可能是列表）
            if isinstance(content, str):
                if content.strip():  # 跳过空内容
                    response_messages.append(content)
            elif isinstance(content, list):
                # 多模态消息，提取文本部分
                text_parts = [item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"]
                if text_parts:
                    response_messages.append(" ".join(text_parts))
            else:
                response_messages.append(str(content))

    # 只返回最后一条AI回复
    final_response = response_messages[-1] if response_messages else "抱歉，我没有生成回复。"

    return ChatResponse(
        response=final_response,
        thread_id=chat_request.thread_id
    )


@router.post("/chat/stream")
async def chat_stream(chat_request: ChatRequest, request: Request):
    """SSE 流式 Chat 接口 - 真正的LLM流式输出"""

    user_message = chat_request.message
    thread_id = chat_request.thread_id
    user_id = chat_request.user_id  # ✅ 获取user_id

    async def event_generator():
        """生成 SSE 事件"""
        try:
            # 发送开始事件
            yield f"data: {json.dumps({'type': 'start', 'message': '开始处理...'}, ensure_ascii=False)}\n\n"

            # 从 app.state 获取Agent
            agent = request.app.state.agent

            # 配置 Checkpointing（使用 thread_id 和 user_id）
            config = {"configurable": {"thread_id": thread_id, "user_id": user_id}}

            # 构造初始状态（包含消息和计数器）
            initial_state = {
                "messages": [build_message(user_message, chat_request.images)],
                "iteration_count": 0,      # 初始化循环计数器
                "total_tool_calls": 0,     # 初始化工具调用计数器
            }

            # 状态跟踪
            current_node = None
            current_message = ""
            seen_nodes = set()  # 用于节点事件去重（仅用于node_start消息）
            node_sent_texts: Dict[str, Set[str]] = {}

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

            # ✅ 使用 Agent 的 astream_events 获取真正的流式输出
            # ✅ 添加超时保护（2分钟）
            start_time = time.time()
            async for event in agent.astream_events(initial_state, config):
                # 检查是否超时
                elapsed = time.time() - start_time
                if elapsed > 120:  # 2分钟
                    print(f"\n{'='*60}")
                    print(f"[Stream] ⚠️ Agent执行超时！")
                    print(f"[Stream] 📊 已执行时间: {elapsed:.2f} 秒")
                    print(f"[Stream] 📊 超时限制: 120 秒（2分钟）")
                    print(f"[Stream] 🚫 强制终止执行")
                    print(f"{'='*60}\n")
                    yield f"data: {json.dumps({'type': 'error', 'message': '任务执行超时（2分钟），已强制终止'}, ensure_ascii=False)}\n\n"
                    break

                event_type = event["event"]
                event_name = event.get("name", "")

                # 从事件中解析节点名称
                node_from_tags = detect_node(event)

                # 1. 节点开始事件
                if event_type == "on_chain_start" and node_from_tags:
                    # 更新 current_node
                    current_node = node_from_tags
                    current_message = ""

                    # 只在第一次进入时发送 node_start 事件
                    if node_from_tags not in seen_nodes:
                        seen_nodes.add(node_from_tags)
                        # 发送节点开始事件（reasoning = 思考中，action = 执行工具）
                        display_name = "思考中" if node_from_tags == "reasoning" else "执行工具" if node_from_tags == "action" else node_from_tags
                        yield f"data: {json.dumps({'type': 'node_start', 'node': node_from_tags, 'display': display_name}, ensure_ascii=False)}\n\n"

                # 2. LLM token流式输出 ⭐ 核心功能
                elif event_type == "on_chat_model_stream":
                    try:
                        # 提取节点名称
                        event_node = detect_node(event, fallback=current_node)

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

                        current_message += token

                        # 发送 token 到前端
                        yield f"data: {json.dumps({'type': 'token', 'content': token, 'node': event_node or 'reasoning'}, ensure_ascii=False)}\n\n"

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
                        output_payload = event.get("data", {}).get("output")

                        # 标记是否有内容输出（用于判断是否发送node_end）
                        has_content = bool(current_message.strip())

                        # 如果没有实时token输出，尝试从节点输出中提取文本一次性发送
                        if not current_message.strip():
                            sent_texts = node_sent_texts.setdefault(node_from_tags, set())
                            for text in _flatten_text(output_payload):
                                cleaned = text.strip()
                                if not cleaned:
                                    continue
                                if cleaned in sent_texts:
                                    continue
                                sent_texts.add(cleaned)
                                yield f"data: {json.dumps({'type': 'message', 'content': cleaned, 'node': node_from_tags}, ensure_ascii=False)}\n\n"
                                has_content = True  # 标记已发送内容

                        # ✅ 只有当节点有内容输出时才发送node_end（避免action节点产生空消息）
                        if has_content:
                            yield f"data: {json.dumps({'type': 'node_end', 'node': current_node}, ensure_ascii=False)}\n\n"

                        current_message = ""

            # 发送完成事件（包含最后的节点信息）
            yield f"data: {json.dumps({'type': 'done', 'message': '处理完成', 'node': current_node}, ensure_ascii=False)}\n\n"

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
