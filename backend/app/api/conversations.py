"""对话管理 API"""
from fastapi import APIRouter, HTTPException, Request
from typing import List, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from ..db.database import (
    create_conversation,
    get_conversation,
    list_conversations,
    update_conversation,
    delete_conversation
)
from ..db.models import Conversation, ConversationCreate, ConversationUpdate

router = APIRouter()


@router.post("/conversations", response_model=Conversation)
async def api_create_conversation(conv: ConversationCreate):
    """创建新对话"""
    try:
        return await create_conversation(conv)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建对话失败: {str(e)}")


@router.get("/conversations", response_model=List[Conversation])
async def api_list_conversations(user_id: str = "user_001", include_archived: bool = False):
    """获取用户的所有对话

    Args:
        user_id: 用户ID（默认user_001）
        include_archived: 是否包含归档的对话
    """
    try:
        return await list_conversations(user_id, include_archived)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取对话列表失败: {str(e)}")


@router.get("/conversations/{conversation_id}", response_model=Conversation)
async def api_get_conversation(conversation_id: str):
    """获取单个对话详情"""
    conversation = await get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conversation


@router.patch("/conversations/{conversation_id}", response_model=Conversation)
async def api_update_conversation(conversation_id: str, update: ConversationUpdate):
    """更新对话信息（标题、归档状态等）"""
    conversation = await update_conversation(conversation_id, update)
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conversation


@router.delete("/conversations/{conversation_id}")
async def api_delete_conversation(conversation_id: str):
    """删除对话"""
    success = await delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="对话不存在")
    return {"message": "对话已删除", "conversation_id": conversation_id}


@router.get("/conversations/{conversation_id}/messages")
async def api_get_conversation_messages(conversation_id: str, request: Request):
    """获取对话的完整历史消息（从LangGraph checkpointer加载）

    Returns:
        List of messages: [
            {"role": "user", "content": "...", "timestamp": "..."},
            {"role": "assistant", "content": "...", "timestamp": "..."},
            ...
        ]
    """
    # 检查对话是否存在
    conversation = await get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")

    try:
        # 从 checkpointer 加载该对话的完整状态
        checkpointer = request.app.state.checkpointer
        config = {"configurable": {"thread_id": conversation_id}}

        # 获取该thread的最新state
        try:
            state = await checkpointer.aget(config)
        except Exception as checkpoint_error:
            print(f"[API] Checkpointer.aget 错误: {checkpoint_error}")
            # 如果checkpointer中没有该thread，返回空列表（可能是刚创建还没发消息）
            return []

        if not state:
            # 对话存在但没有消息（刚创建还没发消息）
            print(f"[API] 对话 {conversation_id} 没有state记录")
            return []

        # ✅ 修复：正确访问 LangGraph checkpoint 结构
        # CheckpointTuple.checkpoint 包含实际数据
        # checkpoint 是一个字典，包含 channel_values 字段
        checkpoint = state.checkpoint if hasattr(state, 'checkpoint') else state

        # 尝试从 channel_values 获取数据（LangGraph 标准结构）
        if isinstance(checkpoint, dict) and "channel_values" in checkpoint:
            channel_values = checkpoint["channel_values"]
            messages = channel_values.get("messages", [])
        elif isinstance(checkpoint, dict):
            # 直接从checkpoint获取（旧版本或不同配置）
            messages = checkpoint.get("messages", [])
        else:
            print(f"[API] 未知的checkpoint结构，类型: {type(checkpoint)}")
            print(f"[API] Checkpoint内容: {checkpoint}")
            return []

        if not messages:
            print(f"[API] 对话 {conversation_id} messages字段为空")
            print(f"[API] Checkpoint结构: {checkpoint.keys() if isinstance(checkpoint, dict) else 'not dict'}")
            return []

        # 转换为前端友好的格式
        formatted_messages = []
        print(f"[API] 开始处理 {len(messages)} 条消息")

        for idx, msg in enumerate(messages):
            print(f"[API] 消息 {idx}: 类型={type(msg).__name__}, 内容={str(msg)[:100]}")

            # 只返回用户和AI的消息（跳过ToolMessage等内部消息）
            if isinstance(msg, HumanMessage):
                content = msg.content

                # ✅ 处理多模态用户消息（文本+图片）
                if isinstance(content, list):
                    # 提取文本部分
                    text_parts = [
                        item.get("text", "")
                        for item in content
                        if isinstance(item, dict) and item.get("type") == "text"
                    ]
                    content_str = " ".join(text_parts) if text_parts else "[图片消息]"
                elif isinstance(content, str):
                    content_str = content
                else:
                    content_str = str(content)

                formatted_messages.append({
                    "role": "user",
                    "content": content_str,
                    "timestamp": getattr(msg, "timestamp", None)
                })
                print(f"[API]   ✓ 用户消息: {content_str[:50]}")

            elif isinstance(msg, AIMessage):
                # 跳过空消息
                content = msg.content
                if isinstance(content, str) and content.strip():
                    formatted_messages.append({
                        "role": "assistant",
                        "content": content,
                        "timestamp": getattr(msg, "timestamp", None)
                    })
                    print(f"[API]   ✓ AI消息: {content[:50]}")
                elif isinstance(content, list):
                    # 多模态消息，提取文本
                    text_parts = [item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"]
                    if text_parts:
                        formatted_messages.append({
                            "role": "assistant",
                            "content": " ".join(text_parts),
                            "timestamp": getattr(msg, "timestamp", None)
                        })
                        print(f"[API]   ✓ AI多模态消息: {text_parts[0][:50]}")
                else:
                    print(f"[API]   ✗ 跳过空AI消息")
            else:
                print(f"[API]   - 跳过其他类型: {type(msg).__name__}")

        print(f"[API] 加载对话 {conversation_id} 成功，共 {len(formatted_messages)} 条消息（原始{len(messages)}条）")
        return formatted_messages

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[API] 加载对话消息失败: {error_detail}")
        raise HTTPException(status_code=500, detail=f"加载消息失败: {str(e)}")
