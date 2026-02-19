"""
채팅 데이터를 관리하는 모듈입니다.
SQLite DB를 통해 채팅 기록을 저장/조회합니다.
"""
import aiosqlite
import asyncio
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import pytz

KST = pytz.timezone("Asia/Seoul")
db_path = "data/chatting.db"


class ChattingDataManager:
    """채팅 데이터 매니저 (싱글턴)"""
    _instance = None
    _initialized = False
    _init_lock = asyncio.Lock()

    def __new__(cls, db_path: str = db_path):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.db_path = db_path
            cls._instance._db = None
        return cls._instance

    def __init__(self, db_path: str = db_path):
        if not hasattr(self, 'db_path'):
            self.db_path = db_path
            self._db = None

    async def ensure_initialized(self):
        """데이터베이스가 초기화되었는지 확인합니다."""
        if not self._initialized:
            async with self._init_lock:
                if not self._initialized:
                    await self.initialize()

    async def initialize(self):
        """데이터베이스 연결을 초기화하고 테이블을 생성합니다."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        if self._db is None:
            self._db = await aiosqlite.connect(self.db_path)
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL UNIQUE,
                    char_count INTEGER NOT NULL,
                    points INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            await self._db.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_user_date 
                ON chat_messages (user_id, created_at)
            """)
            await self._db.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_channel_date 
                ON chat_messages (channel_id, created_at)
            """)
            await self._db.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_message_id 
                ON chat_messages (message_id)
            """)
            await self._db.commit()
            self._initialized = True

    async def close(self):
        """데이터베이스 연결을 닫습니다."""
        if self._db:
            await self._db.close()
            self._db = None

    async def add_chat_record(
        self,
        user_id: int,
        channel_id: int,
        message_id: int,
        char_count: int,
        points: int,
        created_at: str
    ) -> bool:
        """채팅 기록을 추가합니다."""
        await self.ensure_initialized()
        try:
            await self._db.execute("""
                INSERT OR IGNORE INTO chat_messages 
                    (user_id, channel_id, message_id, char_count, points, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, channel_id, message_id, char_count, points, created_at))
            await self._db.commit()
            return True
        except Exception as e:
            print(f"채팅 기록 추가 중 오류: {e}")
            return False

    async def get_user_chat_stats(
        self,
        user_id: int,
        start: str,
        end: str
    ) -> Tuple[int, int]:
        """기간별 유저 채팅 통계를 반환합니다. (총 메시지 수, 총 점수)"""
        await self.ensure_initialized()
        async with self._db.execute("""
            SELECT COUNT(*), COALESCE(SUM(points), 0)
            FROM chat_messages
            WHERE user_id = ? AND created_at >= ? AND created_at < ?
        """, (user_id, start, end)) as cursor:
            row = await cursor.fetchone()
            return (row[0], row[1]) if row else (0, 0)

    async def get_user_channel_stats(
        self,
        user_id: int,
        start: str,
        end: str
    ) -> List[Tuple[int, int, int]]:
        """채널별 유저 채팅 통계를 반환합니다. [(channel_id, count, points), ...]"""
        await self.ensure_initialized()
        async with self._db.execute("""
            SELECT channel_id, COUNT(*), COALESCE(SUM(points), 0)
            FROM chat_messages
            WHERE user_id = ? AND created_at >= ? AND created_at < ?
            GROUP BY channel_id
            ORDER BY SUM(points) DESC
        """, (user_id, start, end)) as cursor:
            return await cursor.fetchall()

    async def get_all_users_stats(
        self,
        start: str,
        end: str,
        user_ids: Optional[set] = None
    ) -> List[Tuple[int, int, int]]:
        """전체 유저의 채팅 통계를 반환합니다. [(user_id, count, points), ...]"""
        await self.ensure_initialized()
        if user_ids is not None:
            placeholders = ",".join("?" for _ in user_ids)
            query = f"""
                SELECT user_id, COUNT(*), COALESCE(SUM(points), 0)
                FROM chat_messages
                WHERE created_at >= ? AND created_at < ?
                    AND user_id IN ({placeholders})
                GROUP BY user_id
                ORDER BY SUM(points) DESC
            """
            params = [start, end] + list(user_ids)
        else:
            query = """
                SELECT user_id, COUNT(*), COALESCE(SUM(points), 0)
                FROM chat_messages
                WHERE created_at >= ? AND created_at < ?
                GROUP BY user_id
                ORDER BY SUM(points) DESC
            """
            params = [start, end]

        async with self._db.execute(query, params) as cursor:
            return await cursor.fetchall()

    async def get_last_scored_time(self, user_id: int) -> Optional[str]:
        """유저의 마지막 점수 획득 시간을 반환합니다."""
        await self.ensure_initialized()
        async with self._db.execute("""
            SELECT created_at FROM chat_messages
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def clear_all(self):
        """DB의 모든 채팅 기록을 삭제합니다."""
        await self.ensure_initialized()
        await self._db.execute("DELETE FROM chat_messages")
        await self._db.commit()

    async def bulk_insert(self, records: List[Tuple]) -> int:
        """대량의 채팅 기록을 한 번에 삽입합니다. (동기화용)"""
        await self.ensure_initialized()
        try:
            await self._db.executemany("""
                INSERT OR IGNORE INTO chat_messages 
                    (user_id, channel_id, message_id, char_count, points, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, records)
            await self._db.commit()
            return len(records)
        except Exception as e:
            print(f"대량 삽입 중 오류: {e}")
            return 0
