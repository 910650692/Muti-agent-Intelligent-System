"""
Memory Module - 智能记忆系统

提供长短期记忆功能：
- 长期记忆：用户画像、常用地址、偏好设置、纪念日、关系网络
- 短期记忆：对话快照、临时上下文

Phase 1: 位置记忆 + 偏好记忆
"""

from .service import MemoryService

__all__ = ["MemoryService"]
