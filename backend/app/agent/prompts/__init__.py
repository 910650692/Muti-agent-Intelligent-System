"""Prompt模块 - Agent V2 分层 Prompt 配置

架构说明：
- constitution.py: 核心准则（简洁、稳定）
- memory_guide.py: 记忆系统详细指南（总是加载）
"""

from .constitution import CONSTITUTION
from .memory_guide import MEMORY_GUIDE

__all__ = [
    "CONSTITUTION",
    "MEMORY_GUIDE",
]
