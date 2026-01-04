"""
Memory Service - 核心记忆服务

负责管理用户的长短期记忆数据
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path


class MemoryService:
    """记忆服务 - 管理长短期记忆"""

    def __init__(self, db_path: str = "data/memory.db"):
        """初始化记忆服务

        Args:
            db_path: SQLite数据库文件路径
        """
        self.db_path = db_path

        # 确保数据目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 支持字典式访问
        return conn

    def _init_database(self):
        """初始化数据库表结构"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 1. 用户画像表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id TEXT PRIMARY KEY,
            name TEXT,
            occupation TEXT,
            interests TEXT,  -- JSON array
            mbti TEXT,
            age_range TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 2. 地址记忆表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            label TEXT NOT NULL,        -- "家"、"公司"、"对象家"
            address TEXT NOT NULL,
            poi_id TEXT,
            lat REAL,
            lon REAL,
            use_count INTEGER DEFAULT 0,
            last_used TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, label)
        )
        """)

        # 3. 偏好记忆表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            category TEXT NOT NULL,     -- "navigation" | "music" | "food" | "vehicle"
            key TEXT NOT NULL,
            value TEXT NOT NULL,        -- JSON format
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, category, key)
        )
        """)

        # 4. 纪念日表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_anniversaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            label TEXT NOT NULL,
            date TEXT NOT NULL,         -- "MM-DD" format
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 5. 关系网络表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            relation TEXT,              -- "对象"、"母亲"、"朋友"
            home_address TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 6. 对话快照表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            time_range TEXT,
            summary TEXT NOT NULL,
            key_topics TEXT,            -- JSON array
            message_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 7. 临时上下文表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS temp_context (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        conn.commit()
        conn.close()

    # ==================== Phase 1: 位置记忆 ====================

    def save_location(
        self,
        user_id: str,
        label: str,
        address: str,
        poi_id: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None
    ) -> bool:
        """保存常用地址记忆

        Args:
            user_id: 用户ID
            label: 地址标签，如 "家"、"公司"、"对象家"
            address: 详细地址
            poi_id: POI ID（可选）
            lat: 纬度（可选）
            lon: 经度（可选）

        Returns:
            是否保存成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
            INSERT OR REPLACE INTO memory_locations
            (user_id, label, address, poi_id, lat, lon, use_count, last_used)
            VALUES (?, ?, ?, ?, ?, ?,
                    COALESCE((SELECT use_count FROM memory_locations WHERE user_id=? AND label=?), 0),
                    CURRENT_TIMESTAMP)
            """, (user_id, label, address, poi_id, lat, lon, user_id, label))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"保存地址记忆失败: {e}")
            return False

    def recall_location(self, user_id: str, label: str) -> Optional[Dict]:
        """精确召回地址记忆（通过标签）

        Args:
            user_id: 用户ID
            label: 地址标签，如 "家"、"公司"

        Returns:
            地址信息字典，未找到返回None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
            SELECT * FROM memory_locations
            WHERE user_id = ? AND label = ?
            """, (user_id, label))

            row = cursor.fetchone()
            conn.close()

            if row:
                return dict(row)
            return None
        except Exception as e:
            print(f"召回地址记忆失败: {e}")
            return None

    def search_location(self, user_id: str, query: str) -> Optional[Dict]:
        """模糊搜索地址记忆

        Args:
            user_id: 用户ID
            query: 搜索关键词（会在label和address中搜索）

        Returns:
            最匹配的地址信息，未找到返回None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 优先精确匹配label
            cursor.execute("""
            SELECT * FROM memory_locations
            WHERE user_id = ? AND label LIKE ?
            ORDER BY use_count DESC
            LIMIT 1
            """, (user_id, f"%{query}%"))

            row = cursor.fetchone()

            # 如果label没找到，再搜索address
            if not row:
                cursor.execute("""
                SELECT * FROM memory_locations
                WHERE user_id = ? AND address LIKE ?
                ORDER BY use_count DESC
                LIMIT 1
                """, (user_id, f"%{query}%"))
                row = cursor.fetchone()

            conn.close()

            if row:
                return dict(row)
            return None
        except Exception as e:
            print(f"搜索地址记忆失败: {e}")
            return None

    def update_location_usage(self, user_id: str, label: str) -> bool:
        """更新地址使用统计

        Args:
            user_id: 用户ID
            label: 地址标签

        Returns:
            是否更新成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
            UPDATE memory_locations
            SET use_count = use_count + 1,
                last_used = CURRENT_TIMESTAMP
            WHERE user_id = ? AND label = ?
            """, (user_id, label))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"更新地址使用统计失败: {e}")
            return False

    def list_all_locations(self, user_id: str) -> List[Dict]:
        """列出用户的所有地址记忆

        Args:
            user_id: 用户ID

        Returns:
            地址列表
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
            SELECT * FROM memory_locations
            WHERE user_id = ?
            ORDER BY use_count DESC, last_used DESC
            """, (user_id,))

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]
        except Exception as e:
            print(f"列出地址记忆失败: {e}")
            return []

    # ==================== Phase 1: 偏好记忆 ====================

    def save_preference(
        self,
        user_id: str,
        category: str,
        key: str,
        value: Any
    ) -> bool:
        """保存偏好记忆

        Args:
            user_id: 用户ID
            category: 偏好类别，如 "navigation"、"music"、"food"、"vehicle"
            key: 偏好键，如 "avoid_highway"、"favorite_genre"
            value: 偏好值（会自动转为JSON）

        Returns:
            是否保存成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 将value序列化为JSON
            value_json = json.dumps(value, ensure_ascii=False)

            cursor.execute("""
            INSERT OR REPLACE INTO memory_preferences
            (user_id, category, key, value, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, category, key, value_json))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"保存偏好记忆失败: {e}")
            return False

    def get_preference(
        self,
        user_id: str,
        category: str,
        key: str
    ) -> Optional[Any]:
        """获取偏好记忆

        Args:
            user_id: 用户ID
            category: 偏好类别
            key: 偏好键

        Returns:
            偏好值，未找到返回None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
            SELECT value FROM memory_preferences
            WHERE user_id = ? AND category = ? AND key = ?
            """, (user_id, category, key))

            row = cursor.fetchone()
            conn.close()

            if row:
                return json.loads(row['value'])
            return None
        except Exception as e:
            print(f"获取偏好记忆失败: {e}")
            return None

    def get_all_preferences(
        self,
        user_id: str,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取所有偏好记忆

        Args:
            user_id: 用户ID
            category: 可选，仅获取指定类别的偏好

        Returns:
            偏好字典 {key: value}
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if category:
                cursor.execute("""
                SELECT key, value FROM memory_preferences
                WHERE user_id = ? AND category = ?
                """, (user_id, category))
            else:
                cursor.execute("""
                SELECT category, key, value FROM memory_preferences
                WHERE user_id = ?
                """, (user_id,))

            rows = cursor.fetchall()
            conn.close()

            if category:
                # 返回 {key: value}
                return {row['key']: json.loads(row['value']) for row in rows}
            else:
                # 返回 {category: {key: value}}
                result = {}
                for row in rows:
                    cat = row['category']
                    if cat not in result:
                        result[cat] = {}
                    result[cat][row['key']] = json.loads(row['value'])
                return result
        except Exception as e:
            print(f"获取所有偏好记忆失败: {e}")
            return {}

    # ==================== Phase 2: 用户画像 ====================

    def check_profile_initialized(self, user_id: str) -> bool:
        """检查用户 profile 是否已初始化

        Args:
            user_id: 用户ID

        Returns:
            是否已初始化（True=已有profile记录）
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
            SELECT COUNT(*) as count FROM user_profiles
            WHERE user_id = ?
            """, (user_id,))

            row = cursor.fetchone()
            conn.close()

            return row['count'] > 0
        except Exception as e:
            print(f"检查profile初始化失败: {e}")
            return False

    def save_user_profile(
        self,
        user_id: str,
        name: Optional[str] = None,
        occupation: Optional[str] = None,
        interests: Optional[List[str]] = None,
        mbti: Optional[str] = None,
        age_range: Optional[str] = None
    ) -> bool:
        """保存/更新用户画像

        Args:
            user_id: 用户ID
            name: 姓名（可选）
            occupation: 职业（可选）
            interests: 兴趣列表（可选）
            mbti: MBTI性格类型（可选）
            age_range: 年龄段（可选，如 "20-30"）

        Returns:
            是否保存成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 检查是否已存在
            cursor.execute("SELECT user_id FROM user_profiles WHERE user_id = ?", (user_id,))
            exists = cursor.fetchone() is not None

            # 序列化 interests
            interests_json = json.dumps(interests, ensure_ascii=False) if interests else None

            if exists:
                # 更新（只更新非None的字段）
                update_fields = []
                update_values = []

                if name is not None:
                    update_fields.append("name = ?")
                    update_values.append(name)
                if occupation is not None:
                    update_fields.append("occupation = ?")
                    update_values.append(occupation)
                if interests is not None:
                    update_fields.append("interests = ?")
                    update_values.append(interests_json)
                if mbti is not None:
                    update_fields.append("mbti = ?")
                    update_values.append(mbti)
                if age_range is not None:
                    update_fields.append("age_range = ?")
                    update_values.append(age_range)

                if update_fields:
                    update_fields.append("updated_at = CURRENT_TIMESTAMP")
                    update_values.append(user_id)

                    sql = f"UPDATE user_profiles SET {', '.join(update_fields)} WHERE user_id = ?"
                    cursor.execute(sql, update_values)
            else:
                # 新建
                cursor.execute("""
                INSERT INTO user_profiles
                (user_id, name, occupation, interests, mbti, age_range)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, name, occupation, interests_json, mbti, age_range))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"保存用户画像失败: {e}")
            return False

    def \
            get_user_profile(self, user_id: str) -> Optional[Dict]:
        """获取用户画像

        Args:
            user_id: 用户ID

        Returns:
            用户画像字典，未找到返回None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
            SELECT * FROM user_profiles
            WHERE user_id = ?
            """, (user_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                profile = dict(row)
                # 反序列化 interests
                if profile.get('interests'):
                    profile['interests'] = json.loads(profile['interests'])
                return profile
            return None
        except Exception as e:
            print(f"获取用户画像失败: {e}")
            return None

    # ==================== Phase 2: 关系网络 ====================

    def save_relationship(
        self,
        user_id: str,
        name: str,
        relation: Optional[str] = None,
        home_address: Optional[str] = None,
        phone: Optional[str] = None
    ) -> bool:
        """保存关系网络信息

        Args:
            user_id: 用户ID
            name: 联系人姓名
            relation: 关系（如 "朋友"、"同事"、"对象"、"母亲"）
            home_address: 家庭地址（可选）
            phone: 电话（可选）

        Returns:
            是否保存成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
            INSERT INTO memory_relationships
            (user_id, name, relation, home_address, phone)
            VALUES (?, ?, ?, ?, ?)
            """, (user_id, name, relation, home_address, phone))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"保存关系网络失败: {e}")
            return False

    def get_relationship(self, user_id: str, name: str) -> Optional[Dict]:
        """通过姓名查询关系网络

        Args:
            user_id: 用户ID
            name: 联系人姓名

        Returns:
            关系信息字典，未找到返回None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
            SELECT * FROM memory_relationships
            WHERE user_id = ? AND name = ?
            ORDER BY created_at DESC
            LIMIT 1
            """, (user_id, name))

            row = cursor.fetchone()
            conn.close()

            if row:
                return dict(row)
            return None
        except Exception as e:
            print(f"获取关系网络失败: {e}")
            return None

    def search_relationship(self, user_id: str, query: str) -> Optional[Dict]:
        """模糊搜索关系网络（按姓名或关系）

        Args:
            user_id: 用户ID
            query: 搜索关键词

        Returns:
            最匹配的关系信息，未找到返回None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 优先精确匹配name
            cursor.execute("""
            SELECT * FROM memory_relationships
            WHERE user_id = ? AND name LIKE ?
            ORDER BY created_at DESC
            LIMIT 1
            """, (user_id, f"%{query}%"))

            row = cursor.fetchone()

            # 如果name没找到，再搜索relation
            if not row:
                cursor.execute("""
                SELECT * FROM memory_relationships
                WHERE user_id = ? AND relation LIKE ?
                ORDER BY created_at DESC
                LIMIT 1
                """, (user_id, f"%{query}%"))
                row = cursor.fetchone()

            conn.close()

            if row:
                return dict(row)
            return None
        except Exception as e:
            print(f"搜索关系网络失败: {e}")
            return None

    def list_all_relationships(self, user_id: str) -> List[Dict]:
        """列出用户的所有关系网络

        Args:
            user_id: 用户ID

        Returns:
            关系列表
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
            SELECT * FROM memory_relationships
            WHERE user_id = ?
            ORDER BY created_at DESC
            """, (user_id,))

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]
        except Exception as e:
            print(f"列出关系网络失败: {e}")
            return []

    # ==================== Phase 3: 对话快照（预留） ====================
    # Phase 3 will implement: save_conversation_snapshot, get_recent_snapshots

    # ==================== Phase 3: 智能召回（预留） ====================
    # Phase 3 will implement: smart_recall
