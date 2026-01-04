"""Chat API 接口"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Iterable, Dict, Set
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import json
import asyncio
import time
import uuid

# HITL 支持
from langgraph.types import Command

# Agent从app.state中获取，不需要导入
from ..config import config
from ..db.database import update_conversation_activity, ensure_conversation_exists
from ..db.models import ConversationCreate
from ..utils.structured_logger import get_logger, LogContext
from ..langfuse_config import create_langfuse_handler

# 获取logger
logger = get_logger(__name__)

router = APIRouter()


class ImageData(BaseModel):
    """图片数据"""
    type: str = Field(default="base64", description="图片类型: base64 或 url")
    data: str = Field(..., description="Base64编码的图片数据或URL")


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    user_id: str = "user_001"  # 用户ID（当前固定为user_001）
    conversation_id: str = "default"  # 对话ID（对应LangGraph的thread_id）
    images: Optional[List[ImageData]] = Field(default=None, description="图片列表（可选）")


class ChatResponse(BaseModel):
    """聊天响应"""
    response: str
    conversation_id: str


class ResumeRequest(BaseModel):
    """恢复中断请求"""
    conversation_id: str = Field(..., description="对话ID")
    user_id: str = Field(default="user_001", description="用户ID")
    resume_value: Any = Field(..., description="用户响应值（确认/选择/参数）")


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
        # 过滤LangGraph的内部常量和空字符串
        if value in ["__end__", "__start__", ""] or not value.strip():
            return []
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

        # ⚠️ 忽略状态字段（total_tool_calls, force_terminate, iteration_count等）
        # 这些字段不应该被当作消息内容
        # 如果没有messages/output/content字段，返回空列表
        return []

    return [str(value)]


@router.post("/chat", response_model=ChatResponse)
async def chat(chat_request: ChatRequest, request: Request):
    """标准 Chat 接口（非流式）"""

    # 从 app.state 获取Agent
    agent = request.app.state.agent

    # 配置 Checkpointing（使用 conversation_id 作为 thread_id）
    config = {"configurable": {"thread_id": chat_request.conversation_id, "user_id": chat_request.user_id}}

    # 构造初始状态（包含消息和计数器）
    initial_state = {
        "messages": [build_message(chat_request.message, chat_request.images)],
        "iteration_count": 0,      # 初始化循环计数器
        "total_tool_calls": 0,     # 初始化工具调用计数器
        "force_terminate": False,  # 初始化强制终止标记
    }

    # 运行 Agent
    final_state = await agent.ainvoke(initial_state, config)

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

    # 更新对话活动
    await update_conversation_activity(chat_request.conversation_id, chat_request.message)

    return ChatResponse(
        response=final_response,
        conversation_id=chat_request.conversation_id
    )


@router.post("/chat/stream")
async def chat_stream(chat_request: ChatRequest, request: Request):
    """SSE 流式 Chat 接口 - 真正的LLM流式输出"""

    user_message = chat_request.message
    conversation_id = chat_request.conversation_id
    user_id = chat_request.user_id

    # 生成唯一请求ID
    request_id = str(uuid.uuid4())

    async def event_generator():
        """生成 SSE 事件"""
        # ✅ 设置日志上下文（自动传播到所有子调用）
        with LogContext(
            request_id=request_id,
            conversation_id=conversation_id,
            user_id=user_id
        ):
            try:
                # ✅ 记录请求开始
                logger.info(
                    "收到聊天请求",
                    endpoint="/chat/stream",
                    message_length=len(user_message),
                    has_images=bool(chat_request.images),
                    image_count=len(chat_request.images) if chat_request.images else 0
                )

                # ✅ 确保对话记录存在（如果不存在则自动创建）
                await ensure_conversation_exists(conversation_id, user_id, "新对话")

                # 发送开始事件
                yield f"data: {json.dumps({'type': 'start', 'message': '开始处理...'}, ensure_ascii=False)}\n\n"

                # 从 app.state 获取Agent
                agent = request.app.state.agent

                # ✅ 创建独立的 LangFuse handler（v3.x 官方方式）
                langfuse_handler, langfuse_metadata = create_langfuse_handler(
                    session_id=conversation_id,
                    user_id=user_id,
                    tags=["production", "navigation"],
                    metadata={
                        "has_images": bool(chat_request.images),
                        "image_count": len(chat_request.images) if chat_request.images else 0
                    }
                )

                # 配置 Checkpointing 和 LangFuse
                config = {
                    "configurable": {
                        "thread_id": conversation_id,
                        "user_id": user_id
                    }
                }

                # ✅ v3.x: 通过 metadata 传递 session_id 和 user_id
                if langfuse_handler and langfuse_metadata:
                    config["callbacks"] = [langfuse_handler]
                    config["metadata"] = langfuse_metadata

                # 构造初始状态（包含消息和计数器）
                initial_state = {
                    "messages": [build_message(user_message, chat_request.images)],
                    "iteration_count": 0,      # 初始化循环计数器
                    "total_tool_calls": 0,     # 初始化工具调用计数器
                    "force_terminate": False,  # 初始化强制终止标记
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
                graph_finished = False  # 标记 graph 是否完成执行

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

                        # ⭐ 调试日志
                        print(f"[Stream DEBUG] 节点开始: {node_from_tags}")

                        # 只在第一次进入时发送 node_start 事件
                        if node_from_tags not in seen_nodes:
                            seen_nodes.add(node_from_tags)
                            # 发送节点开始事件（agent = 思考中，execution = 执行工具）
                            display_name = "思考中" if node_from_tags == "agent" else "执行工具" if node_from_tags == "execution" else node_from_tags
                            yield f"data: {json.dumps({'type': 'node_start', 'node': node_from_tags, 'display': display_name}, ensure_ascii=False)}\n\n"

                    # 2. LLM token流式输出 ⭐ 核心功能
                    elif event_type == "on_chat_model_stream":
                        try:
                            # 提取节点名称
                            event_node = detect_node(event, fallback=current_node)

                            # ⚠️ 关键修改：跳过 agent 节点的所有流式输出（避免中间推理过程显示给用户）
                            # agent 节点的内容保留在 state.messages 中供 LLM 阅读
                            # 最终响应由 response 节点通过 on_chain_end 事件发送（非流式）
                            if event_node == "agent":
                                # 仍然累加到 current_message（用于日志和调试）
                                chunk_data = event.get("data", {}).get("chunk", {})
                                if hasattr(chunk_data, "content"):
                                    token = chunk_data.content
                                elif isinstance(chunk_data, dict):
                                    token = chunk_data.get("content", "")
                                else:
                                    token = str(chunk_data) if chunk_data else ""
                                current_message += token if token else ""
                                continue  # 跳过发送给前端

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
                            yield f"data: {json.dumps({'type': 'token', 'content': token, 'node': event_node}, ensure_ascii=False)}\n\n"

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

                            # ⚠️ response 节点输出最终响应（因为 agent 节点的流式输出已被跳过）
                            # execution 节点不应该有文本输出
                            if node_from_tags == "response":
                                sent_texts = node_sent_texts.setdefault(node_from_tags, set())
                                for text in _flatten_text(output_payload):
                                    cleaned = text.strip()
                                    if not cleaned:
                                        continue
                                    # 过滤节点名称和内部标记
                                    if cleaned in ["execution", "agent", "response", "terminate", "__end__", "__start__"]:
                                        continue
                                    if cleaned in sent_texts:
                                        continue
                                    sent_texts.add(cleaned)
                                    yield f"data: {json.dumps({'type': 'message', 'content': cleaned, 'node': node_from_tags}, ensure_ascii=False)}\n\n"
                                    has_content = True

                            # ✅ 只有当节点有内容输出时才发送node_end（避免空消息）
                            if has_content:
                                yield f"data: {json.dumps({'type': 'node_end', 'node': current_node}, ensure_ascii=False)}\n\n"

                            current_message = ""

                    # 6. Graph 完成事件
                    elif event_type == "on_chain_end" and not node_from_tags and event_name == "LangGraph":
                        graph_finished = True
                        print(f"[Stream DEBUG] Graph execution finished")

                # ⚠️ 事件循环结束后，检查是否有 interrupt
                print(f"[Stream DEBUG] Event loop ended, checking for interrupt...")
                try:
                    state = await agent.aget_state(config)
                    print(f"[Stream DEBUG] Got state: next={state.next}, tasks={len(state.tasks) if state.tasks else 0}")

                    # 检查是否有待处理的 interrupt
                    if state.tasks:
                        for task in state.tasks:
                            if hasattr(task, 'interrupts') and task.interrupts:
                                for interrupt_item in task.interrupts:
                                    interrupt_value = interrupt_item.value if hasattr(interrupt_item, 'value') else interrupt_item
                                    print(f"[Stream] [HITL] 检测到 interrupt: {interrupt_value}")

                                    # 发送 interrupt 事件给前端
                                    yield f"data: {json.dumps({'type': 'interrupt', 'data': interrupt_value}, ensure_ascii=False)}\n\n"
                                    yield f"data: {json.dumps({'type': 'waiting_input', 'message': interrupt_value.get('message', '请确认操作')}, ensure_ascii=False)}\n\n"

                                    # 更新对话活动
                                    await update_conversation_activity(conversation_id, user_message)
                                    return  # 停止，等待用户 resume
                except Exception as state_error:
                    print(f"[Stream] 获取状态失败: {state_error}")

                # 更新对话活动
                await update_conversation_activity(conversation_id, user_message)

                # ✅ 记录请求完成
                elapsed = time.time() - start_time
                logger.info(
                    "请求完成",
                    endpoint="/chat/stream",
                    status="success",
                    duration_ms=int(elapsed * 1000)
                )

                # 发送完成事件（包含最后的节点信息）
                yield f"data: {json.dumps({'type': 'done', 'message': '处理完成', 'node': current_node}, ensure_ascii=False)}\n\n"

            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()

                # ✅ 记录错误
                logger.error(
                    "请求失败",
                    endpoint="/chat/stream",
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True
                )
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


@router.post("/chat/resume")
async def resume_chat(resume_request: ResumeRequest, request: Request):
    """恢复被中断的对话（HITL）

    当 Agent 触发 interrupt 等待用户输入时，前端调用此接口恢复执行。

    Args:
        resume_request: 恢复请求，包含用户响应值

    Returns:
        StreamingResponse: 流式返回后续执行结果
    """
    conversation_id = resume_request.conversation_id
    user_id = resume_request.user_id
    resume_value = resume_request.resume_value

    async def event_generator():
        """生成 SSE 事件"""
        try:
            # 发送恢复开始事件
            yield f"data: {json.dumps({'type': 'resume_start', 'message': '正在恢复执行...'}, ensure_ascii=False)}\n\n"

            # 从 app.state 获取Agent
            agent = request.app.state.agent

            # ✅ 创建独立的 LangFuse handler（v3.x 官方方式）
            langfuse_handler, langfuse_metadata = create_langfuse_handler(
                session_id=conversation_id,
                user_id=user_id,
                tags=["production", "navigation", "resume"],
                metadata={
                    "is_resume": True
                }
            )

            # 配置 Checkpointing 和 LangFuse
            config = {
                "configurable": {
                    "thread_id": conversation_id,
                    "user_id": user_id
                }
            }

            # ✅ v3.x: 通过 metadata 传递 session_id 和 user_id
            if langfuse_handler and langfuse_metadata:
                config["callbacks"] = [langfuse_handler]
                config["metadata"] = langfuse_metadata

            # 状态跟踪
            current_node = None
            current_message = ""
            seen_nodes = set()
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

            # 使用 Command(resume=...) 恢复执行
            start_time = time.time()
            async for event in agent.astream_events(
                Command(resume=resume_value),
                config,
                version="v2"
            ):
                # 检查是否超时
                elapsed = time.time() - start_time
                if elapsed > 120:  # 2分钟
                    print(f"[Resume] Agent执行超时！")
                    yield f"data: {json.dumps({'type': 'error', 'message': '任务执行超时'}, ensure_ascii=False)}\n\n"
                    break

                event_type = event["event"]
                event_name = event.get("name", "")

                # 从事件中解析节点名称
                node_from_tags = detect_node(event)

                # 1. 节点开始事件
                if event_type == "on_chain_start" and node_from_tags:
                    current_node = node_from_tags
                    current_message = ""

                    if node_from_tags not in seen_nodes:
                        seen_nodes.add(node_from_tags)
                        display_name = "思考中" if node_from_tags == "agent" else "执行工具" if node_from_tags == "execution" else node_from_tags
                        yield f"data: {json.dumps({'type': 'node_start', 'node': node_from_tags, 'display': display_name}, ensure_ascii=False)}\n\n"

                # 2. LLM token流式输出
                elif event_type == "on_chat_model_stream":
                    try:
                        event_node = detect_node(event, fallback=current_node)

                        # ⚠️ 关键修改：跳过 agent 节点的所有流式输出（避免中间推理过程显示给用户）
                        # 与 /chat/stream 保持一致的逻辑
                        if event_node == "agent":
                            chunk_data = event.get("data", {}).get("chunk", {})
                            if hasattr(chunk_data, "content"):
                                token = chunk_data.content
                            elif isinstance(chunk_data, dict):
                                token = chunk_data.get("content", "")
                            else:
                                token = str(chunk_data) if chunk_data else ""
                            current_message += token if token else ""
                            continue  # 跳过发送给前端

                        chunk_data = event.get("data", {}).get("chunk", {})

                        if hasattr(chunk_data, "content"):
                            token = chunk_data.content
                        elif isinstance(chunk_data, dict):
                            token = chunk_data.get("content", "")
                        else:
                            token = str(chunk_data) if chunk_data else ""

                        if not token:
                            continue

                        current_message += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token, 'node': event_node or 'agent'}, ensure_ascii=False)}\n\n"

                    except Exception as token_error:
                        print(f"[Resume] Token处理错误: {token_error}")

                # 3. 工具调用开始
                elif event_type == "on_tool_start":
                    tool_name = event_name
                    yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name}, ensure_ascii=False)}\n\n"

                # 4. 工具调用完成
                elif event_type == "on_tool_end":
                    tool_name = event_name
                    tool_output = event.get("data", {}).get("output", "")
                    tool_result = str(tool_output)[:200] if tool_output else ""
                    yield f"data: {json.dumps({'type': 'tool_end', 'tool': tool_name, 'result': tool_result}, ensure_ascii=False)}\n\n"

                # 5. 节点完成事件
                elif event_type == "on_chain_end" and node_from_tags:
                    if node_from_tags == current_node:
                        output_payload = event.get("data", {}).get("output")
                        has_content = bool(current_message.strip())

                        # ⚠️ response 节点输出最终响应（ReAct 架构设计）
                        # agent = 思考过程（黑盒，不输出）
                        # execution = 工具执行（内部过程，不输出）
                        # response = 最终响应（白盒，用户可见）
                        if node_from_tags == "response":
                            sent_texts = node_sent_texts.setdefault(node_from_tags, set())
                            for text in _flatten_text(output_payload):
                                cleaned = text.strip()
                                if not cleaned:
                                    continue
                                # 过滤节点名称和内部标记
                                if cleaned in ["execution", "agent", "response", "terminate", "__end__", "__start__"]:
                                    continue
                                if cleaned in sent_texts:
                                    continue
                                sent_texts.add(cleaned)
                                yield f"data: {json.dumps({'type': 'message', 'content': cleaned, 'node': node_from_tags}, ensure_ascii=False)}\n\n"
                                has_content = True

                        # ✅ 只有当节点有内容输出时才发送node_end（避免空消息）
                        if has_content:
                            yield f"data: {json.dumps({'type': 'node_end', 'node': current_node}, ensure_ascii=False)}\n\n"

                        # 重置当前消息累积
                        current_message = ""

            # ⚠️ 事件循环结束后，检查是否有 interrupt（与 /chat/stream 相同的逻辑）
            print(f"[Resume DEBUG] Event loop ended, checking for interrupt...")
            try:
                state = await agent.aget_state(config)
                print(f"[Resume DEBUG] Got state: next={state.next}, tasks={len(state.tasks) if state.tasks else 0}")

                # 检查是否有待处理的 interrupt
                if state.tasks:
                    for task in state.tasks:
                        if hasattr(task, 'interrupts') and task.interrupts:
                            for interrupt_item in task.interrupts:
                                interrupt_value = interrupt_item.value if hasattr(interrupt_item, 'value') else interrupt_item
                                print(f"[Resume] [HITL] 检测到 interrupt: {interrupt_value}")

                                # 发送 interrupt 事件给前端
                                yield f"data: {json.dumps({'type': 'interrupt', 'data': interrupt_value}, ensure_ascii=False)}\n\n"
                                yield f"data: {json.dumps({'type': 'waiting_input', 'message': interrupt_value.get('message', '请确认操作')}, ensure_ascii=False)}\n\n"
                                return  # 停止，等待用户 resume
            except Exception as state_error:
                print(f"[Resume] 获取状态失败: {state_error}")

            # 发送完成事件
            yield f"data: {json.dumps({'type': 'done', 'message': '恢复执行完成', 'node': current_node}, ensure_ascii=False)}\n\n"

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[Resume] 错误: {error_detail}")
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


@router.get("/mcp/status")
async def get_mcp_status(request: Request):
    """
    获取 MCP 连接状态

    Returns:
        各 MCP 服务的连接状态
    """
    from ..mcp.manager import mcp_manager

    status = mcp_manager.get_sse_connection_status()

    return {
        "status": "ok",
        "connections": status
    }


@router.post("/mcp/reconnect")
async def reconnect_mcp(request: Request, server_name: Optional[str] = None):
    """
    手动重连 MCP 服务

    Args:
        server_name: 指定重连的服务名称，不传则重连所有断开的服务

    Returns:
        重连结果
    """
    from ..mcp.manager import mcp_manager

    results = mcp_manager.reconnect_sse(server_name)

    return {
        "status": "ok",
        "reconnect_results": results
    }


@router.get("/memory/check-profile")
async def check_profile_status(user_id: str = "user_001"):
    """
    检查用户 profile 是否已初始化

    用于前端判断是否需要显示引导消息。

    Args:
        user_id: 用户ID（默认 user_001）

    Returns:
        {
            "user_id": str,
            "is_initialized": bool,
            "greeting": str | null  # 如果未初始化，返回引导消息
        }
    """
    from ..memory.service import MemoryService

    memory_service = MemoryService(db_path="data/memory.db")
    is_initialized = memory_service.check_profile_initialized(user_id)

    greeting = None
    if not is_initialized:
        greeting = "你好！我是你的智能车载助手。为了更好地为你服务，能简单介绍下自己吗？比如你的职业、兴趣爱好等~（也可以直接告诉我需要什么帮助）"

    return {
        "user_id": user_id,
        "is_initialized": is_initialized,
        "greeting": greeting
    }

