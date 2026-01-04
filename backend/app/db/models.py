"""数据模型定义"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Conversation(BaseModel):
    """对话模型"""
    id: str = Field(..., description="对话ID")
    user_id: str = Field(..., description="用户ID")
    title: str = Field(default="新对话", description="对话标题")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    message_count: int = Field(default=0, description="消息数量")
    is_archived: bool = Field(default=False, description="是否归档")
    preview: Optional[str] = Field(default=None, description="首条消息预览")


class ConversationCreate(BaseModel):
    """创建对话请求"""
    user_id: str = Field(..., description="用户ID")
    title: Optional[str] = Field(default=None, description="对话标题（可选）")


class ConversationUpdate(BaseModel):
    """更新对话请求"""
    title: Optional[str] = Field(default=None, description="对话标题")
    is_archived: Optional[bool] = Field(default=None, description="是否归档")
