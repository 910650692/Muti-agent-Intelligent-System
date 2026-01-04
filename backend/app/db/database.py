"""数据库连接和操作"""
import aiosqlite
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from .models import Conversation, ConversationCreate, ConversationUpdate

# 数据库路径
DB_PATH = Path(__file__).parent.parent.parent / "data" / "conversations.db"


async def init_db():
    """初始化数据库（创建表）"""
    # 确保data目录存在
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '新对话',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                message_count INTEGER DEFAULT 0,
                is_archived INTEGER DEFAULT 0,
                preview TEXT
            )
        """)

        # 创建索引以加速查询
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_id
            ON conversations(user_id)
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_updated_at
            ON conversations(updated_at DESC)
        """)

        await db.commit()
        print(f"[Database] 数据库初始化完成: {DB_PATH}")


async def get_db():
    """获取数据库连接（用于依赖注入）"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db


async def create_conversation(conv: ConversationCreate) -> Conversation:
    """创建新对话"""
    conversation_id = f"conv_{int(datetime.now().timestamp() * 1000)}_{id(conv) % 1000000000}"
    now = datetime.now().isoformat()
    title = conv.title or "新对话"

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO conversations (id, user_id, title, created_at, updated_at, message_count, is_archived)
            VALUES (?, ?, ?, ?, ?, 0, 0)
        """, (conversation_id, conv.user_id, title, now, now))
        await db.commit()

    return Conversation(
        id=conversation_id,
        user_id=conv.user_id,
        title=title,
        created_at=datetime.fromisoformat(now),
        updated_at=datetime.fromisoformat(now),
        message_count=0,
        is_archived=False,
        preview=None
    )


async def get_conversation(conversation_id: str) -> Optional[Conversation]:
    """获取单个对话"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM conversations WHERE id = ?
        """, (conversation_id,))
        row = await cursor.fetchone()

        if not row:
            return None

        return Conversation(
            id=row['id'],
            user_id=row['user_id'],
            title=row['title'],
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            message_count=row['message_count'],
            is_archived=bool(row['is_archived']),
            preview=row['preview']
        )


async def list_conversations(user_id: str, include_archived: bool = False) -> List[Conversation]:
    """获取用户的所有对话"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        if include_archived:
            query = """
                SELECT * FROM conversations
                WHERE user_id = ?
                ORDER BY updated_at DESC
            """
            cursor = await db.execute(query, (user_id,))
        else:
            query = """
                SELECT * FROM conversations
                WHERE user_id = ? AND is_archived = 0
                ORDER BY updated_at DESC
            """
            cursor = await db.execute(query, (user_id,))

        rows = await cursor.fetchall()

        return [
            Conversation(
                id=row['id'],
                user_id=row['user_id'],
                title=row['title'],
                created_at=datetime.fromisoformat(row['created_at']),
                updated_at=datetime.fromisoformat(row['updated_at']),
                message_count=row['message_count'],
                is_archived=bool(row['is_archived']),
                preview=row['preview']
            )
            for row in rows
        ]


async def update_conversation(conversation_id: str, update: ConversationUpdate) -> Optional[Conversation]:
    """更新对话信息"""
    async with aiosqlite.connect(DB_PATH) as db:
        # 构建动态更新SQL
        updates = []
        params = []

        if update.title is not None:
            updates.append("title = ?")
            params.append(update.title)

        if update.is_archived is not None:
            updates.append("is_archived = ?")
            params.append(int(update.is_archived))

        if not updates:
            return await get_conversation(conversation_id)

        # 总是更新 updated_at
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())

        params.append(conversation_id)

        query = f"""
            UPDATE conversations
            SET {', '.join(updates)}
            WHERE id = ?
        """

        await db.execute(query, params)
        await db.commit()

    return await get_conversation(conversation_id)


async def delete_conversation(conversation_id: str) -> bool:
    """删除对话"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            DELETE FROM conversations WHERE id = ?
        """, (conversation_id,))
        await db.commit()
        return cursor.rowcount > 0


async def update_conversation_activity(conversation_id: str, message_text: Optional[str] = None):
    """更新对话活动（在收到新消息时调用）"""
    async with aiosqlite.connect(DB_PATH) as db:
        # 检查是否需要更新preview
        if message_text:
            preview = message_text[:100]  # 取前100个字符作为预览
            await db.execute("""
                UPDATE conversations
                SET updated_at = ?, message_count = message_count + 1, preview = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), preview, conversation_id))
        else:
            await db.execute("""
                UPDATE conversations
                SET updated_at = ?, message_count = message_count + 1
                WHERE id = ?
            """, (datetime.now().isoformat(), conversation_id))

        await db.commit()


async def ensure_conversation_exists(conversation_id: str, user_id: str, title: str = "新对话"):
    """确保对话记录存在，如果不存在则创建"""
    existing = await get_conversation(conversation_id)
    if not existing:
        async with aiosqlite.connect(DB_PATH) as db:
            now = datetime.now().isoformat()
            await db.execute("""
                INSERT OR IGNORE INTO conversations (id, user_id, title, created_at, updated_at, message_count, is_archived)
                VALUES (?, ?, ?, ?, ?, 0, 0)
            """, (conversation_id, user_id, title, now, now))
            await db.commit()
        print(f"[Database] 自动创建对话记录: {conversation_id}")
    return await get_conversation(conversation_id)
